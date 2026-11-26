"""Streams: list them with their clip counts and disk size, and read their score sheet."""
import json
from pathlib import Path

from sqlmodel import Session, select

from ..config import VOD_DIR
from ..models import Clip, Stream
from ..schemas import MonitorSheetOut, StreamOut
from .errors import NotFound


def _folder_size(folder: Path) -> int:
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder.exists() else 0


def to_out(session: Session, s: Stream) -> StreamOut:
    clips = list(session.exec(select(Clip).where(Clip.stream_id == s.id, Clip.deleted == False)))  # noqa: E712
    return StreamOut(
        id=s.id, title=s.title, channel=s.channel, source_url=s.source_url, duration_s=s.duration_s,
        video_file=s.video_file, size_gb=round(_folder_size(VOD_DIR / s.id) / 1e9, 2),
        clips=len(clips), ready=sum(c.status == "ready" for c in clips),
        approved=sum(c.decision == "approved" for c in clips), updated_at=s.updated_at)


def all_streams(session: Session) -> list[Stream]:
    return list(session.exec(select(Stream).order_by(Stream.updated_at.desc())))


def get(session: Session, stream_id: str) -> Stream:
    stream = session.get(Stream, stream_id)
    if stream is None:
        raise NotFound("stream not found")
    return stream


def monitor_sheet(stream_id: str) -> MonitorSheetOut:
    path = VOD_DIR / stream_id / "monitor.json"
    if not path.exists():
        return MonitorSheetOut(exists=False)
    data = json.loads(path.read_text(encoding="utf-8"))
    return MonitorSheetOut(exists=True, picks=data.get("picks", []), window=data.get("window"),
                           step=data.get("step"))
