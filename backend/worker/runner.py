"""The worker: a separate process that runs queued jobs one at a time.

It keeps running when the API or the frontend restarts. A job that was running when the worker
itself stopped is queued again on the next start, and its finished steps are skipped.
One job at a time on purpose: Whisper, MediaPipe and NVENC share one GPU.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime

from sqlmodel import Session, select

from ..config import DATA_DIR, MIN_FREE_GB, PROGRESS_WRITE_SECONDS, ROOT, WORKER_IDLE_SECONDS
from ..db import engine, init_db
from ..events import emit
from ..importer import sync_stream
from ..services.jobs import step_command, steps_of
from ..models import Job, JobStep, now
from .errors import explain

PERCENT = re.compile(r"\[download\]\s+([\d.]+)%(?:\s+of\s+~?\s*([\d.]+\s*\w+))?(?:\s+at\s+([\d.]+\s*\S+))?(?:\s+ETA\s+(\S+))?")


class _Output:
    """Reads a step's output on a background thread, writes it to the job log, keeps the latest line."""

    def __init__(self, proc, log_path):
        self.proc = proc
        self.log_path = log_path
        self.last_line = ""
        self.percent = None
        self.eta = ""
        self.tail = []
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self):
        buf = b""
        with open(self.log_path, "ab") as log:
            while True:
                chunk = os.read(self.proc.stdout.fileno(), 4096) if self.proc.stdout else b""
                if not chunk:
                    break
                log.write(chunk)
                log.flush()
                buf += chunk
                parts = re.split(rb"[\r\n]", buf)
                buf = parts.pop()
                for raw in parts:
                    line = raw.decode("utf-8", "replace").strip()
                    if line:
                        self._line(line)

    def _line(self, line):
        if line.startswith("@@P "):                 # structured progress from a pipeline step
            try:
                data = json.loads(line[4:])
            except ValueError:
                return
            self.percent = data.get("percent")
            self.last_line = (data.get("message") or self.last_line)[-200:]
            self.eta = data.get("eta") or ""
            return
        self.last_line = line[-200:]
        self.tail = (self.tail + [line])[-40:]       # enough to hold a full traceback
        m = PERCENT.search(line)
        if m:
            self.percent = float(m.group(1))
            size, speed, eta = m.group(2), m.group(3), m.group(4)
            bits = [f"{self.percent:.1f}%"]
            if size:
                bits.append(f"of {size}")
            if speed:
                bits.append(f"at {speed}")
            self.last_line = " ".join(bits)
            self.eta = f"{eta} left" if eta and eta != "Unknown" else ""

    def join(self):
        self._thread.join(timeout=10)


def _kill_tree(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def _run_step(session: Session, job: Job, step: JobStep) -> str:
    """Run one step. Returns done | failed | cancelled."""
    free_gb = shutil.disk_usage(DATA_DIR).free / 1e9
    if free_gb < MIN_FREE_GB:                 # refuse before writing half a file onto a full disk
        step.status, step.started_at, step.finished_at = "failed", now(), now()
        step.message = f"only {free_gb:.1f} GB free on the data disk (need {MIN_FREE_GB:.0f} GB)"
        job.error, job.error_hint = step.message, ("Free some space (Streams page: delete old stream videos), "
                                                   "then press Retry.")
        session.add_all([step, job])
        emit(session, "step", f"{step.label} failed: disk nearly full", job_id=job.id,
             data={"step": step.name, "status": "failed"}, commit=False)
        session.commit()
        return "failed"
    args = step_command(job, step.name)
    step.status, step.started_at, step.progress, step.message, step.eta = "running", now(), None, "starting", ""
    job.current_step = step.label
    session.add_all([step, job])
    emit(session, "step", f"{step.label} started", job_id=job.id,
         data={"step": step.name, "status": "running"}, commit=False)
    session.commit()

    with open(job.log_file, "a", encoding="utf-8") as log:
        log.write(f"\n=== {step.label}  ({datetime.now():%Y-%m-%d %H:%M:%S})\n$ python {' '.join(args)}\n")

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen([sys.executable, "-u", *args], cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
    out = _Output(proc, job.log_file)
    last_write = 0.0
    cancelled = False
    while proc.poll() is None:
        time.sleep(0.5)
        if time.time() - last_write < PROGRESS_WRITE_SECONDS:
            continue
        last_write = time.time()
        session.refresh(job)
        if job.cancel_requested:
            _kill_tree(proc.pid)
            cancelled = True
            break
        if out.last_line and (out.last_line != step.message or out.percent != step.progress):
            step.message, step.progress, step.eta = out.last_line, out.percent, out.eta
            session.add(step)
            emit(session, "progress", step.message, job_id=job.id,
                 data={"step": step.name, "percent": step.progress, "eta": step.eta}, commit=False)
            session.commit()
    proc.wait()
    out.join()

    step.finished_at = now()
    if cancelled:
        step.status, step.message = "cancelled", "cancelled"
        result = "cancelled"
    elif proc.returncode == 0:
        step.status, step.progress, step.message, step.eta = "done", 100.0, "done", ""
        result = "done"
    else:
        reason, hint = explain(out.tail, proc.returncode)
        step.status, step.message = "failed", reason
        job.error, job.error_hint = reason, hint
        result = "failed"
    session.add_all([step, job])
    emit(session, "step", f"{step.label} {result}", job_id=job.id,
         data={"step": step.name, "status": result}, commit=False)
    session.commit()
    return result


def run_job(session: Session, job: Job) -> None:
    job.status, job.started_at, job.error = "running", job.started_at or now(), ""
    session.add(job)
    emit(session, "job", f"Job {job.id} started", job_id=job.id, data={"status": "running"}, commit=False)
    session.commit()

    steps = steps_of(session, job.id)
    if not steps:                         # should not happen; never mark an empty job as done
        job.status, job.error, job.finished_at = "failed", "job has no steps", now()
        session.add(job)
        emit(session, "job", f"Job {job.id} failed: no steps", job_id=job.id, data={"status": "failed"})
        return
    result = "done"
    for step in steps:
        if step.status == "done":
            continue                      # finished on an earlier run
        result = _run_step(session, job, step)
        if result != "done":
            break
        try:                              # keep the database in step with the files after each step
            sync_stream(session, job.stream_id, job.source_url)
        except Exception as exc:
            emit(session, "info", f"Could not read stream files yet: {exc}", job_id=job.id)

    session.refresh(job)
    if result == "cancelled":
        for s in steps_of(session, job.id):
            if s.status == "pending":
                s.status = "cancelled"
                session.add(s)
    job.status = {"done": "done", "failed": "failed", "cancelled": "cancelled"}[result]
    job.current_step = "" if result == "done" else job.current_step
    job.cancel_requested = False
    job.finished_at = now()
    session.add(job)
    emit(session, "job", f"Job {job.id} {job.status}", job_id=job.id, data={"status": job.status}, commit=False)
    session.commit()


def _recover(session: Session) -> None:
    """Jobs left 'running' by a stopped worker go back to the queue; their unfinished steps reset."""
    for job in session.exec(select(Job).where(Job.status == "running")):
        for s in steps_of(session, job.id):
            if s.status == "running":
                s.status, s.progress, s.message = "pending", None, "resumed after worker restart"
                session.add(s)
        job.status = "queued"
        session.add(job)
        emit(session, "job", f"Job {job.id} queued again after a worker restart", job_id=job.id,
             data={"status": "queued"}, commit=False)
    session.commit()


_lock_handle = None


def _single_instance() -> bool:
    """Only one worker may run: two workers could start the same job and fight over the GPU."""
    global _lock_handle
    from ..config import DATA_DIR
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _lock_handle = open(DATA_DIR / "worker.lock", "a+")
    try:
        if os.name == "nt":
            import msvcrt
            _lock_handle.seek(0)
            msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def main() -> None:
    if not _single_instance():
        print("Another worker is already running. Close it first, or keep using that one.", flush=True)
        sys.exit(1)
    init_db()
    print(f"Worker started (pid {os.getpid()}). Waiting for jobs...", flush=True)
    with Session(engine) as session:
        _recover(session)
    while True:
        with Session(engine) as session:
            job = session.exec(select(Job).where(Job.status == "queued").order_by(Job.id)).first()
            if job is None:
                time.sleep(WORKER_IDLE_SECONDS)
                continue
            print(f"Running job {job.id}: {job.kind} {job.stream_id}", flush=True)
            try:
                run_job(session, job)
            except Exception as exc:                     # never let one job kill the worker
                session.rollback()
                job = session.get(Job, job.id)
                job.status, job.error, job.finished_at = "failed", f"worker error: {exc}", now()
                session.add(job)
                emit(session, "job", f"Job {job.id} failed: {exc}", job_id=job.id, data={"status": "failed"})
            print(f"Job {job.id} finished: {job.status}", flush=True)
