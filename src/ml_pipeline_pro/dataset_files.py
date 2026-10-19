"""Project boundaries and immutable publication for locally uploaded CSV files."""

import hashlib
import os
from pathlib import Path

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.errors import ApiError

UPLOAD_MAX_BYTES = 10_000_000
UPLOAD_RECEIVE_SECONDS = 30


def check_dataset_scope(uri: str, project: str, settings: Settings) -> None:
    """Protect uploaded files through ordinary registration too, including symlink aliases."""
    root = settings.dataset_root.resolve()
    protected = root / "uploads"
    candidate = (root / uri).resolve()
    logical = Path(uri).parts
    if logical and logical[0] == "uploads" and (len(logical) < 2 or logical[1] != project):
        raise ApiError(404, "dataset_not_found", "Dataset file was not found in this project")
    if candidate.is_relative_to(protected):
        relative = candidate.relative_to(protected).parts
        if not relative or relative[0] != project:
            raise ApiError(404, "dataset_not_found", "Dataset file was not found in this project")
    # Resolve the protected directory too: an operator-created alias must not bypass ownership.
    resolved_protected = protected.resolve()
    if candidate.is_relative_to(resolved_protected):
        relative = candidate.relative_to(resolved_protected).parts
        if not relative or relative[0] != project:
            raise ApiError(404, "dataset_not_found", "Dataset file was not found in this project")


def upload_directory(project: str, settings: Settings) -> Path:
    root = settings.dataset_root.resolve(strict=True)
    protected = root / "uploads"
    protected.mkdir(exist_ok=True)
    if protected.is_symlink() or protected.resolve().parent != root:
        raise OSError("Upload storage is not a regular directory")
    directory = protected / project
    directory.mkdir(exist_ok=True)
    if directory.is_symlink() or directory.resolve().parent != protected:
        raise OSError("Project upload storage is not a regular directory")
    return directory


def publish_dataset(staged: Path, directory: Path, digest: str, size: int) -> str:
    destination = directory / f"{digest}.csv"
    try:
        # Same-filesystem link is atomic and never replaces a prior destination.
        os.link(staged, destination)
    except FileExistsError:
        if destination.is_symlink() or destination.stat().st_size != size:
            raise ApiError(
                409, "dataset_file_conflict", "Saved dataset content does not match"
            ) from None
        with destination.open("rb") as source:
            content = source.read(size + 1)
        if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
            raise ApiError(
                409, "dataset_file_conflict", "Saved dataset content does not match"
            ) from None
    return f"uploads/{directory.name}/{digest}.csv"
