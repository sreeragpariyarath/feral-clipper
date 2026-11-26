"""Streams: list them with their clip counts and disk size, and read their score sheet."""
import json
from pathlib import Path

from sqlmodel import Session, select

from ..config import VOD_DIR
from ..events import emit
from ..models import Clip, Job, Stream
from ..schemas import MonitorSheetOut, StreamOut, VideoDeletedOut
from .errors import Conflict, InvalidInput, NotFound


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


def delete_video(session: Session, stream: Stream) -> VideoDeletedOut:
    """Permanently delete the downloaded source video of a stream to free disk space.

    Clips, transcript, audio and score sheets stay. Only a video inside the stream's own folder is
    deleted: a local file the user pointed a job at is never touched. Refused while a job uses the stream.
    """
    busy = session.exec(select(Job).where(Job.stream_id == stream.id, Job.status.in_(("queued", "running")))).first()
    if busy:
        raise Conflict(f"job {busy.id} is using this stream; wait for it or cancel it first")
    folder = (VOD_DIR / stream.id).resolve()
    meta = json.loads((folder / "session.json").read_text(encoding="utf-8")) if (folder / "session.json").exists() else {}
    name = meta.get("file") or stream.video_file
    if not name:
        raise NotFound("this stream has no video file")
    video = (folder / name).resolve()
    if video.parent != folder:
        raise InvalidInput("this stream uses your own video file outside the app's folder; delete it yourself if you want")
    if not video.is_file():
        raise NotFound("the video is already gone")
    size = video.stat().st_size
    video.unlink()
    for part in folder.glob(video.name + ".part*"):                 # leftovers of an unfinished download
        part.unlink(missing_ok=True)
    stream.video_file = ""
    session.add(stream)
    emit(session, "info", f"Deleted the video of {stream.id} ({size / 1e9:.1f} GB freed)", commit=False)
    session.commit()
    return VideoDeletedOut(stream_id=stream.id, freed_gb=round(size / 1e9, 2))


def monitor_sheet(stream_id: str) -> MonitorSheetOut:
    path = VOD_DIR / stream_id / "monitor.json"
    if not path.exists():
        return MonitorSheetOut(exists=False)
    data = json.loads(path.read_text(encoding="utf-8"))
    return MonitorSheetOut(exists=True, picks=data.get("picks", []), window=data.get("window"),
                           step=data.get("step"))
