from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["youtube", "tiktok", "instagram", "other"]


class PostIn(BaseModel):
    clip_id: int
    platform: Platform
    url: str = ""
    title: str = ""
    posted_at: datetime | None = None
    campaign_id: int | None = None


class PostPatch(BaseModel):
    views: int | None = Field(default=None, ge=0)
    url: str | None = None


class PostOut(BaseModel):
    id: int
    clip_id: int
    campaign_id: int | None
    campaign_name: str | None
    platform: str
    url: str
    title: str
    posted_at: datetime
    views: int
    views_at: datetime | None
    payout_usd: float | None
    clip_title: str
    thumb_url: str | None


class PlatformKit(BaseModel):
    platform: Platform
    title: str
    caption: str
    hashtags: list[str]
    limit_note: str


class PostingKitOut(BaseModel):
    clip_id: int
    campaign_name: str | None
    platforms: list[PlatformKit]
    best_times_local: list[str]
    best_times_note: str
    thumb_url: str | None
