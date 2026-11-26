"""Clips: list, review (approve / reject / edit text), trash and restore."""
import json
import shutil
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from ..config import VOD_DIR
from ..events import emit
from ..models import Clip, now
from ..schemas import ClipOut, ClipPatch
from .errors import Conflict, NotFound


def folder_of(clip: Clip) -> Path:
    return VOD_DIR / clip.stream_id / ("clips_trash" if clip.deleted else "clips") / clip.clip_no


def to_out(c: Clip) -> ClipOut:
    playable = c.has_video and not c.deleted
    base = f"/media/{c.stream_id}/{c.clip_no}"
    return ClipOut(
        id=c.id, stream_id=c.stream_id, clip_no=c.clip_no, status=c.status, final_score=c.final_score,
        strong=c.strong, title=c.title, caption=c.caption, hook=c.hook, reasons=c.reasons,
        judge_source=c.judge_source, decision=c.decision, deleted=c.deleted, has_video=c.has_video,
        video_url=f"{base}/clip.mp4" if playable else None,
        thumb_url=f"{base}/thumb.jpg" if playable else None, updated_at=c.updated_at)


def query(session: Session, stream_id: str | None = None, decision: str | None = None,
          deleted: bool = False) -> list[Clip]:
    q = select(Clip).where(Clip.deleted == deleted)  # noqa: E712
    if stream_id:
        q = q.where(Clip.stream_id == stream_id)
    if decision:
        q = q.where(Clip.decision == decision)
    return list(session.exec(q.order_by(Clip.final_score.desc())))


def get(session: Session, clip_id: int) -> Clip:
    clip = session.get(Clip, clip_id)
    if clip is None:
        raise NotFound("clip not found")
    return clip


def by_number(session: Session, stream_id: str, clip_no: str) -> Clip:
    clip = session.exec(select(Clip).where(Clip.stream_id == stream_id, Clip.clip_no == clip_no,
                                           Clip.deleted == False)).first()  # noqa: E712
    if clip is None:
        raise NotFound("clip not found")
    return clip


def review(session: Session, clip: Clip, patch: ClipPatch) -> Clip:
    if patch.decision is not None:
        clip.decision = patch.decision
    if patch.title is not None:
        clip.title = patch.title
    if patch.caption is not None:
        clip.caption = patch.caption
    clip.updated_at = now()
    session.add(clip)
    folder = folder_of(clip)
    if folder.is_dir():          # keep review.json next to the clip for the command-line tools
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
    clip.deleted, clip.updated_at = True, now()
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
    dest = VOD_DIR / clip.stream_id / "clips" / clip.clip_no
    if dest.exists():
        raise Conflict("a clip with this number already exists")
    trash_dir = VOD_DIR / clip.stream_id / "clips_trash"
    candidates = sorted(trash_dir.glob(f"{clip.clip_no}*")) if trash_dir.exists() else []
    if candidates:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(candidates[-1]), str(dest))
    clip.deleted, clip.updated_at = False, now()
    session.add(clip)
    emit(session, "clip", f"Clip {clip.stream_id}/{clip.clip_no} restored", data={"clip_id": clip.id}, commit=False)
    session.commit()
    session.refresh(clip)
    return clip
