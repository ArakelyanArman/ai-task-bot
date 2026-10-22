from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.models.enums import TaskStatus
from app.models.user import User
from app.repositories.tasks import TaskRepository
from app.schemas import TaskCreate, TaskRead, TaskUpdate


router = APIRouter(prefix="/tasks", tags=["tasks"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    session: SessionDependency, status: TaskStatus | None = None
) -> list[TaskRead]:
    tasks = await TaskRepository(session).list(status)
    return [TaskRead.model_validate(task) for task in tasks]


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate, session: SessionDependency
) -> TaskRead:
    user = await session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    task = await TaskRepository(session).create(**payload.model_dump())
    await session.commit()
    return TaskRead.model_validate(task)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int, payload: TaskUpdate, session: SessionDependency
) -> TaskRead:
    repository = TaskRepository(session)
    task = await repository.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    task = await repository.update(task, **payload.model_dump())
    await session.commit()
    return TaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, session: SessionDependency) -> None:
    repository = TaskRepository(session)
    task = await repository.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    await repository.delete(task)
    await session.commit()
