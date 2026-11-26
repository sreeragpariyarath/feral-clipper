from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["pending", "approved", "rejected"]


class ClipOut(BaseModel):
    id: int
    stream_id: str
    clip_no: str
    status: str
    final_score: float
    strong: bool
    title: str
    caption: str
    hook: str
    reasons: str
    judge_source: str
    decision: Decision
    deleted: bool
    has_video: bool
    video_url: str | None
    thumb_url: str | None
    updated_at: datetime


class ClipPatch(BaseModel):
    decision: Decision | None = None
    title: str | None = Field(default=None, max_length=200)
    caption: str | None = Field(default=None, max_length=2200)
