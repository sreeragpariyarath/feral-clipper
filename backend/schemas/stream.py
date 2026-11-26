from datetime import datetime

from pydantic import BaseModel


class StreamOut(BaseModel):
    id: str
    title: str
    channel: str
    source_url: str
    duration_s: float
    video_file: str
    size_gb: float
    clips: int
    ready: int
    approved: int
    updated_at: datetime


class MonitorSheetOut(BaseModel):
    exists: bool
    picks: list[dict] = []
    window: int | None = None
    step: int | None = None
