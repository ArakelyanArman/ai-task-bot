import enum


class TaskStatus(enum.StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskSource(enum.StrEnum):
    TEXT = "text"
    VOICE = "voice"


class TranscriptionStatus(enum.StrEnum):
    NONE = "none"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
