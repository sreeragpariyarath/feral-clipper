"""Clip actions shared by the v1 API and the older routes the current frontend uses."""
import json
import shutil
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from .config import VOD_DIR
from .events import emit
from .models import Clip, now

DECISIONS = {"pending", "approved", "rejected"}


def clip_dir(clip: Clip) -> Path:
    base = "clips_trash" if clip.deleted else "clips"
    return VOD_DIR / clip.stream_id / base / clip.clip_no


def update_review(session: Session, clip: Clip, decision=None, title=None, caption=None) -> Clip:
    if decision is not None:
        if decision not in DECISIONS:
            raise ValueError("decision must be pending, approved or rejected")
        clip.decision = decision
    if title is not None:
        clip.title = str(title)[:200]
    if caption is not None:
        clip.caption = str(caption)[:2200]
    clip.updated_at = now()
    session.add(clip)
    # keep review.json next to the clip, so the command-line tools see the same decision
    folder = clip_dir(clip)
    if folder.is_dir():
        (folder / "review.json").write_text(json.dumps(
            {"decision": clip.decision, "title": clip.title, "caption": clip.caption},
            indent=2, ensure_ascii=False), encoding="utf-8")
    emit(session, "clip", f"Clip {clip.stream_id}/{clip.clip_no} marked {clip.decision}",
         data={"clip_id": clip.id, "decision": clip.decision}, commit=False)
    session.commit()
    session.refresh(clip)
    return clip


def trash(session: Session, clip: Clip) -> Clip:
    """Move the clip folder into clips_trash. Nothing is deleted permanently."""
    if clip.deleted:
        return clip
    src = VOD_DIR / clip.stream_id / "clips" / clip.clip_no
    trash_dir = VOD_DIR / clip.stream_id / "clips_trash"
    if src.is_dir():
        trash_dir.mkdir(parents=True, exist_ok=True)
        dest = trash_dir / clip.clip_no
        if dest.exists():
            dest = trash_dir / f"{clip.clip_no}_{datetime.now():%Y%m%d-%H%M%S}"
        shutil.move(str(src), str(dest))
    clip.deleted = True
    clip.updated_at = now()
    session.add(clip)
    emit(session, "clip", f"Clip {clip.stream_id}/{clip.clip_no} moved to trash",
         data={"clip_id": clip.id}, commit=False)
    session.commit()
    session.refresh(clip)
    return clip


def restore(session: Session, clip: Clip) -> Clip:
    """Move the clip folder back from clips_trash."""
    if not clip.deleted:
        return clip
    trash_dir = VOD_DIR / clip.stream_id / "clips_trash"
    dest = VOD_DIR / clip.stream_id / "clips" / clip.clip_no
    if dest.exists():
        raise ValueError("a clip with this number already exists in clips")
    candidates = sorted(trash_dir.glob(f"{clip.clip_no}*")) if trash_dir.exists() else []
    if candidates:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(candidates[-1]), str(dest))
    clip.deleted = False
    clip.updated_at = now()
    session.add(clip)
    emit(session, "clip", f"Clip {clip.stream_id}/{clip.clip_no} restored", data={"clip_id": clip.id}, commit=False)
    session.commit()
    session.refresh(clip)
    return clip
