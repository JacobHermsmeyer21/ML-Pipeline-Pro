"""Project saved, verified features without fitting transforms or changing rows."""

import copy
import csv
import io
from dataclasses import dataclass
from time import perf_counter

from ml_pipeline_pro.column_schemas import ColumnEdit, ColumnPreview, DatasetColumns, EditableColumn
from ml_pipeline_pro.dataset_files import check_dataset_scope
from ml_pipeline_pro.dataset_preparation import (
    MANIFEST_MAX_BYTES,
    PREPARATION_SECONDS,
    digest,
    json_bytes,
    selection_recipe_digest,
)
from ml_pipeline_pro.datasets import DatasetValidationError, load_dataset
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.preparation_files import read_preparation


def request_digest(project, parent_id, body: ColumnEdit):
    return digest(json_bytes({"project": project, "parent_id": parent_id, **body.model_dump()}))


def snapshot(dataset, settings):
    check_dataset_scope(dataset.uri, dataset.project_id, settings)
    try:
        loaded = load_dataset(dataset, settings)
        if loaded.sha256 != dataset.sha256:
            raise DatasetValidationError("Dataset content changed after registration")
        del loaded
        recipe = read_preparation(dataset, settings)
        root = settings.dataset_root.resolve()
        path = (root / dataset.uri).resolve(strict=True)
        path.relative_to(root)
        with path.open("rb") as source:
            content = source.read(settings.dataset_max_bytes + 1)
        if digest(content) != dataset.sha256:
            raise DatasetValidationError("Dataset content changed during reading")
        columns = (
            [
                EditableColumn(name=column["name"], output_columns=column["output_columns"])
                for column in recipe["columns"]
                if column["treatment"] != "exclude"
            ]
            if recipe
            else [
                EditableColumn(name=name, output_columns=[name]) for name in dataset.feature_columns
            ]
        )
        if [name for col in columns for name in col.output_columns] != dataset.feature_columns:
            raise DatasetValidationError("Saved feature groups do not match the dataset")
        details = DatasetColumns(
            dataset_id=dataset.id,
            name=dataset.name,
            version=dataset.version,
            source_sha256=dataset.sha256,
            columns=columns,
            target_column=recipe["settings"]["target_column"] if recipe else dataset.target_column,
            split_column=(recipe["settings"].get("split_column") or dataset.split_column)
            if recipe
            else dataset.split_column,
            row_counts=dataset.row_counts,
            encoded_width=len(dataset.feature_columns),
        )
        return content, recipe, details
    except (DatasetValidationError, OSError, ValueError, KeyError, TypeError):
        raise ApiError(
            409, "dataset_file_conflict", "Saved dataset content or preparation is unavailable"
        ) from None


@dataclass
class ColumnProjection:
    content: bytes
    manifest: bytes | None
    preview: ColumnPreview
    lineage: dict


def project_columns(dataset, body: ColumnEdit, settings) -> ColumnProjection:
    deadline = perf_counter() + PREPARATION_SECONDS
    content, recipe, source = snapshot(dataset, settings)
    if body.source_sha256 != dataset.sha256:
        raise ApiError(409, "column_review_required", "Dataset changed; review its columns again")
    dropped = set(body.drop_columns)
    editable = {column.name for column in source.columns}
    if not dropped < editable:
        raise ApiError(
            422,
            "invalid_column_selection",
            "Drop existing inputs only; keep at least one. Target and split are protected.",
        )
    if body.version == dataset.version:
        raise ApiError(409, "dataset_identity_conflict", "Choose a new dataset version")
    kept = [column for column in source.columns if column.name not in dropped]
    features = [name for column in kept for name in column.output_columns]
    output = io.BytesIO()
    line = io.StringIO(newline="")
    writer = csv.writer(line, lineterminator="\n")
    names = [*features, dataset.target_column, dataset.split_column]

    def write(values):
        if perf_counter() > deadline:
            raise TimeoutError
        line.seek(0)
        line.truncate()
        writer.writerow(values)
        chunk = line.getvalue().encode()
        if output.tell() + len(chunk) > settings.dataset_max_bytes:
            raise ApiError(422, "invalid_column_selection", "Selected CSV exceeds the byte limit")
        output.write(chunk)

    write(names)
    for row in csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True):
        write([row[name] for name in names])
    canonical = output.getvalue()
    lineage = {
        "parent_id": dataset.id,
        "parent_sha256": dataset.sha256,
        "parent_manifest_sha256": dataset.preparation.manifest.sha256 if recipe else None,
        "drop_columns": body.drop_columns,
        "request_sha256": request_digest(dataset.project_id, dataset.id, body),
    }
    manifest = None
    if recipe:
        child = copy.deepcopy(recipe)
        child.update(
            format_version=2,
            implementation="classification-csv-selection-v1",
            output_sha256=digest(canonical),
            feature_columns=features,
            selection=lineage,
        )
        for column in child["columns"]:
            if column["name"] in dropped:
                column.update(
                    treatment="exclude",
                    output_columns=[],
                    categories=[],
                    mapping={},
                    fill_value=None,
                    unknown_count=0,
                )
        child["recipe_sha256"] = selection_recipe_digest(child)
        manifest = json_bytes(child)
        if len(manifest) > MANIFEST_MAX_BYTES:
            raise ApiError(
                422, "invalid_column_selection", "Preparation metadata exceeds its limit"
            )
    preview_sha = digest(
        json_bytes(
            {
                "source": source.model_dump(),
                "version": body.version,
                "selection": lineage,
                "output_sha256": digest(canonical),
                "manifest_sha256": digest(manifest) if manifest else None,
            }
        )
    )
    if perf_counter() > deadline:
        raise TimeoutError
    return ColumnProjection(
        canonical,
        manifest,
        ColumnPreview(
            source=source,
            version=body.version,
            drop_columns=body.drop_columns,
            kept_columns=kept,
            feature_columns=features,
            encoded_width=len(features),
            row_counts=dataset.row_counts,
            preview_sha256=preview_sha,
        ),
        lineage,
    )
