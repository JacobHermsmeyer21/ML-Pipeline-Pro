"""Bounded local CSV loading with explicit dataset splits and content hashing."""

import csv
import hashlib
import io
import math
from dataclasses import dataclass, field

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.schemas import DatasetDefinition


class DatasetValidationError(ValueError):
    pass


@dataclass
class Split:
    features: list[list[float]] = field(default_factory=list)
    targets: list[int] = field(default_factory=list)


@dataclass
class LoadedDataset:
    sha256: str
    splits: dict[str, Split]
    num_classes: int

    @property
    def row_counts(self) -> dict[str, int]:
        return {name: len(split.targets) for name, split in self.splits.items()}


def load_dataset(definition: DatasetDefinition, settings: Settings) -> LoadedDataset:
    root = settings.dataset_root.resolve()
    try:
        path = (root / definition.uri).resolve(strict=True)
        path.relative_to(root)
        with path.open("rb") as source:
            content = source.read(settings.dataset_max_bytes + 1)
    except (OSError, ValueError):
        raise DatasetValidationError(
            "Dataset must be a readable file under the dataset root"
        ) from None
    if len(content) > settings.dataset_max_bytes:
        raise DatasetValidationError("Dataset exceeds the configured file size limit")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DatasetValidationError("Dataset must be a UTF-8 CSV file") from None

    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    required = {*definition.feature_columns, definition.target_column, definition.split_column}
    try:
        header = reader.fieldnames
        if not header or len(header) != len(set(header)) or not required.issubset(header):
            raise DatasetValidationError(
                "CSV must contain distinct feature, target, and split columns"
            )
        splits = {name: Split() for name in ("train", "validation", "test")}
        for number, row in enumerate(reader, start=1):
            if number > settings.dataset_max_rows:
                raise DatasetValidationError("Dataset exceeds the configured row limit")
            if None in row or any(value is None for value in row.values()):
                raise DatasetValidationError(f"CSV row {number} has an inconsistent column count")
            split = row[definition.split_column]
            if split not in splits:
                raise DatasetValidationError(f"CSV row {number} has an invalid split")
            try:
                features = [float(row[column]) for column in definition.feature_columns]
                label = int(row[definition.target_column])
            except ValueError:
                raise DatasetValidationError(
                    f"CSV row {number} requires numeric features and an integer target"
                ) from None
            if not all(math.isfinite(value) and abs(value) <= 1e12 for value in features):
                raise DatasetValidationError(f"CSV row {number} has invalid feature values")
            if not 0 <= label < 64:
                raise DatasetValidationError(f"CSV row {number} requires a target between 0 and 63")
            splits[split].features.append(features)
            splits[split].targets.append(label)
    except csv.Error:
        raise DatasetValidationError("Dataset contains malformed CSV") from None

    if any(not split.targets for split in splits.values()):
        raise DatasetValidationError(
            "Dataset must contain nonempty train, validation, and test splits"
        )
    training_labels = set(splits["train"].targets)
    if len(training_labels) < 2 or training_labels != set(range(len(training_labels))):
        raise DatasetValidationError(
            "Training targets must be contiguous class IDs starting at zero"
        )
    if any(not set(split.targets).issubset(training_labels) for split in splits.values()):
        raise DatasetValidationError(
            "Validation and test targets must appear in the training split"
        )
    return LoadedDataset(hashlib.sha256(content).hexdigest(), splits, len(training_labels))
