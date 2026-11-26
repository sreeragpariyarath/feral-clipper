"""Health, settings and the activity feed (including the live event stream)."""
import asyncio
import json
import shutil
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, func, select

from ..config import DATA_DIR, DB_PATH, LOW_DISK_GB, ROOT, key_status
from ..db import engine
from ..models import Event, Job, Setting
from ..schemas import BackupOut, EventOut, HealthOut, SettingsOut
from . import jobs
from .errors import InvalidInput


def health(session: Session) -> HealthOut:
    running = jobs.latest_running(session)
    queued = session.exec(select(func.count()).select_from(Job).where(Job.status == "queued")).one()
    disk = shutil.disk_usage(DATA_DIR)
    free_gb = disk.free / 1e9
    return HealthOut(ok=True, keys=key_status(), running_job=running.id if running else None, queued_jobs=queued,
                     disk={"free_gb": round(free_gb, 1), "total_gb": round(disk.total / 1e9, 1),
                           "low_below_gb": LOW_DISK_GB},
                     low_disk=free_gb < LOW_DISK_GB)


# ---------------------------------------------------------------- database backup
BACKUP_DIR = ROOT / "backups"


def backup() -> BackupOut:
    """Copy the database with SQLite's online backup (safe while the API and worker are writing)."""
    import sqlite3
    BACKUP_DIR.mkdir(exist_ok=True)
    dest = BACKUP_DIR / f"feral-{datetime.now():%Y%m%d-%H%M%S}.db"
    src = sqlite3.connect(DB_PATH)
    try:
        out = sqlite3.connect(dest)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()
    return _backup_out(dest)


def _backup_out(p: Path) -> BackupOut:
    st = p.stat()
    return BackupOut(name=p.name, size_mb=round(st.st_size / 1e6, 2),
                     created_at=datetime.fromtimestamp(st.st_mtime).astimezone())


def backups() -> list[BackupOut]:
    if not BACKUP_DIR.is_dir():
        return []
    return [_backup_out(p) for p in sorted(BACKUP_DIR.glob("feral-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)]


def settings(session: Session) -> SettingsOut:
    rows = session.exec(select(Setting)).all()
    return SettingsOut(keys=key_status(), values={r.key: json.loads(r.value) for r in rows})


def save_settings(session: Session, values: dict[str, Any]) -> SettingsOut:
    for key, value in values.items():
        if not key or len(key) > 80:
            raise InvalidInput("bad setting key")
        row = session.get(Setting, key) or Setting(key=key)
        row.value = json.dumps(value)
        session.add(row)
    session.commit()
    return settings(session)


def event_out(e: Event) -> EventOut:
    return EventOut.model_validate(e, from_attributes=True)


def recent_events(session: Session, limit: int = 50) -> list[EventOut]:
    rows = session.exec(select(Event).order_by(Event.id.desc()).limit(max(1, min(limit, 500)))).all()
    return [event_out(e) for e in rows]


async def event_stream(after: int | None, is_disconnected: Callable[[], Awaitable[bool]],
                       poll_seconds: float = 1.0) -> AsyncIterator[str]:
    """Server-Sent Events: every new event, as it happens. `after` resumes from an event id."""
    with Session(engine) as s:
        last = after if after is not None else (s.exec(select(func.max(Event.id))).one() or 0)
    idle = 0
    while not await is_disconnected():
        with Session(engine) as s:
            batch = [event_out(e) for e in s.exec(
                select(Event).where(Event.id > last).order_by(Event.id).limit(200))]
        for ev in batch:
            last = ev.id
            yield f"id: {ev.id}\nevent: {ev.kind}\ndata: {ev.model_dump_json()}\n\n"
        idle = 0 if batch else idle + 1
        if idle and idle % 15 == 0:
            yield ": keep-alive\n\n"
        await asyncio.sleep(poll_seconds)
