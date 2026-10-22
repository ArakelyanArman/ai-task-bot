from typing import Literal

from pydantic import BaseModel

from app.schemas.tasks import TaskRead


EventType = Literal["task.created", "task.updated", "task.deleted"]


class TaskEvent(BaseModel):
    type: EventType
    task: TaskRead
