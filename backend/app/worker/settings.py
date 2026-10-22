from arq.connections import RedisSettings

from app.core.config import get_settings
from app.worker.tasks import transcribe_task


class WorkerSettings:
    functions = [transcribe_task]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
    job_timeout = 120
