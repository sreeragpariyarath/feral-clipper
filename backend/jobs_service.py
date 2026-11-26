"""Creating jobs, their step plans, and turning jobs into JSON for the API."""
import hashlib
import re
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from .config import JOB_LOG_DIR
from .events import emit
from .models import Job, JobStep, now

KINDS = ("download", "monitor", "render")
TWITCH_VOD = re.compile(r"^https?://(?:www\.)?twitch\.tv/videos/(\d{6,})(?:[/?#].*)?$")

VIDEO_EXT = {".mp4", ".mkv", ".mov", ".webm", ".ts", ".flv", ".avi", ".m4v"}


def _plans():
    from .pipeline.steps import ORDER, STEPS
    pick = {"download": ORDER[:2], "monitor": ORDER[:8], "render": ORDER}
    return {kind: [(name, STEPS[name][0]) for name in names] for kind, names in pick.items()}


class JobError(ValueError):
    pass


def stream_id_for(url: str) -> str:
    m = TWITCH_VOD.match(url.strip())
    if not m:
        raise JobError("paste a Twitch VOD link like https://www.twitch.tv/videos/1234567890")
    return f"twitchvod-v{m.group(1)}"


def step_command(job: Job, step: str) -> list:
    """Arguments for `python <args>`: each step runs in its own process so it can be cancelled."""
    return ["-m", "backend.pipeline.run_step", str(job.id), step]


def local_stream_id(path: str) -> str:
    p = Path(path)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", p.stem).strip("-").lower()[:40] or "video"
    digest = hashlib.sha1(str(p.resolve()).lower().encode("utf-8")).hexdigest()[:6]
    return f"local-{slug}-{digest}"


def create_job(session: Session, kind: str, url: str = "", top: int = 10, has_key: bool = False,
               path: str = "") -> Job:
    if kind not in KINDS:
        raise JobError("kind must be download, monitor or render")
    if not 1 <= int(top) <= 30:
        raise JobError("top must be between 1 and 30")
    if kind == "render" and not has_key:
        raise JobError("render needs ANTHROPIC_API_KEY in .env")
    url, path = (url or "").strip(), (path or "").strip().strip('"')
    params = {"top": int(top)}
    if path:
        p = Path(path)
        if not p.is_file():
            raise JobError(f"file not found: {path}")
        if p.suffix.lower() not in VIDEO_EXT:
            raise JobError("that file is not a video (mp4, mkv, mov, webm, ts, flv, avi)")
        stream_id = local_stream_id(path)
        params["source_path"] = str(p.resolve())
    elif url:
        stream_id = stream_id_for(url)
    else:
        raise JobError("give a Twitch VOD link or a video file path")
    job = Job(kind=kind, source_url=url, stream_id=stream_id, params=params)
    # job and steps go in one transaction: the worker must never see a job without its steps
    job.status = "creating"
    session.add(job)
    session.flush()                     # assigns job.id without committing
    JOB_LOG_DIR.mkdir(parents=True, exist_ok=True)
    job.log_file = str(JOB_LOG_DIR / f"job-{job.id}.log")
    for idx, (name, label) in enumerate(_plans()[kind]):
        session.add(JobStep(job_id=job.id, idx=idx, name=name, label=label))
    job.status = "queued"
    session.add(job)
    emit(session, "job", f"Job {job.id} queued: {kind} {stream_id}", job_id=job.id,
         data={"status": "queued"}, commit=False)
    session.commit()
    session.refresh(job)
    return job


def steps_of(session: Session, job_id: int) -> list:
    return list(session.exec(select(JobStep).where(JobStep.job_id == job_id).order_by(JobStep.idx)))


def log_tail(job: Job, lines: int = 80) -> list:
    if not job.log_file or not Path(job.log_file).exists():
        return []
    text = Path(job.log_file).read_text(encoding="utf-8", errors="replace")
    # the download tool redraws its progress line with \r; keep only the last version of each line
    rows = [part.split("\r")[-1] for part in text.split("\n")]
    return [r for r in rows if r.strip()][-lines:]


def job_dict(session: Session, job: Job, with_log: bool = False) -> dict:
    steps = steps_of(session, job.id)
    running = next((s for s in steps if s.status == "running"), None)
    out = {
        "id": job.id,
        "kind": job.kind,
        "source_url": job.source_url,
        "stream_id": job.stream_id,
        "params": {k: v for k, v in (job.params or {}).items() if k != "results"},
        "results": (job.params or {}).get("results", {}),
        "tokens": {"in": (job.params or {}).get("tokens_in", 0), "out": (job.params or {}).get("tokens_out", 0)},
        "status": job.status,
        "current_step": job.current_step,
        "error": job.error,
        "cancel_requested": job.cancel_requested,
        "created_at": job.created_at.isoformat(timespec="seconds") if job.created_at else None,
        "started_at": job.started_at.isoformat(timespec="seconds") if job.started_at else None,
        "finished_at": job.finished_at.isoformat(timespec="seconds") if job.finished_at else None,
        "progress": {
            "percent": running.progress if running else (100.0 if job.status == "done" else None),
            "text": running.message if running else job.status,
            "eta": running.eta if running else "",
        },
        "steps": [{
            "idx": s.idx, "name": s.name, "label": s.label, "status": s.status, "progress": s.progress,
            "message": s.message, "eta": s.eta,
            "started_at": s.started_at.isoformat(timespec="seconds") if s.started_at else None,
            "finished_at": s.finished_at.isoformat(timespec="seconds") if s.finished_at else None,
        } for s in steps],
    }
    if with_log:
        out["log"] = log_tail(job)
    return out


def request_cancel(session: Session, job: Job) -> Job:
    if job.status in ("done", "failed", "cancelled"):
        return job
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = now()
        for s in steps_of(session, job.id):
            if s.status == "pending":
                s.status = "cancelled"
                session.add(s)
    else:
        job.cancel_requested = True       # the worker stops the running step
    session.add(job)
    emit(session, "job", f"Job {job.id} cancel requested", job_id=job.id, data={"status": job.status}, commit=False)
    session.commit()
    session.refresh(job)
    return job


def retry(session: Session, job: Job) -> Job:
    """Queue a failed or cancelled job again. Finished steps are kept; the rest run again."""
    if job.status not in ("failed", "cancelled"):
        raise JobError("only failed or cancelled jobs can be retried")
    for s in steps_of(session, job.id):
        if s.status != "done":
            s.status, s.progress, s.message, s.eta = "pending", None, "", ""
            s.started_at = s.finished_at = None
            session.add(s)
    job.status, job.error, job.cancel_requested = "queued", "", False
    job.finished_at = None
    session.add(job)
    emit(session, "job", f"Job {job.id} queued again", job_id=job.id, data={"status": "queued"}, commit=False)
    session.commit()
    session.refresh(job)
    return job


def latest_running(session: Session) -> Optional[Job]:
    return session.exec(select(Job).where(Job.status == "running").order_by(Job.id.desc())).first()
