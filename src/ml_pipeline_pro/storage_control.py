"""Native process-held storage locks, never stolen after a database lease expires."""

import asyncio
import hashlib
import re
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from pathlib import Path
from time import monotonic

from filelock import FileLock, SoftFileLock, Timeout

from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.lifecycle import registration_generation


def regular_path(root, relative):
    """Resolve an app-owned path while refusing symlinks and Windows reparse points."""
    root = Path(root).absolute()
    candidate = root / relative
    try:
        candidate.relative_to(root)
        if any(part in {"..", "."} for part in Path(relative).parts):
            raise ValueError
        for path in [root, *reversed(candidate.parents), candidate]:
            if path != root and not path.is_relative_to(root):
                continue
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError
            if path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
                raise ValueError
        candidate.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        raise ApiError(
            409, "unsafe_storage_path", "Storage path is outside its owned scope"
        ) from None
    return candidate


def control_root(settings, project):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", project):
        raise ApiError(409, "unsafe_storage_path", "Invalid project storage scope")
    path = regular_path(settings.artifact_root, f".control/{project}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def native_lock(path):
    lock = FileLock(
        path, timeout=0, thread_local=False, fallback_to_soft=False, preserve_lock_file=True
    )
    if isinstance(lock, SoftFileLock):
        raise OSError("Native filesystem locks are required")
    return lock


def attempt_directory(settings, project, collection, identity):
    digest = hashlib.sha256(f"{collection}:{identity}".encode()).hexdigest()
    return regular_path(control_root(settings, project), digest)


@contextmanager
def attempt_lock(settings, project, collection, identity, token):
    directory = attempt_directory(settings, project, collection, identity)
    directory.mkdir(exist_ok=True)
    digest = hashlib.sha256(token.encode()).hexdigest()
    with native_lock(directory / f"{digest}.lock"):
        yield


@asynccontextmanager
async def publication_lock(settings, project, *, wait=True):
    lock = native_lock(control_root(settings, project) / "publication.lock")
    deadline = monotonic() + 60
    while True:
        try:
            lock.acquire()
            break
        except Timeout:
            if not wait or monotonic() >= deadline:
                raise ApiError(
                    409, "deletion_blocked", "Project storage is busy; try again"
                ) from None
            await asyncio.sleep(0.025)
    try:
        yield
    finally:
        lock.release()


async def finish_owned(awaitable):
    """Cancellation cannot release a lock while its filesystem/worker thread survives."""
    task = asyncio.ensure_future(awaitable)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError as cancelled:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not task.cancelled():
            task.exception()
        raise cancelled


def dataset_registration(function):
    @wraps(function)
    async def registered(*args, **kwargs):
        request, project, store = kwargs["request"], kwargs["project"], kwargs["store"]
        generation = await store.lifecycle.generation(project)
        token = registration_generation.set((project, generation))
        try:
            async with publication_lock(request.app.state.settings, project):
                if await store.lifecycle.generation(project) != generation:
                    raise ApiError(409, "deletion_in_progress", "Registration crossed a deletion")
                return await finish_owned(function(*args, **kwargs))
        except OSError:
            raise ApiError(
                503, "dataset_storage_unavailable", "Dataset storage is unavailable"
            ) from None
        finally:
            registration_generation.reset(token)

    return registered
