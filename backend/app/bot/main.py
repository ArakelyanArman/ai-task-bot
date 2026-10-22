import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.enums import TaskSource, TranscriptionStatus
from app.repositories.tasks import TaskRepository
from app.repositories.users import UserRepository
from app.worker.queue import enqueue_transcription


logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    await message.answer(
        "Welcome! Send me a message and I will save it as a task."
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer("Send a text or voice message to create a task.")


@router.message(F.voice)
async def voice_handler(message: Message) -> None:
    if message.from_user is None or message.voice is None:
        return

    settings = get_settings()
    if (
        message.voice.duration > settings.max_audio_duration
        or (
            message.voice.file_size is not None
            and message.voice.file_size > settings.max_audio_size
        )
    ):
        await message.answer(
            "Please keep voice messages under "
            f"{settings.max_audio_duration} seconds and "
            f"{settings.max_audio_size // (1024 * 1024)} MB."
        )
        return

    acknowledgement = await message.answer("🎙 Transcribing…")
    async with SessionLocal() as session:
        try:
            user = await UserRepository(session).get_or_create(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
            )
            task = await TaskRepository(session).create(
                user_id=user.id,
                title="Transcribing voice message…",
                source=TaskSource.VOICE,
                transcription_status=TranscriptionStatus.PROCESSING,
                telegram_chat_id=message.chat.id,
                telegram_message_id=acknowledgement.message_id,
            )
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to create voice task from message %s", message.message_id)
            await acknowledgement.edit_text("I couldn't save that task. Please try again.")
            return

    try:
        await enqueue_transcription(task.id, message.voice.file_id)
    except (OSError, RuntimeError):
        logger.exception("Failed to enqueue transcription for task %s", task.id)
        async with SessionLocal() as session:
            failed_task = await TaskRepository(session).get(task.id)
            if failed_task is not None:
                await TaskRepository(session).update(
                    failed_task,
                    transcription_status=TranscriptionStatus.FAILED,
                    error_message="Couldn't start transcription",
                )
                await session.commit()
        await acknowledgement.edit_text("Couldn't start transcription. Please try again.")


@router.message(F.text)
async def text_handler(message: Message) -> None:
    if message.from_user is None or message.text is None:
        return

    async with SessionLocal() as session:
        try:
            user = await UserRepository(session).get_or_create(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
            )
            task = await TaskRepository(session).create(
                user_id=user.id,
                title=message.text[:500],
                source=TaskSource.TEXT,
            )
            await session.commit()
        except (SQLAlchemyError, OSError):
            await session.rollback()
            logger.exception("Failed to create task from message %s", message.message_id)
            await message.answer("I couldn't save that task. Please try again.")
            return

    await message.answer(f"✅ Task created: {task.title}")


@router.message()
async def unsupported_message_handler(message: Message) -> None:
    await message.answer("Please send a text message. Voice messages will be supported soon.")


async def run() -> None:
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import asyncio

    asyncio.run(run())
