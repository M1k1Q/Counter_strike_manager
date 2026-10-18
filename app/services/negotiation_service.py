from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.services.transfer_service import TransferService, ensure_transfers_unlocked


class NegotiationService:
    def __init__(self, db: Session):
        self.db = db
        self.transfer_service = TransferService(db)

    def start_negotiation(self, negotiation_data, manager: models.Manager) -> models.Negotiation:
        player = self.db.query(models.Player).filter(models.Player.id == negotiation_data.player_id).first()
        if not player or not player.team_id:
            raise HTTPException(status_code=400, detail="Player must be on another team")

        source_team = self.db.query(models.Team).filter(models.Team.id == player.team_id).first()
        if not source_team:
            raise HTTPException(status_code=404, detail="Source team not found")
        ensure_transfers_unlocked(self.db, source_team.id, manager.team_id)

        if manager.budget < negotiation_data.offer_amount:
            raise HTTPException(status_code=400, detail="Offer exceeds current budget")

        new_negotiation = models.Negotiation(
            player_id=player.id,
            source_team_id=source_team.id,
            target_team_id=manager.team_id,
            manager_id=manager.id,
            offer_amount=negotiation_data.offer_amount,
        )
        new_negotiation.player = player
        new_negotiation.source_team = source_team
        new_negotiation.target_team = self.db.query(models.Team).filter(models.Team.id == manager.team_id).first()
        new_negotiation.manager = manager
        new_negotiation.calculate_success()

        if self._some_acceptance_check(new_negotiation):
            new_negotiation.status = "accepted"
            self.transfer_service.complete_transfer(player, new_negotiation.target_team_id, negotiation_data.offer_amount, manager, source_team)
        elif new_negotiation.is_untouchable or new_negotiation.success_chance < 10.0:
            new_negotiation.status = "rejected"

        self.db.add(new_negotiation)
        self.db.commit()
        self.db.refresh(new_negotiation)
        return new_negotiation

    def make_offer(self, negotiation_id: int, offer_data, manager: models.Manager) -> models.Negotiation:
        negotiation = self.db.query(models.Negotiation).filter(models.Negotiation.id == negotiation_id).first()
        if not negotiation or negotiation.status != "pending":
            raise HTTPException(status_code=404, detail="Negotiation not found or closed")

        ensure_transfers_unlocked(
            self.db,
            negotiation.source_team_id,
            negotiation.target_team_id,
            manager.team_id,
        )

        if negotiation.manager.budget < offer_data.offer_amount:
            raise HTTPException(status_code=400, detail="Offer exceeds current budget")

        negotiation.offer_amount = offer_data.offer_amount
        negotiation.rounds += 1
        negotiation.calculate_success()

        if self._some_acceptance_check(negotiation):
            negotiation.status = "accepted"
            self.transfer_service.complete_transfer(negotiation.player, negotiation.target_team_id, offer_data.offer_amount, manager, negotiation.source_team)
        elif negotiation.is_untouchable or negotiation.rounds >= 3 or negotiation.success_chance < 10.0:
            negotiation.status = "rejected"

        self.db.commit()
        self.db.refresh(negotiation)
        return negotiation

    def _some_acceptance_check(self, negotiation: models.Negotiation) -> bool:
        if negotiation.is_untouchable:
            return False

        if negotiation.success_chance >= 75:
            return True

        offer_ratio = negotiation.offer_amount / max(negotiation.player.price, 1) if negotiation.player else 1.0
        source_rank = negotiation.source_team.ranking if negotiation.source_team and negotiation.source_team.ranking else 50

        if source_rank <= 5 and offer_ratio >= 2.0 and negotiation.success_chance >= 40:
            return True
        if source_rank <= 10 and offer_ratio >= 1.5 and negotiation.success_chance >= 45:
            return True
        if source_rank > 10 and offer_ratio >= 1.2 and negotiation.success_chance >= 50:
            return True

        return False
