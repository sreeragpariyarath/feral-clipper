"""Campaigns: rules, logo, caption and payout for a clipping campaign."""
from sqlmodel import Session, select

from ..models import Campaign
from ..schemas import CampaignIn, CampaignOut
from .errors import NotFound


def to_out(c: Campaign) -> CampaignOut:
    return CampaignOut.model_validate(c, from_attributes=True)


def all_campaigns(session: Session) -> list[Campaign]:
    return list(session.exec(select(Campaign).order_by(Campaign.id.desc())))


def get(session: Session, campaign_id: int) -> Campaign:
    c = session.get(Campaign, campaign_id)
    if c is None:
        raise NotFound("campaign not found")
    return c


def create(session: Session, body: CampaignIn) -> Campaign:
    c = Campaign(**body.model_dump())
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def update(session: Session, c: Campaign, body: CampaignIn) -> Campaign:
    for key, value in body.model_dump().items():
        setattr(c, key, value)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def delete(session: Session, c: Campaign) -> None:
    session.delete(c)
    session.commit()
