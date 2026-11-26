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


class Word(BaseModel):
    w: str
    s: float
    e: float


class ClipDetailOut(BaseModel):
    """Everything the clip page shows besides the video: judge notes, transcript and the score sheet row."""
    clip: ClipOut
    judge: dict
    words: list[Word]
    score: dict | None
    face_box: list[float] | dict | None
    strip_url: str | None
