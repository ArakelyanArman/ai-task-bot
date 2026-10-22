from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        query = select(User).where(User.telegram_id == telegram_id)
        return await self.session.scalar(query)

    async def get_or_create(
        self, telegram_id: int, username: str | None = None
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is not None:
            if username is not None and user.username != username:
                user.username = username
                await self.session.flush()
            return user

        user = User(telegram_id=telegram_id, username=username)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
