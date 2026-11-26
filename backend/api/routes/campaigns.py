from fastapi import APIRouter, Depends, Response
from sqlmodel import Session

from ...db import get_session
from ...schemas import CampaignIn, CampaignOut
from ...services import campaigns

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignOut])
def list_campaigns(session: Session = Depends(get_session)) -> list[CampaignOut]:
    return [campaigns.to_out(c) for c in campaigns.all_campaigns(session)]


@router.post("", status_code=201, response_model=CampaignOut)
def create_campaign(body: CampaignIn, session: Session = Depends(get_session)) -> CampaignOut:
    return campaigns.to_out(campaigns.create(session, body))


@router.put("/{campaign_id}", response_model=CampaignOut)
def update_campaign(campaign_id: int, body: CampaignIn, session: Session = Depends(get_session)) -> CampaignOut:
    return campaigns.to_out(campaigns.update(session, campaigns.get(session, campaign_id), body))


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: int, session: Session = Depends(get_session)) -> Response:
    campaigns.delete(session, campaigns.get(session, campaign_id))
    return Response(status_code=204)
