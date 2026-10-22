from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings


async def enqueue_transcription(task_id: int, file_id: str) -> None:
    settings = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await redis.enqueue_job("transcribe_task", task_id, file_id)
    finally:
        await redis.close()
