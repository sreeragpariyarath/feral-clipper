from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    streamer: str = ""
    active: bool = True
    brief: str = ""
    caption: str = ""
    logo_path: str = ""
    payout_per_1k: float = Field(default=0.0, ge=0)
    platforms: list[str] = []
    ends_at: datetime | None = None
    logo_on: bool = True
    logo_width: int = Field(default=420, ge=100, le=1080)
    logo_y: int = Field(default=28, ge=0, le=1800)
    hashtags: str = ""

    @field_validator("ends_at")
    @classmethod
    def local_time(cls, v: datetime | None) -> datetime | None:
        """Dates without a timezone are treated as local time."""
        return v.astimezone() if v is not None and v.tzinfo is None else v


class CampaignOut(CampaignIn):
    id: int
    created_at: datetime
