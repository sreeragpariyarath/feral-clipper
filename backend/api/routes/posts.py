from fastapi import APIRouter, Depends, Response
from sqlmodel import Session

from ...db import get_session
from ...schemas import PostIn, PostingKitOut, PostOut, PostPatch
from ...services import clips, kit, posts

router = APIRouter(tags=["posts"])


@router.get("/posts", response_model=list[PostOut])
def list_posts(clip_id: int | None = None, session: Session = Depends(get_session)) -> list[PostOut]:
    return [posts.to_out(session, p) for p in posts.all_posts(session, clip_id)]


@router.post("/posts", status_code=201, response_model=PostOut)
def create_post(body: PostIn, session: Session = Depends(get_session)) -> PostOut:
    return posts.to_out(session, posts.create(session, body))


@router.patch("/posts/{post_id}", response_model=PostOut)
def update_post(post_id: int, body: PostPatch, session: Session = Depends(get_session)) -> PostOut:
    return posts.to_out(session, posts.update(session, posts.get(session, post_id), body))


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: int, session: Session = Depends(get_session)) -> Response:
    posts.delete(session, posts.get(session, post_id))
    return Response(status_code=204)


@router.get("/clips/{clip_id}/kit", response_model=PostingKitOut)
def posting_kit(clip_id: int, session: Session = Depends(get_session)) -> PostingKitOut:
    return kit.build(session, clips.get(session, clip_id))
