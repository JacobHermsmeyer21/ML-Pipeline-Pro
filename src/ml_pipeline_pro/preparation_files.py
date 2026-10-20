"""Verify immutable preparation provenance before a worker uses it."""

import json

from ml_pipeline_pro.dataset_files import check_dataset_scope
from ml_pipeline_pro.dataset_preparation import MANIFEST_MAX_BYTES, digest
from ml_pipeline_pro.datasets import DatasetValidationError


def read_preparation(dataset, settings):
    if dataset.preparation is None:
        return None
    reference = dataset.preparation
    contents = []
    for file, limit in (
        (reference.source, min(settings.dataset_max_bytes, 10_000_000)),
        (reference.manifest, MANIFEST_MAX_BYTES),
    ):
        check_dataset_scope(file.uri, dataset.project_id, settings)
        try:
            root = settings.dataset_root.resolve()
            path = (root / file.uri).resolve(strict=True)
            path.relative_to(root)
            if not 0 < file.size_bytes <= limit:
                raise ValueError
            with path.open("rb") as source:
                content = source.read(file.size_bytes + 1)
            if len(content) != file.size_bytes or digest(content) != file.sha256:
                raise ValueError
            contents.append(content)
        except (OSError, ValueError):
            raise DatasetValidationError(
                "Preparation file hash or size verification failed"
            ) from None
    try:
        recipe = json.loads(contents[1])
        if (
            recipe["format_version"] != 1
            or recipe["source_sha256"] != reference.source.sha256
            or recipe["output_sha256"] != dataset.sha256
            or recipe["recipe_sha256"] != reference.recipe_sha256
            or recipe["feature_columns"] != dataset.feature_columns
            or recipe["row_counts"] != dataset.row_counts
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise DatasetValidationError(
            "Preparation metadata does not match the saved dataset"
        ) from None
    return recipe
