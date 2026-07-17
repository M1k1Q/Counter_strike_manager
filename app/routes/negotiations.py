from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db


router = APIRouter()


def some_acceptance_check(negotiation: models.Negotiation) -> bool:
    if negotiation.success_chance >= 70:
        return True
    if negotiation.rounds >= 1 and negotiation.offer_amount >= (negotiation.player.price * 1.3):
        return True
    if negotiation.success_chance >= 55 and negotiation.rounds >= 2:
        return True
    return False


@router.post("/negotiations", response_model=schemas.NegotiationResponse)
def start_negotiation(negotiation: schemas.NegotiationCreate, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == negotiation.player_id).first()
    if not player or not player.team_id:
        raise HTTPException(status_code=400, detail="Player must be on another team")

    source_team = db.query(models.Team).filter(models.Team.id == player.team_id).first()
    if not source_team:
        raise HTTPException(status_code=404, detail="Source team not found")

    manager = db.query(models.Manager).first()
    if not manager or not manager.team_id:
        raise HTTPException(status_code=404, detail="No active manager or team selected")

    if manager.budget < negotiation.offer_amount:
        raise HTTPException(status_code=400, detail="Offer exceeds current budget")

    new_negotiation = models.Negotiation(
        player_id=player.id,
        source_team_id=source_team.id,
        target_team_id=manager.team_id,
        manager_id=manager.id,
        offer_amount=negotiation.offer_amount,
    )
    new_negotiation.player = player
    new_negotiation.source_team = source_team
    new_negotiation.target_team = db.query(models.Team).filter(models.Team.id == manager.team_id).first()
    new_negotiation.manager = manager
    new_negotiation.calculate_success()

    if some_acceptance_check(new_negotiation):
        new_negotiation.status = "accepted"
        new_negotiation.player.team_id = new_negotiation.target_team_id
        manager.budget -= negotiation.offer_amount

    db.add(new_negotiation)
    db.commit()
    db.refresh(new_negotiation)
    return new_negotiation

@router.post("/negotiations/{negotiation_id}/offer", response_model=schemas.NegotiationResponse)
def make_offer(negotiation_id: int, offer: schemas.NegotiationOffer, db: Session = Depends(get_db)):
    negotiation = db.query(models.Negotiation).filter(models.Negotiation.id == negotiation_id).first()
    if not negotiation or negotiation.status != "pending":
        raise HTTPException(status_code=404, detail="Negotiation not found or closed")

    negotiation.offer_amount = offer.offer_amount
    negotiation.rounds += 1
    negotiation.calculate_success()

    # decide acceptance in backend logic
    if some_acceptance_check(negotiation):
        negotiation.status = "accepted"
        negotiation.player.team_id = negotiation.target_team_id
        manager = negotiation.manager
        manager.budget -= offer.offer_amount
    elif negotiation.rounds >= 3:
        negotiation.status = "rejected"

    db.commit()
    db.refresh(negotiation)
    return negotiation