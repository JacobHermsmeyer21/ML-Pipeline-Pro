"""Small local artifacts with atomic writes and verified downloads."""

import hashlib
import os
import tempfile

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.schemas import ArtifactReference


class ArtifactError(ValueError):
    pass


def write_artifact(
    content: bytes, name: str, project_id: str, experiment_id: str, token: str, settings: Settings
) -> ArtifactReference:
    root = settings.artifact_root.resolve()
    directory = (root / project_id / experiment_id / token).resolve()
    try:
        directory.relative_to(root)
    except ValueError:
        raise ArtifactError("Artifact destination is outside the configured storage") from None
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / name
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return ArtifactReference(
        name=name,
        uri=destination.relative_to(root).as_posix(),
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )


def read_artifact(
    artifact: ArtifactReference, project_id: str, experiment_id: str, settings: Settings
) -> bytes:
    root = settings.artifact_root.resolve()
    scope = root / project_id / experiment_id
    try:
        path = (root / artifact.uri).resolve(strict=True)
        path.relative_to(scope)
        with path.open("rb") as stream:
            content = stream.read(10_000_001)
    except (OSError, ValueError):
        raise ArtifactError("Artifact is missing or outside this experiment's storage") from None
    if (
        len(content) != artifact.size_bytes
        or hashlib.sha256(content).hexdigest() != artifact.sha256
    ):
        raise ArtifactError("Artifact content does not match the recorded hash and size")
    return content
