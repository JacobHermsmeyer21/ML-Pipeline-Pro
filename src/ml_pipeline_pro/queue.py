"""Redis-backed Celery dispatch; MongoDB remains the source of job status."""

from celery import Celery
from fastapi import Request

from ml_pipeline_pro.config import Settings


def make_celery(settings: Settings) -> Celery:
    app = Celery(
        "ml_pipeline_pro",
        broker=settings.redis_url.get_secret_value(),
        include=["ml_pipeline_pro.worker"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_ignore_result=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_time_limit=630,
        task_soft_time_limit=620,
        broker_connection_timeout=settings.dependency_timeout_seconds,
        broker_transport_options={
            "visibility_timeout": 3600,
            "socket_timeout": settings.dependency_timeout_seconds,
            "socket_connect_timeout": settings.dependency_timeout_seconds,
        },
        task_routes={"ml_pipeline_pro.train": {"queue": "training"}},
        beat_schedule={
            "recover-experiments": {"task": "ml_pipeline_pro.recover", "schedule": 15.0}
        },
    )
    return app


class Publisher:
    def __init__(self, settings: Settings) -> None:
        self.app = make_celery(settings)

    def publish(self, project_id: str, experiment_id: str) -> None:
        self.app.send_task(
            "ml_pipeline_pro.train",
            args=[project_id, experiment_id],
            task_id=experiment_id,
            queue="training",
            retry=False,
        )


def get_publisher(request: Request) -> Publisher:
    if not hasattr(request.app.state, "publisher"):
        request.app.state.publisher = Publisher(request.app.state.settings)
    return request.app.state.publisher
