"""Shared asynchronous clients, owned by the application lifespan."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

from ml_pipeline_pro.config import Settings


@dataclass
class Connections:
    mongo: AsyncMongoClient
    redis: Redis


@asynccontextmanager
async def open_connections(settings: Settings) -> AsyncIterator[Connections]:
    timeout = settings.dependency_timeout_seconds
    async with AsyncExitStack() as stack:
        mongo = AsyncMongoClient(
            settings.mongodb_uri.get_secret_value(),
            serverSelectionTimeoutMS=int(timeout * 1000),
            connectTimeoutMS=int(timeout * 1000),
            socketTimeoutMS=int(timeout * 1000),
            timeoutMS=int(timeout * 1000),
            tz_aware=True,
        )
        stack.push_async_callback(mongo.close)
        redis = Redis.from_url(
            settings.redis_url.get_secret_value(),
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
            retry=Retry(NoBackoff(), 0),
        )
        stack.push_async_callback(redis.aclose)
        yield Connections(mongo=mongo, redis=redis)


async def check_readiness(connections: Connections, settings: Settings) -> dict[str, str]:
    async def ping(name: str) -> str:
        try:
            operation = (
                connections.mongo.admin.command("ping")
                if name == "mongodb"
                else connections.redis.ping()
            )
            async with asyncio.timeout(settings.dependency_timeout_seconds):
                await operation
        except (PyMongoError, RedisError, OSError, TimeoutError):
            return "down"
        return "up"

    mongo_status, redis_status = await asyncio.gather(ping("mongodb"), ping("redis"))
    return {"mongodb": mongo_status, "redis": redis_status}
