import random
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.transfer_service import (
    active_tournament_team_ids,
    add_player_to_ai_roster,
    ensure_transfers_unlocked,
    ai_upgrade_target,
    transfer_role_group,
    MAX_AI_ROSTER_SIZE,
)

router = APIRouter(prefix="/ai-buyouts", tags=["ai-buyouts"])

MAX_ROUNDS = 3
AI_CEILING_MULTIPLIER = 2.5
TRANSFER_RANK_RANGE = 10
SUPERSTAR_RATING = 90
SUPERSTAR_BUYER_MAX_RANK = 15


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
    if offer.player.team_id != manager.team_id:
        raise HTTPException(status_code=409, detail="Player is no longer on your team")
    if (offer.ai_team.budget or 0) < sold_for:
        raise HTTPException(status_code=409, detail="AI team can no longer afford this offer")

    ensure_transfers_unlocked(db, manager.team_id, offer.ai_team_id)
    manager.budget += sold_for
    offer.ai_team.budget -= sold_for
    add_player_to_ai_roster(db, offer.ai_team, offer.player)
    offer.player.is_transfer_listed = False

    offer.status = "accepted"
    offer.current_offer = sold_for
    offer.updated_at = datetime.utcnow()
    competing_offers = db.query(models.AIBuyoutOffer).filter(
        models.AIBuyoutOffer.player_id == offer.player_id,
        models.AIBuyoutOffer.id != offer.id,
        models.AIBuyoutOffer.status == "pending",
    ).all()
    for competing_offer in competing_offers:
        competing_offer.status = "collapsed"
        competing_offer.updated_at = datetime.utcnow()


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
    locked_team_ids = active_tournament_team_ids(db)
    if manager_team_id in locked_team_ids:
        return {"message": "Transfers are locked during your team's active tournament", "generated": 0}

    manager_team = db.query(models.Team).filter(models.Team.id == manager_team_id).first()
    if not manager_team:
        return {"message": "Manager's team could not be found", "generated": 0}

    listed_players = db.query(models.Player).filter(
        models.Player.team_id == manager_team_id,
        models.Player.is_transfer_listed.is_(True),
    ).all()
    if not listed_players:
        return {"message": "Manager's team has no transfer-listed players", "generated": 0}

    already_pending_pairs = {
        (row.player_id, row.ai_team_id)
        for row in db.query(
            models.AIBuyoutOffer.player_id,
            models.AIBuyoutOffer.ai_team_id,
        ).filter(models.AIBuyoutOffer.status == "pending").all()
    }
    already_pending_team_ids = {team_id for _, team_id in already_pending_pairs}

    ai_teams = db.query(models.Team).filter(
        models.Team.id != manager_team_id,
        models.Team.ranking.isnot(None),
    ).all()
    rosters = {team.id: [] for team in ai_teams}
    if rosters:
        for player in db.query(models.Player).filter(models.Player.team_id.in_(list(rosters))).all():
            rosters[player.team_id].append(player)

    generated = 0
    for ai_team in ai_teams:
        if ai_team.id in locked_team_ids or ai_team.id in already_pending_team_ids:
            continue

        ai_budget = ai_team.budget or 0
        roster = rosters[ai_team.id]
        in_rank_range = manager_team.ranking is not None and abs(ai_team.ranking - manager_team.ranking) <= TRANSFER_RANK_RANGE
        affordable_targets = []
        for player in listed_players:
            group = transfer_role_group(player)
            superstar_interest = (player.Rating or 0) >= SUPERSTAR_RATING and 1 <= ai_team.ranking <= SUPERSTAR_BUYER_MAX_RANK
            if not group or (player.id, ai_team.id) in already_pending_pairs or player.price > ai_budget:
                continue
            if not in_rank_range and not superstar_interest:
                continue
            group_count = sum(transfer_role_group(incumbent) == group for incumbent in roster)
            has_vacancy = len(roster) < MAX_AI_ROSTER_SIZE and group_count < (1 if group == "awper" else 4)
            incumbent = ai_upgrade_target(roster, player)
            improves_lineup = incumbent is not None and (player.Rating or 0) > (incumbent.Rating or 0)
            if has_vacancy or (superstar_interest and improves_lineup):
                affordable_targets.append(player)

        if not affordable_targets:
            continue

        target = max(affordable_targets, key=lambda player: player.Rating or 0)
        multiplier = round(random.uniform(1.0, 1.9), 5)
        initial_offer = min(int(target.price * multiplier), ai_budget)
        
        new_offer = models.AIBuyoutOffer(
            player_id=target.id,
            ai_team_id=ai_team.id,
            current_offer=initial_offer,
            initial_offer=initial_offer,
            rounds=0,
            status="pending",
        )
        db.add(new_offer)
        already_pending_pairs.add((target.id, ai_team.id))
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

    manager = db.query(models.Manager).first()
    ensure_transfers_unlocked(db, manager.team_id if manager else None, offer.ai_team_id)

    ai_ceiling = int(offer.initial_offer * AI_CEILING_MULTIPLIER)
    ai_ceiling = min(ai_ceiling, offer.ai_team.budget or 0)
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
