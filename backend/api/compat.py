"""Routes the current frontend already uses (/api/sessions, /api/jobs, /media).
They read and write the same database as /api/v1, so both stay in step.
Phase 3 moves the frontend to /api/v1; then these routes can go."""
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from ..schemas import ClipPatch, JobCreate
from ..services import clips as clips_svc, jobs as jobs_svc, streams as streams_svc
from ..config import VOD_DIR, key_status
from ..db import get_session
from ..models import Clip, Job, Stream

router = APIRouter()
SAFE = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")


def _safe(*parts: str) -> None:
    for p in parts:
        if not SAFE.match(p or ""):
            raise HTTPException(400, "bad id")


def _clip(session: Session, sid: str, cid: str) -> Clip:
    _safe(sid, cid)
    return clips_svc.by_number(session, sid, cid)


@router.get("/api/sessions")
def sessions(session: Session = Depends(get_session)):
    out = []
    for s in session.exec(select(Stream).order_by(Stream.id)).all():
        clips = session.exec(select(Clip).where(Clip.stream_id == s.id, Clip.deleted == False)).all()  # noqa: E712
        out.append({"id": s.id, "title": s.title or s.id, "channel": s.channel, "clips": len(clips),
                    "ready": sum(1 for c in clips if c.status == "ready")})
    return out


@router.get("/api/sessions/{sid}/clips")
def session_clips(sid: str, session: Session = Depends(get_session)):
    _safe(sid)
    rows = session.exec(select(Clip).where(Clip.stream_id == sid, Clip.deleted == False)).all()  # noqa: E712
    rows = sorted(rows, key=lambda c: (c.status != "ready", -c.final_score))
    return [{"id": c.clip_no, "status": c.status, "final": c.final_score, "strong": c.strong,
             "has_video": c.has_video, "title": c.title, "caption": c.caption, "hook": c.hook,
             "reasons": c.reasons, "judge_source": c.judge_source, "decision": c.decision} for c in rows]


@router.get("/api/sessions/{sid}/monitor")
def session_monitor(sid: str):
    _safe(sid)
    return streams_svc.monitor_sheet(sid).model_dump()


@router.post("/api/sessions/{sid}/clips/{cid}/review")
def session_review(sid: str, cid: str, body: ClipPatch, session: Session = Depends(get_session)):
    c = clips_svc.review(session, _clip(session, sid, cid), body)
    return {"decision": c.decision, "title": c.title, "caption": c.caption}


@router.delete("/api/sessions/{sid}/clips/{cid}")
def session_delete(sid: str, cid: str, session: Session = Depends(get_session)):
    clips_svc.trash(session, _clip(session, sid, cid))
    return {"trashed": cid}


# ---------------------------------------------------------------- jobs in the shape the current page expects
def _old_job(session: Session, job: Job, with_log: bool) -> dict:
    d = jobs_svc.to_out(session, job, with_log=with_log).model_dump(mode="json")
    state = {"queued": "running", "running": "running", "done": "done"}.get(job.status, "failed")
    return {"id": str(job.id), "url": job.source_url, "mode": job.kind, "top": job.params.get("top", 10),
            "session": job.stream_id, "state": state,
            "step": "queued" if job.status == "queued" else (job.current_step or job.status),
            "started": d["started_at"] or d["created_at"], "finished": d["finished_at"], "error": job.error,
            "log": d.get("log"), "progress": d["progress"]}


class OldJobIn(BaseModel):
    url: str = ""
    path: str = ""
    mode: Literal["download", "monitor", "render"] = "monitor"
    top: int = 10


@router.post("/api/jobs", status_code=202)
def old_create_job(body: OldJobIn, session: Session = Depends(get_session)):
    req = JobCreate(kind=body.mode, url=body.url, path=body.path, top=body.top)
    job = jobs_svc.create(session, req, key_status()["anthropic"])
    return _old_job(session, job, with_log=False)


@router.get("/api/jobs")
def old_list_jobs(session: Session = Depends(get_session)):
    return [_old_job(session, j, False) for j in jobs_svc.recent(session, 20)]


@router.get("/api/jobs/{job_id}")
def old_get_job(job_id: str, session: Session = Depends(get_session)):
    if not job_id.isdigit():
        raise HTTPException(404, "job not found")
    return _old_job(session, jobs_svc.get(session, int(job_id)), with_log=True)


# ---------------------------------------------------------------- media (video seeking supported)
@router.get("/media/{sid}/{cid}/{name}")
def media(sid: str, cid: str, name: str, download: bool = False):
    _safe(sid, cid)
    if name == "strip.jpg":                       # frame strip from the visual step
        path: Path = VOD_DIR / sid / "auto" / "frames" / cid / name
    elif name in ("clip.mp4", "thumb.jpg"):
        path = VOD_DIR / sid / "clips" / cid / name
    else:
        raise HTTPException(404, "not found")
    if not path.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="video/mp4" if name.endswith(".mp4") else "image/jpeg",
                        filename=f"{sid}-{cid}.mp4" if name.endswith(".mp4") and download else None)
