"""Enumerate and remove only the exact application-owned deletion candidates."""

import hashlib
import json
import re
import shutil
from pathlib import Path

from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.storage_control import regular_path


def storage_identity(settings):
    roots = [str(settings.dataset_root.resolve()), str(settings.artifact_root.resolve())]
    return hashlib.sha256(json.dumps(roots).encode()).hexdigest()


def dataset_references(document):
    refs = [document["uri"]]
    preparation = document.get("preparation")
    if preparation:
        refs += [preparation["source"]["uri"], preparation["manifest"]["uri"]]
    return refs


def owned_path(settings, project, entry):
    uri = entry["uri"]
    if entry["storage"] == "datasets":
        scope = settings.dataset_root / "uploads" / project
        path = regular_path(settings.dataset_root, uri)
        if path.parent != scope.absolute():
            raise ApiError(409, "unsafe_storage_path", "Dataset file is outside owned uploads")
        return path
    parts = Path(uri).parts
    if len(parts) != 2 or parts[0] != project or not re.fullmatch(r"[\w-]{1,128}", parts[1]):
        raise ApiError(409, "unsafe_storage_path", "Invalid experiment artifact scope")
    return regular_path(settings.artifact_root, uri)


def tree_files(path):
    if not path.exists():
        return []
    if path.is_file():
        stat = path.stat()
        return [("", stat.st_size, stat.st_mtime_ns)]
    files = []
    for child in sorted(path.iterdir()):
        checked = regular_path(path, child.name)
        for name, size, modified in tree_files(checked):
            files.append((str(Path(child.name) / name), size, modified))
    return files


def plan_files(settings, project, deleted_datasets, survivors, experiment_ids):
    referenced = {
        (settings.dataset_root / uri).resolve()
        for document in survivors
        for uri in dataset_references(document)
    }
    entries, shared, unmanaged = [], set(), set()
    candidates = {uri for doc in deleted_datasets for uri in dataset_references(doc)}
    for uri in sorted(candidates):
        logical = Path(uri)
        if len(logical.parts) != 3 or logical.parts[:2] != ("uploads", project):
            unmanaged.add(uri)
            continue
        entry = {"storage": "datasets", "uri": uri}
        path = owned_path(settings, project, entry)
        if path.resolve() in referenced:
            shared.add(uri)
        else:
            entries.append(entry)
    entries += [
        {"storage": "artifacts", "uri": f"{project}/{identity}"}
        for identity in sorted(set(experiment_ids))
    ]
    files, size, signatures = 0, 0, []
    for entry in entries:
        contents = tree_files(owned_path(settings, project, entry))
        files += len(contents)
        size += sum(row[1] for row in contents)
        signatures.append((entry, contents))
    return (
        entries,
        {
            "files": files,
            "size_bytes": size,
            "shared_files": len(shared),
            "unmanaged_files": len(unmanaged),
        },
        signatures,
    )


def remove_entry(settings, project, entry):
    path = owned_path(settings, project, entry)
    # Recheck the entire tree before a recursive operation, including junctions.
    tree_files(path)
    if path.is_dir():
        if entry["storage"] != "artifacts":
            raise ApiError(409, "unsafe_storage_path", "An uploaded file became a directory")
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)
