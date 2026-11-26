"""Health, settings and the activity feed (including the live event stream)."""
import asyncio
import json
import shutil
from collections.abc import AsyncIterator, Callable, Awaitable
from typing import Any

from sqlmodel import Session, func, select

from ..config import ROOT, key_status
from ..db import engine
from ..models import Event, Job, Setting
from ..schemas import EventOut, HealthOut, SettingsOut
from . import jobs
from .errors import InvalidInput


def health(session: Session) -> HealthOut:
    running = jobs.latest_running(session)
    queued = session.exec(select(func.count()).select_from(Job).where(Job.status == "queued")).one()
    disk = shutil.disk_usage(ROOT)
    return HealthOut(ok=True, keys=key_status(), running_job=running.id if running else None, queued_jobs=queued,
                     disk={"free_gb": round(disk.free / 1e9, 1), "total_gb": round(disk.total / 1e9, 1)})


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
