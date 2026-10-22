from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import TaskSource, TaskStatus, TranscriptionStatus


class TaskCreate(BaseModel):
    user_id: int
    title: str
    description: str | None = None
    source: TaskSource = TaskSource.TEXT


class TaskUpdate(BaseModel):
    status: TaskStatus


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    description: str | None
    status: TaskStatus
    source: TaskSource
    transcription_status: TranscriptionStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime
