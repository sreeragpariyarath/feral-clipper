from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from ...db import get_session
from ...importer import sync_all
from ...schemas import BackupOut, EventOut, HealthOut, SettingsIn, SettingsOut
from ...services import system

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthOut)
def health(session: Session = Depends(get_session)) -> HealthOut:
    return system.health(session)


@router.get("/settings", response_model=SettingsOut)
def get_settings(session: Session = Depends(get_session)) -> SettingsOut:
    return system.settings(session)


@router.put("/settings", response_model=SettingsOut)
def put_settings(body: SettingsIn, session: Session = Depends(get_session)) -> SettingsOut:
    return system.save_settings(session, body.values)


@router.post("/sync")
def sync(session: Session = Depends(get_session)) -> dict[str, int]:
    """Re-read every stream folder into the database."""
    return {"streams": sync_all(session)}


@router.get("/backups", response_model=list[BackupOut])
def list_backups() -> list[BackupOut]:
    return system.backups()


@router.post("/backups", status_code=201, response_model=BackupOut)
def make_backup() -> BackupOut:
    """Copy data/feral.db into backups/ (safe while jobs run)."""
    return system.backup()


@router.get("/activity", response_model=list[EventOut])
def activity(limit: int = 50, session: Session = Depends(get_session)) -> list[EventOut]:
    return system.recent_events(session, limit)


@router.get("/events")
async def events(request: Request, after: int | None = None) -> StreamingResponse:
    """Server-Sent Events: every new activity event, as it happens. Pass ?after=<id> to resume."""
    return StreamingResponse(system.event_stream(after, request.is_disconnected), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
