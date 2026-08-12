from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.api.schemas.negotiation_schema import NegotiationCreate, NegotiationOffer, NegotiationResponse
from app.database import get_db
from app.services.negotiation_service import NegotiationService

router = APIRouter()


@router.post("/negotiations", response_model=NegotiationResponse)
def start_negotiation(negotiation: NegotiationCreate, db: Session = Depends(get_db)):
    manager = db.query(models.Manager).first()
    if not manager or not manager.team_id:
        raise HTTPException(status_code=404, detail="No active manager or team selected")

    return NegotiationService(db).start_negotiation(negotiation, manager)


@router.post("/negotiations/{negotiation_id}/offer", response_model=NegotiationResponse)
def make_offer(negotiation_id: int, offer: NegotiationOffer, db: Session = Depends(get_db)):
    manager = db.query(models.Manager).first()
    if not manager or not manager.team_id:
        raise HTTPException(status_code=404, detail="No active manager or team selected")

    return NegotiationService(db).make_offer(negotiation_id, offer, manager)
