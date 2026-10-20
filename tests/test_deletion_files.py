import asyncio
import os
import signal
import subprocess
import sys
import threading

import pytest
from filelock import Timeout

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.deletion_files import owned_path, plan_files, remove_entry
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.storage_control import (
    finish_owned,
    native_lock,
    publication_lock,
    regular_path,
)


def test_native_lock_excludes_other_processes_and_survives_process_death(tmp_path):
    path = tmp_path / "native.lock"
    program = (
        "import os, sys; from ml_pipeline_pro.storage_control import native_lock; "
        "lock = native_lock(sys.argv[1]); lock.acquire(); "
        "print(os.getpid(), flush=True); sys.stdin.read()"
    )
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", program, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    worker_pid = None
    try:
        # Windows' venv launcher has a different PID from the actual lock owner.
        worker_pid = int(process.stdout.readline().strip())
        with pytest.raises(Timeout):
            with native_lock(path):
                pytest.fail("A different process already owns this storage lock")
        os.kill(worker_pid, signal.SIGTERM)
        process.wait(timeout=10)
        with native_lock(path):
            assert path.exists()
        assert path.exists() and path.stat().st_size == 0
    finally:
        if process.poll() is None:
            if worker_pid is not None:
                os.kill(worker_pid, signal.SIGTERM)
            else:
                process.terminate()
        process.communicate(timeout=10)


def test_repeated_cancellation_cannot_release_a_live_thread_storage_lock(tmp_path):
    async def run():
        settings = Settings(_env_file=None, artifact_root=tmp_path)
        started, release = threading.Event(), threading.Event()

        def file_work():
            started.set()
            assert release.wait(10)

        async def owner():
            async with publication_lock(settings, "demo"):
                await finish_owned(asyncio.to_thread(file_work))

        task = asyncio.create_task(owner())
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        try:
            with pytest.raises(Timeout):
                with native_lock(tmp_path / ".control/demo/publication.lock"):
                    pytest.fail("The owned thread is still writing")
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with publication_lock(settings, "demo", wait=False):
            pass

    asyncio.run(run())


@pytest.mark.parametrize("uri", ["../outside", "/outside", "demo/../outside", "demo"])
def test_artifact_cleanup_rejects_non_experiment_paths(tmp_path, uri):
    settings = Settings(_env_file=None, artifact_root=tmp_path)
    with pytest.raises(ApiError, match="scope"):
        owned_path(settings, "demo", {"storage": "artifacts", "uri": uri})


def test_file_plan_retains_shared_preparation_references_and_unmanaged_inputs(tmp_path):
    settings = Settings(
        _env_file=None, dataset_root=tmp_path / "data", artifact_root=tmp_path / "artifacts"
    )
    uploads = settings.dataset_root / "uploads/demo"
    uploads.mkdir(parents=True)
    for name in ("source.csv", "prepared.csv", "recipe.preparation.json"):
        (uploads / name).write_text(name)
    original = settings.dataset_root / "operator.csv"
    original.write_text("operator original")
    removed = {
        "uri": "uploads/demo/prepared.csv",
        "preparation": {
            "source": {"uri": "uploads/demo/source.csv"},
            "manifest": {"uri": "uploads/demo/recipe.preparation.json"},
        },
    }
    survivor = {"uri": "uploads/demo/source.csv"}
    artifact = settings.artifact_root / "demo/experiment/old-attempt/model.pt"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"old checkpoint")
    entries, counts, _ = plan_files(
        settings, "demo", [removed, {"uri": "operator.csv"}], [survivor], ["experiment"]
    )
    assert counts["shared_files"] == 1 and counts["unmanaged_files"] == 1
    assert counts["files"] == 3
    for entry in entries:
        remove_entry(settings, "demo", entry)
        remove_entry(settings, "demo", entry)  # Crash after unlink/before progress persistence.
    assert (uploads / "source.csv").read_text() == "source.csv"
    assert original.read_text() == "operator original"
    assert not (uploads / "prepared.csv").exists()
    assert not (uploads / "recipe.preparation.json").exists()
    assert not (settings.artifact_root / "demo/experiment").exists()


def test_regular_path_rejects_traversal_before_any_cleanup(tmp_path):
    outside = tmp_path.parent / "must-survive.txt"
    with pytest.raises(ApiError):
        regular_path(tmp_path, "../must-survive.txt")
    assert not outside.exists()
