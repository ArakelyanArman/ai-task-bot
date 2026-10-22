import asyncio

from google import genai
from google.genai import types

from app.core.config import get_settings


def _transcript_text(response: object) -> str:
    text = getattr(response, "text", None)
    if text:
        return text.strip()

    parts = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            transcription = getattr(part, "audio_transcription", None)
            value = getattr(transcription, "text", None)
            if value:
                parts.append(value)
    return " ".join(parts).strip()


async def transcribe(
    audio_bytes: bytes, mime_type: str = "audio/ogg", timeout: float = 60
) -> str:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    response = await asyncio.wait_for(
        client.aio.models.generate_content(
            model=settings.gemini_transcribe_model,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            ],
            config=types.GenerateContentConfig(
                audio_transcription_config=types.AudioTranscriptionConfig(
                    mode="SMART",
                    language_codes=[],
                )
            ),
        ),
        timeout=timeout,
    )
    return _transcript_text(response)
