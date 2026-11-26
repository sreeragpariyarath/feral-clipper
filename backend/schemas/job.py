from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

JobKind = Literal["download", "monitor", "render"]
JobStatus = Literal["creating", "queued", "running", "done", "failed", "cancelled"]


class JobCreate(BaseModel):
    kind: JobKind = "render"
    url: str = ""
    path: str = ""
    top: int = Field(default=10, ge=1, le=30)
    campaign_id: int | None = None

    @model_validator(mode="after")
    def one_source(self) -> "JobCreate":
        if bool(self.url.strip()) == bool(self.path.strip()):
            raise ValueError("give either a Twitch VOD link or a video file path")
        return self


class ProgressOut(BaseModel):
    percent: float | None
    text: str
    eta: str


class StepOut(BaseModel):
    idx: int
    name: str
    label: str
    status: str
    progress: float | None
    message: str
    eta: str
    started_at: datetime | None
    finished_at: datetime | None


class JobOut(BaseModel):
    id: int
    kind: str
    source_url: str
    stream_id: str
    params: dict
    results: dict
    tokens: dict
    status: JobStatus
    current_step: str
    error: str
    error_hint: str = ""
    cancel_requested: bool
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    progress: ProgressOut
    steps: list[StepOut]
    log: list[str] | None = None
