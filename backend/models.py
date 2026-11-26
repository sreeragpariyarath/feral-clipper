"""Database tables. One SQLite file (data/feral.db) shared by the API and the worker."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def now() -> datetime:
    """Local time with its timezone attached (the database layer rejects naive datetimes)."""
    return datetime.now().astimezone()


class Stream(SQLModel, table=True):
    """A downloaded stream. id is its folder name in data/vod, e.g. twitchvod-v2934513082."""
    id: str = Field(primary_key=True)
    source_url: str = ""
    title: str = ""
    channel: str = ""
    duration_s: float = 0.0
    video_file: str = ""
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Job(SQLModel, table=True):
    """A unit of work for the worker: download, monitor or render a stream."""
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str                                   # download | monitor | render
    source_url: str = ""
    stream_id: str = Field(default="", index=True)
    params: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="queued", index=True)   # queued | running | done | failed | cancelled
    current_step: str = ""
    error: str = ""
    cancel_requested: bool = False
    log_file: str = ""
    created_at: datetime = Field(default_factory=now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class JobStep(SQLModel, table=True):
    """One step of a job, with its own status and progress."""
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(index=True)
    idx: int
    name: str
    label: str
    status: str = "pending"                     # pending | running | done | failed | cancelled
    progress: Optional[float] = None            # 0..100, or None when the step has no percentage
    message: str = ""
    eta: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class Clip(SQLModel, table=True):
    """A rendered (or skipped) clip of a stream. Files live in data/vod/<stream>/clips/<clip_no>/."""
    __table_args__ = (UniqueConstraint("stream_id", "clip_no"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    stream_id: str = Field(index=True)
    clip_no: str
    status: str = "ready"                       # ready | skipped
    final_score: float = 0.0
    strong: bool = False
    title: str = ""
    caption: str = ""
    hook: str = ""
    reasons: str = ""
    judge_source: str = ""
    decision: str = "pending"                   # pending | approved | rejected
    deleted: bool = False                       # moved to clips_trash
    has_video: bool = False
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Campaign(SQLModel, table=True):
    """A clipping campaign: rules, logo, caption and payout."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    streamer: str = ""
    active: bool = True
    brief: str = ""
    caption: str = ""
    logo_path: str = ""
    payout_per_1k: float = 0.0
    platforms: list = Field(default_factory=list, sa_column=Column(JSON))
    ends_at: Optional[datetime] = None
    logo_on: bool = True              # draw the logo on every clip of this campaign
    logo_width: int = 420             # px on the 1080-wide video
    logo_y: int = 28                  # px from the top
    hashtags: str = ""                # extra tags added to every caption
    created_at: datetime = Field(default_factory=now)


class Post(SQLModel, table=True):
    """One clip posted to one platform. Views are typed in by hand (no platform logins)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    clip_id: int = Field(foreign_key="clip.id", index=True)
    campaign_id: Optional[int] = Field(default=None, foreign_key="campaign.id", index=True)
    platform: str                     # youtube | tiktok | instagram | other
    url: str = ""
    title: str = ""
    posted_at: datetime = Field(default_factory=now)
    views: int = 0
    views_at: Optional[datetime] = None


class Setting(SQLModel, table=True):
    """Editable settings. value is JSON-encoded text."""
    key: str = Field(primary_key=True)
    value: str = "null"


class Event(SQLModel, table=True):
    """Activity feed and live updates (sent to the browser over Server-Sent Events)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, index=True)
    kind: str                                   # job | step | progress | clip | info
    message: str = ""
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)
