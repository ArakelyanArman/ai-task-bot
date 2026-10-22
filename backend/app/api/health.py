from fastapi import APIRouter, HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import SessionLocal


router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Database is unavailable") from error

    redis = Redis.from_url(get_settings().redis_url)
    try:
        await redis.ping()
    except RedisError as error:
        raise HTTPException(status_code=503, detail="Redis is unavailable") from error
    finally:
        await redis.aclose()

    return {"status": "ok"}
