"""Write activity events. The browser receives them live through /api/v1/events."""
from typing import Optional

from sqlmodel import Session

from .models import Event


def emit(session: Session, kind: str, message: str = "", job_id: Optional[int] = None,
         data: Optional[dict] = None, commit: bool = True) -> Event:
    ev = Event(job_id=job_id, kind=kind, message=message, data=data or {})
    session.add(ev)
    if commit:
        session.commit()
    return ev
