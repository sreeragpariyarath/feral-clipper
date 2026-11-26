from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...db import get_session
from ...schemas import ClipDetailOut, ClipOut, ClipPatch
from ...schemas.clip import Decision
from ...services import clips

router = APIRouter(prefix="/clips", tags=["clips"])


@router.get("", response_model=list[ClipOut])
def list_clips(stream_id: str | None = None, decision: Decision | None = None, deleted: bool = False,
               session: Session = Depends(get_session)) -> list[ClipOut]:
    return [clips.to_out(c) for c in clips.query(session, stream_id, decision, deleted)]


@router.get("/{clip_id}", response_model=ClipOut)
def get_clip(clip_id: int, session: Session = Depends(get_session)) -> ClipOut:
    return clips.to_out(clips.get(session, clip_id))


@router.get("/{clip_id}/details", response_model=ClipDetailOut)
def clip_details(clip_id: int, session: Session = Depends(get_session)) -> ClipDetailOut:
    return clips.details(clips.get(session, clip_id))


@router.patch("/{clip_id}", response_model=ClipOut)
def patch_clip(clip_id: int, body: ClipPatch, session: Session = Depends(get_session)) -> ClipOut:
    return clips.to_out(clips.review(session, clips.get(session, clip_id), body))


@router.delete("/{clip_id}", response_model=ClipOut)
def delete_clip(clip_id: int, session: Session = Depends(get_session)) -> ClipOut:
    """Moves the clip to the trash folder; nothing is removed permanently."""
    return clips.to_out(clips.trash(session, clips.get(session, clip_id)))


@router.post("/{clip_id}/restore", response_model=ClipOut)
def restore_clip(clip_id: int, session: Session = Depends(get_session)) -> ClipOut:
    return clips.to_out(clips.restore(session, clips.get(session, clip_id)))
