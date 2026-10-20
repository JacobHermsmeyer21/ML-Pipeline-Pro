"""Training-fitted CSV preparation with immutable, reviewable transformation recipes."""

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from importlib.metadata import version
from time import perf_counter

from ml_pipeline_pro.datasets import DatasetValidationError
from ml_pipeline_pro.preparation_schemas import ColumnEncoding, PreparationSettings

MANIFEST_MAX_BYTES = 256 * 1024
MATRIX_MAX_BYTES = 64 * 1024 * 1024
PREPARATION_SECONDS = 30
SPLITS = ("train", "validation", "test")


def json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def selection_recipe_digest(recipe: dict) -> str:
    return digest(
        json_bytes({key: value for key, value in recipe.items() if key != "recipe_sha256"})
    )


@dataclass
class PreparedDataset:
    content: bytes
    manifest: bytes
    preview: dict


def _number(value: str) -> float:
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise DatasetValidationError("A numeric feature contains a nonnumeric value") from None
    if not math.isfinite(number) or abs(number) > 1e12:
        raise DatasetValidationError("A numeric feature exceeds the finite value bounds")
    return number


def transform_rows(rows: list[dict[str, str]], recipe: dict) -> list[list[float]]:
    """Apply saved raw feature transforms without fitting on new observations."""
    transformed = []
    for row in rows:
        values = []
        for column in recipe["columns"]:
            if column["treatment"] == "exclude":
                continue
            if column["name"] not in row:
                raise DatasetValidationError("A required source feature is missing")
            value = row[column["name"]]
            if value == "":
                if column["fill_value"] is None:
                    raise DatasetValidationError("Missing feature values require imputation")
                value = column["fill_value"]
            if column["treatment"] == "numeric":
                values.append(_number(value))
            elif column["treatment"] == "mapping":
                values.append(column["mapping"].get(value, column["unknown_value"]))
            else:
                values.extend(float(value == category) for category in column["categories"])
        transformed.append(values)
    return transformed


def decode_labels(ids: list[int], recipe: dict) -> list[str]:
    labels = {value: label for label, value in recipe["label_mapping"].items()}
    try:
        return [labels[value] for value in ids]
    except KeyError:
        raise DatasetValidationError("Prediction contains an unknown class ID") from None


def prepare_csv(
    content: bytes, config: PreparationSettings, settings, *, deadline: float | None = None
) -> PreparedDataset:
    deadline = perf_counter() + PREPARATION_SECONDS if deadline is None else deadline
    try:
        import numpy as np
        from sklearn.impute import SimpleImputer
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import OneHotEncoder
    except ImportError:
        raise ImportError("Install the training extra for dataset preparation") from None

    def check():
        if perf_counter() > deadline:
            raise TimeoutError("Dataset preparation exceeded its time budget")

    check()

    if len(content) > min(settings.dataset_max_bytes, 10_000_000):
        raise DatasetValidationError("Dataset exceeds the raw CSV byte limit")
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        headers = next(reader)
        if (
            not headers
            or len(headers) > 130
            or len(set(headers)) != len(headers)
            or any(not name.strip() or len(name.encode()) > 128 for name in headers)
        ):
            raise DatasetValidationError("CSV requires distinct nonempty bounded column names")
        if config.target_column not in headers or (
            config.split_column and config.split_column not in headers
        ):
            raise DatasetValidationError("Selected target or split column is absent from the CSV")
        if set(config.columns) - set(headers):
            raise DatasetValidationError("Encoding settings reference an absent column")
        reserved = {config.target_column, config.split_column}
        if any(
            name in reserved and option.treatment != "exclude"
            for name, option in config.columns.items()
        ):
            raise DatasetValidationError("Target and split columns cannot be features")
        rows = []
        for values in reader:
            check()
            if not values:
                continue
            if len(rows) >= settings.dataset_max_rows:
                raise DatasetValidationError("Dataset exceeds the configured row limit")
            if len(values) != len(headers):
                raise DatasetValidationError("CSV has an inconsistent column count")
            if any(len(value.encode()) > 128 for value in values):
                raise DatasetValidationError("CSV cell exceeds the 128-byte preparation limit")
            rows.append(dict(zip(headers, values, strict=True)))
    except (UnicodeDecodeError, csv.Error, StopIteration):
        raise DatasetValidationError("Dataset must be a valid UTF-8 CSV with a header") from None
    if not rows or any(not row[config.target_column] for row in rows):
        raise DatasetValidationError("Every row requires a nonempty target")
    labels = [row[config.target_column] for row in rows]
    classes = sorted(set(labels))
    if not 2 <= len(classes) <= 64:
        raise DatasetValidationError("Classification requires between 2 and 64 classes")
    indices = list(range(len(rows)))
    if config.split_column:
        membership = [row[config.split_column] for row in rows]
        if set(membership) != set(SPLITS):
            raise DatasetValidationError("Existing splits must contain train, validation and test")
    else:
        try:
            train_valid, test = train_test_split(
                indices,
                test_size=(len(rows) * config.test_percent + 99) // 100,
                stratify=labels,
                random_state=config.seed,
            )
            train, valid = train_test_split(
                train_valid,
                test_size=(len(rows) * config.validation_percent + 99) // 100,
                stratify=[labels[index] for index in train_valid],
                random_state=config.seed,
            )
        except ValueError:
            raise DatasetValidationError(
                "Classes are too small for these stratified splits; add rows, adjust ratios "
                "or supply existing splits"
            ) from None
        membership = [""] * len(rows)
        for split, members in zip(SPLITS, (train, valid, test), strict=True):
            for index in members:
                membership[index] = split
    partition = {
        split: [i for i, value in enumerate(membership) if value == split] for split in SPLITS
    }
    if any({labels[i] for i in members} != set(classes) for members in partition.values()):
        raise DatasetValidationError(
            "Each split must contain every class; add rows, adjust ratios or use existing splits"
        )
    training = partition["train"]
    label_mapping = config.label_mapping or {label: i for i, label in enumerate(classes)}
    if set(label_mapping) != set(classes) or set(label_mapping.values()) != set(
        range(len(classes))
    ):
        raise DatasetValidationError(
            "Target IDs must map each training class to a distinct 0..N-1 ID"
        )
    columns, output_names, warnings = [], [], []
    matrices = []
    for name in headers:
        check()
        if name in reserved:
            continue
        option = config.columns.get(name, ColumnEncoding())
        training_values = [rows[index][name] for index in training]
        present = [value for value in training_values if value != ""]
        treatment = option.treatment
        if treatment == "auto":
            try:
                for value in present:
                    float(value)
                treatment = "numeric"
            except ValueError:
                treatment = "one_hot"
        spec = {
            "name": name,
            "treatment": treatment,
            "categories": [],
            "mapping": {},
            "unknown_value": option.unknown_value,
            "fill_value": None,
            "missing_count": sum(row[name] == "" for row in rows),
            "unknown_count": 0,
            "output_columns": [],
        }
        if treatment == "exclude":
            columns.append(spec)
            continue
        if not present:
            raise DatasetValidationError(f"Column {name}: training values are entirely missing")
        if len(set(present)) == 1:
            warnings.append(f"Column {name}: constant in training")
        if len(present) >= 20 and len(set(present)) / len(present) >= 0.9:
            warnings.append(f"Column {name}: high uniqueness; review whether this is an identifier")
        if spec["missing_count"] and not config.impute_missing:
            raise DatasetValidationError(
                f"Column {name}: enable imputation or exclude missing features"
            )
        numeric = treatment == "numeric"
        train_values = np.array(
            [[_number(value) if value != "" else np.nan] for value in training_values]
            if numeric
            else [[value] for value in training_values],
            dtype=float if numeric else object,
        )
        if config.impute_missing:
            imputer = SimpleImputer(
                strategy="median" if numeric else "most_frequent",
                missing_values=np.nan if numeric else "",
            )
            train_values = imputer.fit_transform(train_values)
            spec["fill_value"] = (
                float(imputer.statistics_[0]) if numeric else str(imputer.statistics_[0])
            )
        categories = sorted({str(value[0]) for value in train_values}) if not numeric else []
        width = len(categories) if treatment == "one_hot" else 1
        if len(output_names) + width > 128:
            raise DatasetValidationError(
                f"Column {name}: encoding exceeds 128 features; exclude or remap it"
            )
        if len(rows) * (len(output_names) + width) * 4 > MATRIX_MAX_BYTES:
            raise DatasetValidationError("Encoded matrix exceeds the preparation memory limit")
        values = [[row[name] if row[name] != "" else spec["fill_value"]] for row in rows]
        if numeric:
            matrix = np.array([[_number(value[0])] for value in values], dtype=np.float32)
        else:
            spec["categories"] = categories
            spec["unknown_count"] = sum(value[0] not in categories for value in values)
            if spec["unknown_count"]:
                warnings.append(
                    f"Column {name}: {spec['unknown_count']} unseen values use the fixed fallback"
                )
            if treatment == "mapping":
                if set(option.mapping) != set(categories):
                    raise DatasetValidationError(
                        f"Column {name}: supply a numeric mapping for every training category"
                    )
                spec["mapping"] = option.mapping
                matrix = np.array(
                    [[option.mapping.get(value[0], option.unknown_value)] for value in values],
                    dtype=np.float32,
                )
                warnings.append(
                    f"Column {name}: your numeric mapping imposes distances between categories"
                )
            else:
                encoder = OneHotEncoder(
                    handle_unknown="ignore", sparse_output=False, dtype=np.float32
                )
                encoder.fit(train_values)
                matrix = encoder.transform(np.array(values, dtype=object))
        names = [f"feature_{len(output_names) + i}" for i in range(width)]
        spec["output_columns"] = names
        output_names.extend(names)
        columns.append(spec)
        matrices.append(matrix)
    if not matrices:
        raise DatasetValidationError("Choose at least one input feature")
    check()
    matrix = np.concatenate(matrices, axis=1)
    output = io.BytesIO()
    line = io.StringIO(newline="")
    writer = csv.writer(line, lineterminator="\n")

    def write(values):
        check()
        line.seek(0)
        line.truncate()
        writer.writerow(values)
        encoded = line.getvalue().encode()
        if output.tell() + len(encoded) > settings.dataset_max_bytes:
            raise DatasetValidationError("Prepared CSV exceeds the configured output byte limit")
        output.write(encoded)

    write([*output_names, "target", "split"])
    for index, row in enumerate(matrix):
        write(
            [
                *(format(float(value), ".9g") for value in row),
                label_mapping[labels[index]],
                membership[index],
            ]
        )
    canonical = output.getvalue()
    recipe_settings = config.model_dump(exclude={"reviewed_sha256", "name", "version"})
    recipe_sha = digest(json_bytes(recipe_settings))
    recipe = {
        "format_version": 1,
        "implementation": "classification-csv-v1",
        "source_sha256": digest(content),
        "output_sha256": digest(canonical),
        "recipe_sha256": recipe_sha,
        "settings": recipe_settings,
        "dependencies": {
            name: version(name) for name in ("scikit-learn", "numpy", "ml-pipeline-pro")
        },
        "columns": columns,
        "feature_columns": output_names,
        "label_mapping": label_mapping,
        "split_sha256": digest(json_bytes(membership)),
        "row_counts": {name: len(values) for name, values in partition.items()},
        "class_counts": {
            name: {label: sum(labels[i] == label for i in values) for label in classes}
            for name, values in partition.items()
        },
    }
    # Counts are observations, not learned parameters. Keep the complete recipe for provenance.
    manifest = json_bytes(recipe)
    if len(manifest) > MANIFEST_MAX_BYTES:
        raise DatasetValidationError("Preparation metadata exceeds its size limit")
    check()
    preview = {
        **recipe,
        "preview_sha256": digest(manifest),
        "warnings": warnings,
        "encoded_width": len(output_names),
        "source_headers": headers,
    }
    return PreparedDataset(canonical, manifest, preview)
