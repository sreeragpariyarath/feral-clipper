from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...db import get_session
from ...schemas import MonitorSheetOut, StreamOut
from ...services import streams

router = APIRouter(prefix="/streams", tags=["streams"])


@router.get("", response_model=list[StreamOut])
def list_streams(session: Session = Depends(get_session)) -> list[StreamOut]:
    return [streams.to_out(session, s) for s in streams.all_streams(session)]


@router.get("/{stream_id}", response_model=StreamOut)
def get_stream(stream_id: str, session: Session = Depends(get_session)) -> StreamOut:
    return streams.to_out(session, streams.get(session, stream_id))


@router.get("/{stream_id}/monitor", response_model=MonitorSheetOut)
def stream_monitor(stream_id: str, session: Session = Depends(get_session)) -> MonitorSheetOut:
    return streams.monitor_sheet(streams.get(session, stream_id).id)
