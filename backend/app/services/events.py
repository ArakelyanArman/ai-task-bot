import json

from redis.asyncio import Redis

from app.core.config import get_settings
from app.schemas.events import TaskEvent


EVENTS_CHANNEL = "task_events"


async def publish_event(event: TaskEvent) -> None:
    redis = Redis.from_url(get_settings().redis_url)
    try:
        await redis.publish(EVENTS_CHANNEL, json.dumps(event.model_dump(mode="json")))
    finally:
        await redis.aclose()
