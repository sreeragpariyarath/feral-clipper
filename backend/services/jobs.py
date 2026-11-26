"""Jobs: create, list, cancel, retry, and turn them into API responses."""
import hashlib
import re
from pathlib import Path

from sqlmodel import Session, select

from ..config import JOB_LOG_DIR
from ..events import emit
from ..models import Job, JobStep, now
from ..schemas import JobCreate, JobOut, ProgressOut, StepOut
from .errors import Conflict, InvalidInput, NotFound

TWITCH_VOD = re.compile(r"^https?://(?:www\.)?twitch\.tv/videos/(\d{6,})(?:[/?#].*)?$")
VIDEO_EXT = frozenset({".mp4", ".mkv", ".mov", ".webm", ".ts", ".flv", ".avi", ".m4v"})
FINISHED = frozenset({"done", "failed", "cancelled"})


# ---------------------------------------------------------------- step plans
def step_plans() -> dict[str, list[tuple[str, str]]]:
    """Which steps each kind of job runs, with the label shown in the UI."""
    from ..pipeline.registry import ORDER, label_of
    pick = {"download": ORDER[:2], "monitor": ORDER[:8], "render": ORDER}
    return {kind: [(name, label_of(name)) for name in names] for kind, names in pick.items()}


def step_command(job: Job, step: str) -> list[str]:
    """Arguments for `python <args>`: each step runs in its own process so it can be cancelled."""
    return ["-m", "backend.pipeline.run_step", str(job.id), step]


# ---------------------------------------------------------------- sources
def stream_id_for_url(url: str) -> str:
    m = TWITCH_VOD.match(url.strip())
    if not m:
        raise InvalidInput("paste a Twitch VOD link like https://www.twitch.tv/videos/1234567890")
    return f"twitchvod-v{m.group(1)}"


def stream_id_for_file(path: str) -> str:
    p = Path(path)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", p.stem).strip("-").lower()[:40] or "video"
    digest = hashlib.sha1(str(p.resolve()).lower().encode("utf-8")).hexdigest()[:6]
    return f"local-{slug}-{digest}"


def _resolve_source(body: JobCreate) -> tuple[str, str, dict]:
    """Returns (stream_id, source_url, extra params) for a URL or a local file."""
    path = body.path.strip().strip('"')
    if path:
        p = Path(path)
        if not p.is_file():
            raise InvalidInput(f"file not found: {path}")
        if p.suffix.lower() not in VIDEO_EXT:
            raise InvalidInput("that file is not a video (mp4, mkv, mov, webm, ts, flv, avi)")
        return stream_id_for_file(path), "", {"source_path": str(p.resolve())}
    return stream_id_for_url(body.url), body.url.strip(), {}


# ---------------------------------------------------------------- actions
def create(session: Session, body: JobCreate, has_key: bool) -> Job:
    if body.kind == "render" and not has_key:
        raise InvalidInput("render needs the judge: set judge_provider in config.json and its key in .env")
    stream_id, url, extra = _resolve_source(body)
    # job and steps are written in one transaction: the worker never sees a job without steps
    job = Job(kind=body.kind, source_url=url, stream_id=stream_id, params={"top": body.top, **extra},
              status="creating")
    session.add(job)
    session.flush()
    JOB_LOG_DIR.mkdir(parents=True, exist_ok=True)
    job.log_file = str(JOB_LOG_DIR / f"job-{job.id}.log")
    for idx, (name, label) in enumerate(step_plans()[body.kind]):
        session.add(JobStep(job_id=job.id, idx=idx, name=name, label=label))
    job.status = "queued"
    session.add(job)
    emit(session, "job", f"Job {job.id} queued: {body.kind} {stream_id}", job_id=job.id,
         data={"status": "queued"}, commit=False)
    session.commit()
    session.refresh(job)
    return job


def get(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise NotFound("job not found")
    return job


def recent(session: Session, limit: int = 30) -> list[Job]:
    limit = max(1, min(limit, 200))
    return list(session.exec(select(Job).order_by(Job.id.desc()).limit(limit)))


def latest_running(session: Session) -> Job | None:
    return session.exec(select(Job).where(Job.status == "running").order_by(Job.id.desc())).first()


def steps_of(session: Session, job_id: int) -> list[JobStep]:
    return list(session.exec(select(JobStep).where(JobStep.job_id == job_id).order_by(JobStep.idx)))


def cancel(session: Session, job: Job) -> Job:
    if job.status in FINISHED:
        return job
    if job.status == "queued":
        job.status, job.finished_at = "cancelled", now()
        for s in steps_of(session, job.id):
            if s.status == "pending":
                s.status = "cancelled"
                session.add(s)
    else:
        job.cancel_requested = True                 # the worker stops the running step
    session.add(job)
    emit(session, "job", f"Job {job.id} cancel requested", job_id=job.id, data={"status": job.status}, commit=False)
    session.commit()
    session.refresh(job)
    return job


def retry(session: Session, job: Job) -> Job:
    """Queue a failed or cancelled job again. Finished steps are kept; the rest run again."""
    if job.status not in ("failed", "cancelled"):
        raise Conflict("only failed or cancelled jobs can be retried")
    for s in steps_of(session, job.id):
        if s.status != "done":
            s.status, s.progress, s.message, s.eta = "pending", None, "", ""
            s.started_at = s.finished_at = None
            session.add(s)
    job.status, job.error, job.cancel_requested, job.finished_at = "queued", "", False, None
    session.add(job)
    emit(session, "job", f"Job {job.id} queued again", job_id=job.id, data={"status": "queued"}, commit=False)
    session.commit()
    session.refresh(job)
    return job


# ---------------------------------------------------------------- responses
def log_tail(job: Job, lines: int = 80) -> list[str]:
    if not job.log_file or not Path(job.log_file).exists():
        return []
    text = Path(job.log_file).read_text(encoding="utf-8", errors="replace")
    # progress bars redraw one line with \r: keep only the last version of each line
    rows = [part.split("\r")[-1] for part in text.split("\n")]
    return [r for r in rows if r.strip() and not r.startswith("@@P ")][-lines:]


def to_out(session: Session, job: Job, with_log: bool = False) -> JobOut:
    steps = steps_of(session, job.id)
    running = next((s for s in steps if s.status == "running"), None)
    params = job.params or {}
    progress = ProgressOut(
        percent=running.progress if running else (100.0 if job.status == "done" else None),
        text=running.message if running else job.status,
        eta=running.eta if running else "")
    return JobOut(
        id=job.id, kind=job.kind, source_url=job.source_url, stream_id=job.stream_id,
        params={k: v for k, v in params.items() if k != "results"},
        results=params.get("results", {}),
        tokens={"in": params.get("tokens_in", 0), "out": params.get("tokens_out", 0)},
        status=job.status, current_step=job.current_step, error=job.error,
        cancel_requested=job.cancel_requested, created_at=job.created_at, started_at=job.started_at,
        finished_at=job.finished_at, progress=progress,
        steps=[StepOut.model_validate(s, from_attributes=True) for s in steps],
        log=log_tail(job) if with_log else None)
