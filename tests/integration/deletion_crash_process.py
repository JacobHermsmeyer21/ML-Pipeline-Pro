"""Disposable deletion process stopped at a durable boundary by its parent test."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from ml_pipeline_pro import deletions
from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.deletion_schemas import DeletionRequest
from ml_pipeline_pro.deletions import DeletionStore
from ml_pipeline_pro.lifecycle import Lifecycle
from tests.integration.helpers import integration_settings


async def run(args):
    settings = integration_settings(
        mongodb_database=args.database,
        dataset_root=Path(args.dataset_root),
        artifact_root=Path(args.artifact_root),
    )
    marker = Path(args.marker)

    def mark(phase):
        marker.write_text(json.dumps({"pid": os.getpid(), "phase": phase}), encoding="utf-8")

    async def pause(phase):
        mark(phase)
        await asyncio.Event().wait()

    mark("starting")
    transaction = Lifecycle.transaction

    async def checkpoint(self, callback):
        value = await transaction(self, callback)
        if (
            (args.phase == "before_cleanup" and callback.__name__ == "commit")
            or (args.phase == "after_metadata" and callback.__name__ == "erase")
            or (args.phase == "after_complete" and callback.__name__ == "complete")
        ):
            await pause(args.phase)
        return value

    Lifecycle.transaction = checkpoint
    original = deletions.remove_entry

    def remove(*values):
        original(*values)
        if args.phase == "after_file":
            import time

            mark(args.phase)
            while True:
                time.sleep(0.05)

    deletions.remove_entry = remove
    async with open_connections(settings) as connections:
        store = DeletionStore(connections.mongo.get_database(args.database), settings)
        await store.delete(
            "demo",
            "datasets",
            args.record_id,
            DeletionRequest(preview_sha256=args.preview_sha256),
            "crash-test",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in (
        "database",
        "dataset-root",
        "artifact-root",
        "record-id",
        "preview-sha256",
        "marker",
        "phase",
    ):
        parser.add_argument("--" + name, required=True)
    asyncio.run(run(parser.parse_args()))
