"""Celery training worker and periodic recovery of undispatched or expired jobs."""

import asyncio
import logging

from celery.signals import setup_logging

from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.connections import open_connections
from ml_pipeline_pro.execution import execute_experiment
from ml_pipeline_pro.logging import configure_logging
from ml_pipeline_pro.queue import Publisher, make_celery
from ml_pipeline_pro.tracking import TrackingStore

settings = Settings()
app = make_celery(settings)
logger = logging.getLogger(__name__)


@setup_logging.connect
def setup_worker_logging(**kwargs):
    configure_logging(settings)


@app.task(name="ml_pipeline_pro.train")
def train_experiment(project_id: str, experiment_id: str) -> str:
    configure_logging(settings)

    async def run():
        async with open_connections(settings) as connections:
            store = TrackingStore(connections.mongo.get_database(settings.mongodb_database))
            await store.ensure_indexes()
            return await execute_experiment(store, project_id, experiment_id, settings)

    return asyncio.run(run())


@app.task(name="ml_pipeline_pro.recover")
def recover_experiments() -> int:
    async def run():
        count = 0
        publisher = Publisher(settings)
        async with open_connections(settings) as connections:
            store = TrackingStore(connections.mongo.get_database(settings.mongodb_database))
            await store.ensure_indexes()
            for record in await store.experiments.pending_recovery():
                await asyncio.to_thread(publisher.publish, record.project_id, record.id)
                await store.experiments.mark_dispatched(record.project_id, record.id)
                count += 1
        return count

    return asyncio.run(run())
