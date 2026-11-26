"""Posting kit: ready-to-paste title, caption and tags per platform, and when to post.

Built from the judge's notes and the campaign's caption. No API call, so it costs nothing.
"""
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session

from ..models import Campaign, Clip
from ..schemas import PlatformKit, PostingKitOut
from . import clips as clips_svc
from .posts import campaign_of_clip

# About 80 % of viewers are in the USA and Canada, so peak times are set in US Eastern time;
# the page shows them in the browser's own time zone. Short-video traffic peaks at these hours.
AUDIENCE_TZ = ZoneInfo("America/New_York")
PEAK_HOURS_ET = {12: "lunch break", 16: "after school / work", 19: "evening, the biggest window"}

BASE_TAGS = ["GTA6", "GTAVI", "GTA", "Gaming", "Shorts"]
CATEGORY_TAGS = {"funny": ["Funny", "GamingFunny"], "hype": ["Hype"], "fail": ["Fail"],
                 "clutch": ["Clutch"], "rage": ["Rage"], "wholesome": ["Wholesome"]}
YT_TITLE_MAX = 100
CAPTION_MAX = 2200


def _tags_in(text: str) -> list[str]:
    return [t.lstrip("#") for t in re.findall(r"#\w+", text)]


def clean_title(title: str) -> str:
    """Never name the wrong game; the judge is told the same."""
    return re.sub(r"\bGTA ?(V|5|Five)\b", "GTA 6", title, flags=re.I).strip().strip('"')


def fit(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def best_times(now: datetime | None = None, count: int = 3) -> list[datetime]:
    """The next peak slots in US Eastern time, soonest first (at least 20 minutes from now)."""
    now = (now or datetime.now(AUDIENCE_TZ)).astimezone(AUDIENCE_TZ)
    slots = []
    for day in range(3):
        d = (now + timedelta(days=day)).date()
        for hour in sorted(PEAK_HOURS_ET):
            t = datetime(d.year, d.month, d.day, hour, tzinfo=AUDIENCE_TZ)
            if t > now + timedelta(minutes=20):
                slots.append(t)
    return slots[:count]


def tags_for(category: str, required: str) -> list[str]:
    """Campaign tags first (they are required), then the category and base tags, no duplicates."""
    out: list[str] = []
    for t in _tags_in(required) + CATEGORY_TAGS.get(category, []) + BASE_TAGS:
        if t.lower() not in (x.lower() for x in out):
            out.append(t)
    return out


def build(session: Session, clip: Clip, now: datetime | None = None) -> PostingKitOut:
    folder = clips_svc.folder_of(clip)
    judge = json.loads((folder / "judge.json").read_text(encoding="utf-8")) if (folder / "judge.json").exists() else {}
    cid = campaign_of_clip(session, clip)
    camp = session.get(Campaign, cid) if cid else None

    title = clean_title(clip.title or judge.get("title") or judge.get("hook_text") or f"Clip {clip.clip_no}")
    hook = (judge.get("hook_text") or "").strip()
    required = " ".join(p for p in ((camp.caption.strip(), camp.hashtags.strip()) if camp else ()) if p)
    tags = tags_for(judge.get("category", ""), required)

    def caption(n_tags: int) -> str:
        parts = [title]
        if hook and hook.lower() not in title.lower():
            parts.append(hook)
        if required:
            parts.append(required)                  # the campaign's text, word for word
        extra = [t for t in tags[:n_tags] if t.lower() not in required.lower()]
        parts.append(" ".join("#" + t for t in extra))
        return "\n\n".join(p for p in parts if p.strip())

    kits = [
        PlatformKit(platform="youtube", title=fit(title, YT_TITLE_MAX), caption=caption(6), hashtags=tags[:6],
                    limit_note="Title max 100 characters; #Shorts helps the Shorts shelf."),
        PlatformKit(platform="tiktok", title="", caption=fit(caption(5), CAPTION_MAX), hashtags=tags[:5],
                    limit_note="One caption, max 2,200 characters; 3-5 tags work best."),
        PlatformKit(platform="instagram", title="", caption=fit(caption(10), CAPTION_MAX), hashtags=tags[:10],
                    limit_note="Reels caption, max 2,200 characters and 30 hashtags."),
    ]
    times = best_times(now)
    return PostingKitOut(
        clip_id=clip.id, campaign_name=camp.name if camp else None, platforms=kits,
        best_times_local=[t.isoformat() for t in times],
        best_times_note="Peak hours for a USA / Canada audience: "
                        + ", ".join(f"{h % 12 or 12} {'PM' if h >= 12 else 'AM'} ET ({PEAK_HOURS_ET[h]})" for h in sorted(PEAK_HOURS_ET)),
        thumb_url=f"/media/{clip.stream_id}/{clip.clip_no}/thumb.jpg" if clip.has_video and not clip.deleted else None)
