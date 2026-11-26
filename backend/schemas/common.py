from datetime import datetime
from typing import Any

from pydantic import BaseModel


class HealthOut(BaseModel):
    ok: bool
    keys: dict[str, bool]
    running_job: int | None
    queued_jobs: int
    disk: dict[str, float]
    low_disk: bool = False


class BackupOut(BaseModel):
    name: str
    size_mb: float
    created_at: datetime


class VideoDeletedOut(BaseModel):
    stream_id: str
    freed_gb: float


class SettingsOut(BaseModel):
    keys: dict[str, bool]
    values: dict[str, Any]


class SettingsIn(BaseModel):
    values: dict[str, Any]


class EventOut(BaseModel):
    id: int
    job_id: int | None
    kind: str
    message: str
    data: dict
    created_at: datetime
