import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from arq import Retry
from google.genai.errors import APIError

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.enums import TranscriptionStatus
from app.repositories.tasks import TaskRepository
from app.schemas.events import TaskEvent
from app.schemas.tasks import TaskRead
from app.services.telegram import download_file
from app.services.transcription import transcribe
from app.services.events import publish_event


logger = logging.getLogger(__name__)


async def mark_failed(task_id: int) -> None:
    async with SessionLocal() as session:
        task = await TaskRepository(session).get(task_id)
        if task is not None:
            await TaskRepository(session).update(
                task,
                transcription_status=TranscriptionStatus.FAILED,
                error_message="Couldn't transcribe the voice message",
            )
            await session.commit()
            await publish_event(
                TaskEvent(type="task.updated", task=TaskRead.model_validate(task))
            )


def is_retryable_api_error(error: APIError) -> bool:
    return error.code == 429 or error.code >= 500


async def transcribe_task(ctx: dict, task_id: int, file_id: str) -> None:
    async with SessionLocal() as session:
        repository = TaskRepository(session)
        task = await repository.get(task_id)
        if task is None or task.transcription_status == TranscriptionStatus.DONE:
            return

    bot = Bot(token=get_settings().telegram_bot_token)
    try:
        audio = await download_file(bot, file_id)
        transcript = await transcribe(audio)
        if not transcript:
            raise ValueError("Gemini returned an empty transcript")

        async with SessionLocal() as session:
            task = await TaskRepository(session).get(task_id)
            if task is None:
                return
            await TaskRepository(session).update(
                task,
                title=transcript[:500],
                transcription_status=TranscriptionStatus.DONE,
                error_message=None,
            )
            await session.commit()
            task_event = TaskRead.model_validate(task)
            await publish_event(TaskEvent(type="task.updated", task=task_event))

        if task.telegram_chat_id is not None and task.telegram_message_id is not None:
            await bot.edit_message_text(
                chat_id=task.telegram_chat_id,
                message_id=task.telegram_message_id,
                text=f"✅ Task created: {transcript}",
            )
    except (TimeoutError, OSError) as error:
        if ctx.get("job_try", 1) < 3:
            delay = 5 * 2 ** (ctx.get("job_try", 1) - 1)
            logger.warning(
                "Transient transcription error for task %s; retrying in %ss: %s",
                task_id,
                delay,
                error,
            )
            raise Retry(defer=delay)
        await mark_failed(task_id)
        logger.error("Transcription failed after retries for task %s: %s", task_id, error)
    except APIError as error:
        if is_retryable_api_error(error) and ctx.get("job_try", 1) < 3:
            delay = 5 * 2 ** (ctx.get("job_try", 1) - 1)
            logger.warning(
                "Gemini returned %s for task %s; retrying in %ss",
                error.code,
                task_id,
                delay,
            )
            raise Retry(defer=delay)
        await mark_failed(task_id)
        logger.error("Gemini transcription failed for task %s: %s", task_id, error)
    except (ValueError, TelegramAPIError) as error:
        logger.exception("Transcription failed for task %s", task_id)
        await mark_failed(task_id)
    finally:
        await bot.session.close()
