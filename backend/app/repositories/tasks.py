from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task import Task


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **values: object) -> Task:
        task = Task(**values)
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def list(
        self, status: TaskStatus | None = None
    ) -> list[Task]:
        query: Select[tuple[Task]] = select(Task).order_by(Task.created_at.desc())
        if status is not None:
            query = query.where(Task.status == status)
        result = await self.session.scalars(query)
        return list(result.all())

    async def get(self, task_id: int) -> Task | None:
        return await self.session.get(Task, task_id)

    async def update(self, task: Task, **values: object) -> Task:
        for field, value in values.items():
            setattr(task, field, value)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def delete(self, task: Task) -> None:
        await self.session.delete(task)
        await self.session.flush()
