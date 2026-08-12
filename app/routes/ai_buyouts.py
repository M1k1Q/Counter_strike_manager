"""
AI Buyout Offers
================
AI teams can proactively target players on the human manager's squad.

Flow
----
1. POST /ai-buyouts/generate
       → Scans all AI teams, picks affordable targets on the user's roster,
         creates pending AIBuyoutOffer rows.  Call this after every match week
         or from the frontend on game load.

2. GET  /ai-buyouts/pending
       → Returns all pending offers the user needs to respond to.

3. POST /ai-buyouts/{offer_id}/accept
       → User sells; money credited, player transferred.

4. POST /ai-buyouts/{offer_id}/reject
       → User declines; offer is closed (status = rejected).

5. POST /ai-buyouts/{offer_id}/counter
       → User submits a higher price.  AI evaluates and either:
             • accepts  (user price ≤ AI ceiling = 2.5× initial_offer)
             • raises   (AI counter, up to the ceiling)
             • collapses (AI ceiling already reached)
"""

import random
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app import models
from app.database import get_db


router = APIRouter(prefix="/ai-buyouts", tags=["ai-buyouts"])

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

#helpers

MAX_ROUNDS = 3
AI_CEILING_MULTIPLIER = 2.5   # AI will never go above initial_offer × this


def _execute_sale(db: Session, offer: models.AIBuyoutOffer, sold_for: int) -> None:
    """Transfer the player and update budgets."""
    manager = db.query(models.Manager).first()
    if not manager:
        raise HTTPException(status_code=404, detail="No active manager")

    offer.player.team_id = None          # player becomes a free agent first …
    offer.player.is_active_roster = False
    manager.budget += sold_for           # user receives the money
    offer.ai_team.budget -= sold_for     # AI pays

    # Now move the player to the AI team
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


#endpoints

@router.post("/generate")
def generate_ai_buyout_offers(db: Session = Depends(get_db)):
    """
    STILL A WIP
    Scans every AI team and potentially create a buyout offer for a player on the user's roster.  
    Existing pending offers for the same player are not duplicated.
    """
    manager = db.query(models.Manager).first()
    if not manager or not manager.team_id:
        return {"message": "No active manager or team — nothing to do", "generated": 0}

    manager_team_id = manager.team_id

    # Players the manager currently owns
    manager_players = (
        db.query(models.Player)
        .filter(models.Player.team_id == manager_team_id)
        .all()
    )
    if not manager_players:
        return {"message": "Manager's team has no players", "generated": 0}

    # avoid spam
    already_pending_player_ids = {
        row.player_id
        for row in db.query(models.AIBuyoutOffer.player_id)
        .filter(models.AIBuyoutOffer.status == "pending")
        .all()
    }

    # All AI teams
    ai_teams = db.query(models.Team).filter(models.Team.id != manager_team_id).all()

    generated = 0
    for ai_team in ai_teams:
        # Each AI team has a 30 % chance of scouting the user's squad each call
        if random.random() > 0.30:
            continue

        ai_budget = ai_team.budget or 0

        # Find a player on the manager's team that this AI team can (almost) afford.
        # "Almost" = can afford at 1.2× player price to make the offer realistic.
        affordable_targets = [
            p for p in manager_players
            if p.id not in already_pending_player_ids
            and p.price is not None
            and p.price <= ai_budget * 1.2   # AI will stretch a bit over base price
        ]

        if not affordable_targets:
            continue

        # Pick the highest-rated affordable target
        target = max(affordable_targets, key=lambda p: p.Rating or 0)

        # Initial offer = player's market price × a random multiplier (1.0–1.3)
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
        already_pending_player_ids.add(target.id)  # prevent two teams from targeting same player in one sweep
        generated += 1

    db.commit()
    return {"message": f"Generated {generated} AI buyout offer(s)", "generated": generated}


@router.get("/pending", response_model=List[AIBuyoutOfferResponse])
def get_pending_offers(db: Session = Depends(get_db)):
    """Return all buyout offers that are still pending user action."""
    offers = (
        db.query(models.AIBuyoutOffer)
        .filter(models.AIBuyoutOffer.status == "pending")
        .order_by(models.AIBuyoutOffer.created_at.desc())
        .all()
    )
    return [_build_response(o) for o in offers]


@router.post("/{offer_id}/accept", response_model=AIBuyoutOfferResponse)
def accept_offer(offer_id: int, db: Session = Depends(get_db)):
    """User accepts the AI's current offer. Player is sold immediately."""
    offer = db.query(models.AIBuyoutOffer).filter(models.AIBuyoutOffer.id == offer_id).first()
    if not offer or offer.status != "pending":
        raise HTTPException(status_code=404, detail="Offer not found or already closed")

    _execute_sale(db, offer, offer.current_offer)
    db.commit()
    db.refresh(offer)
    return _build_response(offer)


@router.post("/{offer_id}/reject", response_model=AIBuyoutOfferResponse)
def reject_offer(offer_id: int, db: Session = Depends(get_db)):
    """User rejects the AI offer. Offer is closed — AI may try again later."""
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
    """
    User submits a counter-offer (higher asking price).
    AI evaluates:
      • counter ≤ AI ceiling (2.5× initial)  →  AI accepts
      • counter > AI ceiling AND rounds < MAX_ROUNDS  →  AI raises its offer (10–25 %)
      • counter > AI ceiling AND rounds >= MAX_ROUNDS  →  negotiation collapses
    """
    offer = db.query(models.AIBuyoutOffer).filter(models.AIBuyoutOffer.id == offer_id).first()
    if not offer or offer.status != "pending":
        raise HTTPException(status_code=404, detail="Offer not found or already closed")

    ai_ceiling = int(offer.initial_offer * AI_CEILING_MULTIPLIER)
    user_ask = body.counter_amount

    if user_ask <= 0:
        raise HTTPException(status_code=400, detail="Counter amount must be positive")

    offer.rounds += 1

    if user_ask <= ai_ceiling:
        # AI accepts the user's price
        _execute_sale(db, offer, user_ask)
    elif offer.rounds >= MAX_ROUNDS:
        # AI has already stretched as far as it can — walk away
        offer.status = "collapsed"
        offer.updated_at = datetime.utcnow()
    else:
        # AI raises its offer toward the ceiling
        raise_pct = random.uniform(0.10, 0.25)
        new_ai_offer = min(int(offer.current_offer * (1 + raise_pct)), ai_ceiling)
        offer.current_offer = new_ai_offer
        offer.updated_at = datetime.utcnow()
        # If the AI's new offer already meets or exceeds what the user asked, auto-accept
        if new_ai_offer >= user_ask:
            _execute_sale(db, offer, new_ai_offer)

    db.commit()
    db.refresh(offer)
    return _build_response(offer)
