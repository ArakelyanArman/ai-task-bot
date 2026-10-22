from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
            env_file=ROOT_DIR / ".env",
            extra="ignore",
        )

    # required settings
    database_url: str
    redis_url: str
    telegram_bot_token: str
    gemini_api_key: str

    # optional settings
    gemini_transcribe_model: str = "gemini-3.5-transcribe"
    max_audio_duration: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
