import asyncio
from io import BytesIO

from aiogram import Bot


async def download_file(bot: Bot, file_id: str, timeout: float = 30) -> bytes:
    telegram_file = await asyncio.wait_for(bot.get_file(file_id), timeout=timeout)
    if telegram_file.file_path is None:
        raise ValueError("Telegram did not return an audio file path")

    output = BytesIO()
    await asyncio.wait_for(
        bot.download_file(telegram_file.file_path, output),
        timeout=timeout,
    )
    return output.getvalue()
