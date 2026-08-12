import random
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

router = APIRouter(prefix="/ai-buyouts", tags=["ai-buyouts"])

MAX_ROUNDS = 3
AI_CEILING_MULTIPLIER = 2.5


class AIBuyoutOfferResponse(BaseModel):
    id: int
    player_id: int
    ai_team_id: int
    current_offer: int
    initial_offer: int
    rounds: int
    status: str
    player_name: str
    ai_team_name: str
    ai_team_ranking: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CounterOfferBody(BaseModel):
    counter_amount: int


def _execute_sale(db: Session, offer: models.AIBuyoutOffer, sold_for: int) -> None:
    manager = db.query(models.Manager).first()
    if not manager:
        raise HTTPException(status_code=404, detail="No active manager")

    offer.player.team_id = None
    offer.player.is_active_roster = False
    manager.budget += sold_for
    offer.ai_team.budget -= sold_for
    offer.player.team_id = offer.ai_team_id

    offer.status = "accepted"
    offer.current_offer = sold_for
    offer.updated_at = datetime.utcnow()


def _build_response(offer: models.AIBuyoutOffer) -> dict:
    return {
        "id": offer.id,
        "player_id": offer.player_id,
        "ai_team_id": offer.ai_team_id,
        "current_offer": offer.current_offer,
        "initial_offer": offer.initial_offer,
        "rounds": offer.rounds,
        "status": offer.status,
        "player_name": offer.player.player if offer.player else "Unknown",
        "ai_team_name": offer.ai_team.name if offer.ai_team else "Unknown",
        "ai_team_ranking": offer.ai_team.ranking if offer.ai_team else None,
        "created_at": offer.created_at,
        "updated_at": offer.updated_at,
    }


@router.post("/generate")
def generate_ai_buyout_offers(db: Session = Depends(get_db)):
    manager = db.query(models.Manager).first()
    if not manager or not manager.team_id:
        return {"message": "No active manager or team — nothing to do", "generated": 0}

    manager_team_id = manager.team_id
    manager_players = db.query(models.Player).filter(models.Player.team_id == manager_team_id).all()
    if not manager_players:
        return {"message": "Manager's team has no players", "generated": 0}

    already_pending_player_ids = {
        row.player_id
        for row in db.query(models.AIBuyoutOffer.player_id).filter(models.AIBuyoutOffer.status == "pending").all()
    }

    ai_teams = db.query(models.Team).filter(models.Team.id != manager_team_id).all()

    generated = 0
    for ai_team in ai_teams:
        if random.random() > 0.30:
            continue

        ai_budget = ai_team.budget or 0
        affordable_targets = [
            player for player in manager_players
            if player.id not in already_pending_player_ids
            and player.price is not None
            and player.price <= ai_budget * 1.2
        ]

        if not affordable_targets:
            continue

        target = max(affordable_targets, key=lambda player: player.Rating or 0)
        multiplier = round(random.uniform(1.0, 1.3), 2)
        initial_offer = int(target.price * multiplier)

        new_offer = models.AIBuyoutOffer(
            player_id=target.id,
            ai_team_id=ai_team.id,
            current_offer=initial_offer,
            initial_offer=initial_offer,
            rounds=0,
            status="pending",
        )
        db.add(new_offer)
        already_pending_player_ids.add(target.id)
        generated += 1

    db.commit()
    return {"message": f"Generated {generated} AI buyout offer(s)", "generated": generated}


@router.get("/pending", response_model=List[AIBuyoutOfferResponse])
def get_pending_offers(db: Session = Depends(get_db)):
    offers = db.query(models.AIBuyoutOffer).filter(models.AIBuyoutOffer.status == "pending").order_by(models.AIBuyoutOffer.created_at.desc()).all()
    return [_build_response(offer) for offer in offers]


@router.post("/{offer_id}/accept", response_model=AIBuyoutOfferResponse)
def accept_offer(offer_id: int, db: Session = Depends(get_db)):
    offer = db.query(models.AIBuyoutOffer).filter(models.AIBuyoutOffer.id == offer_id).first()
    if not offer or offer.status != "pending":
        raise HTTPException(status_code=404, detail="Offer not found or already closed")

    _execute_sale(db, offer, offer.current_offer)
    db.commit()
    db.refresh(offer)
    return _build_response(offer)


@router.post("/{offer_id}/reject", response_model=AIBuyoutOfferResponse)
def reject_offer(offer_id: int, db: Session = Depends(get_db)):
    offer = db.query(models.AIBuyoutOffer).filter(models.AIBuyoutOffer.id == offer_id).first()
    if not offer or offer.status != "pending":
        raise HTTPException(status_code=404, detail="Offer not found or already closed")

    offer.status = "rejected"
    offer.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(offer)
    return _build_response(offer)


@router.post("/{offer_id}/counter", response_model=AIBuyoutOfferResponse)
def counter_offer(offer_id: int, body: CounterOfferBody, db: Session = Depends(get_db)):
    offer = db.query(models.AIBuyoutOffer).filter(models.AIBuyoutOffer.id == offer_id).first()
    if not offer or offer.status != "pending":
        raise HTTPException(status_code=404, detail="Offer not found or already closed")

    ai_ceiling = int(offer.initial_offer * AI_CEILING_MULTIPLIER)
    user_ask = body.counter_amount

    if user_ask <= 0:
        raise HTTPException(status_code=400, detail="Counter amount must be positive")

    offer.rounds += 1

    if user_ask <= ai_ceiling:
        _execute_sale(db, offer, user_ask)
    elif offer.rounds >= MAX_ROUNDS:
        offer.status = "collapsed"
        offer.updated_at = datetime.utcnow()
    else:
        raise_pct = random.uniform(0.10, 0.25)
        new_ai_offer = min(int(offer.current_offer * (1 + raise_pct)), ai_ceiling)
        offer.current_offer = new_ai_offer
        offer.updated_at = datetime.utcnow()
        if new_ai_offer >= user_ask:
            _execute_sale(db, offer, new_ai_offer)

    db.commit()
    db.refresh(offer)
    return _build_response(offer)
