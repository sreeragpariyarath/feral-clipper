"""Bring the files the pipeline writes (session.json, clips/*/status.json, judge.json, review.json)
into the database. Safe to run any number of times: rows are updated, never duplicated."""
import json
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from .config import VOD_DIR
from .models import Clip, Stream, now


def _read(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _title_from_post(clip_dir: Path) -> str:
    """Title line from post.txt (written when a campaign caption is set). Empty when the title is blank."""
    p = clip_dir / "post.txt"
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("TITLE"):
            for nxt in lines[i + 1:]:
                text = nxt.strip()
                if not text:
                    continue
                if text.upper().startswith("CAPTION") or text.endswith(":"):
                    return ""
                return text
    return ""


def _duration(video: Path) -> float:
    """Length in seconds, or 0 when ffprobe cannot read the file (half-downloaded, missing)."""
    import subprocess
    from clipper.common import duration_of
    try:
        return float(duration_of(video))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return 0.0


def sync_stream(session: Session, stream_id: str, source_url: str = "") -> Optional[Stream]:
    folder = VOD_DIR / stream_id
    meta = _read(folder / "session.json", {}) or {}
    if not folder.is_dir():
        return None
    stream = session.get(Stream, stream_id) or Stream(id=stream_id)
    stream.title = meta.get("title") or stream.title or stream_id
    stream.channel = meta.get("channel") or stream.channel
    stream.source_url = meta.get("url") or source_url or stream.source_url
    video_name = meta.get("file") or ""
    if video_name and (folder / video_name).exists():
        if stream.video_file != video_name or not stream.duration_s:
            stream.duration_s = _duration(folder / video_name)
        stream.video_file = video_name
    else:
        stream.video_file = ""                       # deleted to free space (clips are kept)
    stream.updated_at = now()
    session.add(stream)
    sync_clips(session, stream_id, commit=False)
    session.commit()
    return stream


def _clip_row(session: Session, stream_id: str, clip_no: str) -> Clip:
    row = session.exec(select(Clip).where(Clip.stream_id == stream_id, Clip.clip_no == clip_no)).first()
    return row or Clip(stream_id=stream_id, clip_no=clip_no)


def sync_clips(session: Session, stream_id: str, commit: bool = True) -> int:
    folder = VOD_DIR / stream_id
    count = 0
    for base, deleted in ((folder / "clips", False), (folder / "clips_trash", True)):
        if not base.exists():
            continue
        for clip_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            status = _read(clip_dir / "status.json")
            if status is None:
                continue
            clip_no = clip_dir.name.split("_")[0]   # trash copies may carry a timestamp suffix
            judge = _read(clip_dir / "judge.json", {}) or {}
            review = _read(clip_dir / "review.json", {}) or {}
            row = _clip_row(session, stream_id, clip_no)
            row.status = status.get("status", "ready")
            row.final_score = float(status.get("final") or judge.get("final_score") or 0)
            row.strong = bool(status.get("strong"))
            row.title = review.get("title") or row.title or judge.get("title") or _title_from_post(clip_dir) or ""
            row.caption = review.get("caption") or row.caption or ""
            row.hook = judge.get("hook_text") or ""
            row.reasons = judge.get("reasons") or ""
            row.judge_source = judge.get("source") or ""
            row.decision = review.get("decision") or row.decision or "pending"
            row.has_video = (clip_dir / "clip.mp4").exists()
            row.deleted = deleted
            row.updated_at = now()
            session.add(row)
            count += 1
    if commit:
        session.commit()
    return count


def sync_all(session: Session) -> int:
    if not VOD_DIR.exists():
        return 0
    n = 0
    for d in sorted(VOD_DIR.iterdir()):
        if d.is_dir() and (d / "session.json").exists():
            sync_stream(session, d.name)
            n += 1
    return n
