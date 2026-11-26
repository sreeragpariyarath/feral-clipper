"""Main API: /api/v1/..."""
import asyncio
import json
import shutil
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, func, select

from .. import clips_service, jobs_service
from ..config import ROOT, VOD_DIR, key_status
from ..db import engine, get_session
from ..events import emit
from ..importer import sync_all
from ..models import Campaign, Clip, Event, Job, Setting, Stream

router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------- health and settings
@router.get("/health")
def health(session: Session = Depends(get_session)):
    running = jobs_service.latest_running(session)
    queued = session.exec(select(func.count()).select_from(Job).where(Job.status == "queued")).one()
    disk = shutil.disk_usage(ROOT)
    return {"ok": True, "keys": key_status(), "running_job": running.id if running else None,
            "queued_jobs": queued, "disk": {"free_gb": round(disk.free / 1e9, 1), "total_gb": round(disk.total / 1e9, 1)}}


@router.get("/settings")
def get_settings(session: Session = Depends(get_session)):
    rows = session.exec(select(Setting)).all()
    return {"keys": key_status(), "values": {r.key: json.loads(r.value) for r in rows}}


class SettingsIn(BaseModel):
    values: dict


@router.put("/settings")
def put_settings(body: SettingsIn, session: Session = Depends(get_session)):
    for key, value in body.values.items():
        if not key or len(key) > 80:
            raise HTTPException(400, "bad setting key")
        row = session.get(Setting, key) or Setting(key=key)
        row.value = json.dumps(value)
        session.add(row)
    session.commit()
    return get_settings(session)


# ---------------------------------------------------------------- streams
def _stream_dict(session: Session, s: Stream) -> dict:
    clips = session.exec(select(Clip).where(Clip.stream_id == s.id, Clip.deleted == False)).all()  # noqa: E712
    folder = VOD_DIR / s.id
    size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder.exists() else 0
    return {"id": s.id, "title": s.title, "channel": s.channel, "source_url": s.source_url,
            "duration_s": s.duration_s, "video_file": s.video_file, "size_gb": round(size / 1e9, 2),
            "clips": len(clips), "ready": sum(1 for c in clips if c.status == "ready"),
            "approved": sum(1 for c in clips if c.decision == "approved"),
            "updated_at": s.updated_at.isoformat(timespec="seconds")}


@router.get("/streams")
def list_streams(session: Session = Depends(get_session)):
    rows = session.exec(select(Stream).order_by(Stream.updated_at.desc())).all()
    return [_stream_dict(session, s) for s in rows]


@router.get("/streams/{stream_id}")
def get_stream(stream_id: str, session: Session = Depends(get_session)):
    s = session.get(Stream, stream_id)
    if not s:
        raise HTTPException(404, "stream not found")
    return _stream_dict(session, s)


@router.get("/streams/{stream_id}/monitor")
def stream_monitor(stream_id: str, session: Session = Depends(get_session)):
    if not session.get(Stream, stream_id):
        raise HTTPException(404, "stream not found")
    path = VOD_DIR / stream_id / "monitor.json"
    if not path.exists():
        return {"exists": False, "picks": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"exists": True, **data}


@router.post("/sync")
def sync(session: Session = Depends(get_session)):
    """Re-read every stream folder into the database."""
    return {"streams": sync_all(session)}


# ---------------------------------------------------------------- clips
def clip_dict(c: Clip) -> dict:
    return {"id": c.id, "stream_id": c.stream_id, "clip_no": c.clip_no, "status": c.status,
            "final_score": c.final_score, "strong": c.strong, "title": c.title, "caption": c.caption,
            "hook": c.hook, "reasons": c.reasons, "judge_source": c.judge_source, "decision": c.decision,
            "deleted": c.deleted, "has_video": c.has_video,
            "video_url": f"/media/{c.stream_id}/{c.clip_no}/clip.mp4" if c.has_video and not c.deleted else None,
            "thumb_url": f"/media/{c.stream_id}/{c.clip_no}/thumb.jpg" if c.has_video and not c.deleted else None,
            "updated_at": c.updated_at.isoformat(timespec="seconds")}


@router.get("/clips")
def list_clips(stream_id: Optional[str] = None, decision: Optional[str] = None, deleted: bool = False,
               session: Session = Depends(get_session)):
    q = select(Clip).where(Clip.deleted == deleted)
    if stream_id:
        q = q.where(Clip.stream_id == stream_id)
    if decision:
        q = q.where(Clip.decision == decision)
    rows = session.exec(q.order_by(Clip.final_score.desc())).all()
    return [clip_dict(c) for c in rows]


class ClipPatch(BaseModel):
    decision: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None


def _clip_or_404(session: Session, clip_id: int) -> Clip:
    c = session.get(Clip, clip_id)
    if not c:
        raise HTTPException(404, "clip not found")
    return c


@router.get("/clips/{clip_id}")
def get_clip(clip_id: int, session: Session = Depends(get_session)):
    return clip_dict(_clip_or_404(session, clip_id))


@router.patch("/clips/{clip_id}")
def patch_clip(clip_id: int, body: ClipPatch, session: Session = Depends(get_session)):
    try:
        c = clips_service.update_review(session, _clip_or_404(session, clip_id), body.decision, body.title, body.caption)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return clip_dict(c)


@router.delete("/clips/{clip_id}")
def delete_clip(clip_id: int, session: Session = Depends(get_session)):
    """Moves the clip to the trash folder; nothing is removed permanently."""
    return clip_dict(clips_service.trash(session, _clip_or_404(session, clip_id)))


@router.post("/clips/{clip_id}/restore")
def restore_clip(clip_id: int, session: Session = Depends(get_session)):
    try:
        return clip_dict(clips_service.restore(session, _clip_or_404(session, clip_id)))
    except ValueError as e:
        raise HTTPException(409, str(e))


# ---------------------------------------------------------------- jobs
class JobIn(BaseModel):
    kind: str = "render"
    url: str = ""
    path: str = ""
    top: int = 10


def _job_or_404(session: Session, job_id: int) -> Job:
    j = session.get(Job, job_id)
    if not j:
        raise HTTPException(404, "job not found")
    return j


@router.post("/jobs", status_code=202)
def create_job(body: JobIn, session: Session = Depends(get_session)):
    try:
        job = jobs_service.create_job(session, body.kind, body.url, body.top, key_status()["anthropic"], body.path)
    except jobs_service.JobError as e:
        raise HTTPException(400, str(e))
    return jobs_service.job_dict(session, job)


@router.get("/jobs")
def list_jobs(limit: int = 30, session: Session = Depends(get_session)):
    rows = session.exec(select(Job).order_by(Job.id.desc()).limit(max(1, min(limit, 200)))).all()
    return [jobs_service.job_dict(session, j) for j in rows]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)):
    return jobs_service.job_dict(session, _job_or_404(session, job_id), with_log=True)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int, session: Session = Depends(get_session)):
    return jobs_service.job_dict(session, jobs_service.request_cancel(session, _job_or_404(session, job_id)))


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int, session: Session = Depends(get_session)):
    try:
        return jobs_service.job_dict(session, jobs_service.retry(session, _job_or_404(session, job_id)))
    except jobs_service.JobError as e:
        raise HTTPException(409, str(e))


# ---------------------------------------------------------------- campaigns
class CampaignIn(BaseModel):
    name: str
    streamer: str = ""
    active: bool = True
    brief: str = ""
    caption: str = ""
    logo_path: str = ""
    payout_per_1k: float = 0.0
    platforms: list = []
    ends_at: Optional[datetime] = None


def _aware(values: dict) -> dict:
    """Dates from the browser may come without a timezone; treat them as local time."""
    if values.get("ends_at") is not None and values["ends_at"].tzinfo is None:
        values["ends_at"] = values["ends_at"].astimezone()
    return values


def _campaign_dict(c: Campaign) -> dict:
    return {**c.model_dump(), "created_at": c.created_at.isoformat(timespec="seconds"),
            "ends_at": c.ends_at.isoformat(timespec="seconds") if c.ends_at else None}


@router.get("/campaigns")
def list_campaigns(session: Session = Depends(get_session)):
    return [_campaign_dict(c) for c in session.exec(select(Campaign).order_by(Campaign.id.desc())).all()]


@router.post("/campaigns", status_code=201)
def create_campaign(body: CampaignIn, session: Session = Depends(get_session)):
    c = Campaign(**_aware(body.model_dump()))
    session.add(c)
    session.commit()
    session.refresh(c)
    return _campaign_dict(c)


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, body: CampaignIn, session: Session = Depends(get_session)):
    c = session.get(Campaign, campaign_id)
    if not c:
        raise HTTPException(404, "campaign not found")
    for k, v in _aware(body.model_dump()).items():
        setattr(c, k, v)
    session.add(c)
    session.commit()
    session.refresh(c)
    return _campaign_dict(c)


@router.delete("/campaigns/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: int, session: Session = Depends(get_session)):
    c = session.get(Campaign, campaign_id)
    if c:
        session.delete(c)
        session.commit()


# ---------------------------------------------------------------- activity and live events
def _event_dict(e: Event) -> dict:
    return {"id": e.id, "job_id": e.job_id, "kind": e.kind, "message": e.message, "data": e.data,
            "created_at": e.created_at.isoformat(timespec="seconds")}


@router.get("/activity")
def activity(limit: int = 50, session: Session = Depends(get_session)):
    rows = session.exec(select(Event).order_by(Event.id.desc()).limit(max(1, min(limit, 500)))).all()
    return [_event_dict(e) for e in rows]


@router.get("/events")
async def events(request: Request, after: Optional[int] = None):
    """Server-Sent Events: every new activity event, as it happens. Pass ?after=<id> to resume."""
    async def stream():
        last = after
        if last is None:
            with Session(engine) as s:
                last = s.exec(select(func.max(Event.id))).one() or 0
        idle = 0
        while not await request.is_disconnected():
            with Session(engine) as s:
                rows = s.exec(select(Event).where(Event.id > last).order_by(Event.id).limit(200)).all()
                batch = [_event_dict(e) for e in rows]
            for ev in batch:
                last = ev["id"]
                yield f"id: {ev['id']}\nevent: {ev['kind']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
            if batch:
                idle = 0
            else:
                idle += 1
                if idle % 15 == 0:
                    yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
