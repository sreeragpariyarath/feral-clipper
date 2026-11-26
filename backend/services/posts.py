"""Posts: which clip went where, views typed in by hand, and the payout they earn."""
from sqlmodel import Session, select

from ..models import Campaign, Clip, Job, Post, now
from ..schemas import PostIn, PostOut, PostPatch
from .errors import NotFound


def payout(views: int, campaign: Campaign | None) -> float | None:
    """Campaign pay: payout_per_1k dollars for every 1,000 views (None when there is no campaign)."""
    if campaign is None:
        return None
    return round(views / 1000 * campaign.payout_per_1k, 2)


def campaign_of_clip(session: Session, clip: Clip) -> int | None:
    """The campaign of the newest job on this clip's stream that had a campaign set (and still exists)."""
    for job in session.exec(select(Job).where(Job.stream_id == clip.stream_id).order_by(Job.id.desc())):
        camp = (job.params or {}).get("campaign")
        if camp and camp.get("id") and session.get(Campaign, int(camp["id"])) is not None:
            return int(camp["id"])
    return None


def to_out(session: Session, p: Post) -> PostOut:
    clip = session.get(Clip, p.clip_id)
    camp = session.get(Campaign, p.campaign_id) if p.campaign_id else None
    playable = clip is not None and clip.has_video and not clip.deleted
    return PostOut(
        id=p.id, clip_id=p.clip_id, campaign_id=p.campaign_id, campaign_name=camp.name if camp else None,
        platform=p.platform, url=p.url, title=p.title or (clip.title if clip else ""), posted_at=p.posted_at,
        views=p.views, views_at=p.views_at, payout_usd=payout(p.views, camp),
        clip_title=clip.title if clip else "(deleted clip)",
        thumb_url=f"/media/{clip.stream_id}/{clip.clip_no}/thumb.jpg" if playable else None)


def all_posts(session: Session, clip_id: int | None = None) -> list[Post]:
    q = select(Post)
    if clip_id is not None:
        q = q.where(Post.clip_id == clip_id)
    return list(session.exec(q.order_by(Post.posted_at.desc())))


def get(session: Session, post_id: int) -> Post:
    p = session.get(Post, post_id)
    if p is None:
        raise NotFound("post not found")
    return p


def create(session: Session, body: PostIn) -> Post:
    clip = session.get(Clip, body.clip_id)
    if clip is None:
        raise NotFound("clip not found")
    campaign_id = body.campaign_id if body.campaign_id is not None else campaign_of_clip(session, clip)
    if campaign_id is not None and session.get(Campaign, campaign_id) is None:
        raise NotFound("campaign not found")
    p = Post(clip_id=clip.id, campaign_id=campaign_id, platform=body.platform, url=body.url.strip(),
             title=body.title.strip() or clip.title, posted_at=body.posted_at or now())
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def update(session: Session, p: Post, body: PostPatch) -> Post:
    if body.views is not None:
        p.views, p.views_at = body.views, now()
    if body.url is not None:
        p.url = body.url.strip()
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def delete(session: Session, p: Post) -> None:
    """Removes only this record; the clip and the real upload are untouched."""
    session.delete(p)
    session.commit()
