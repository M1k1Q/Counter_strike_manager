from sqlalchemy.orm import Session

from app import models
from app.routes.ai_transfers import handle_ai_replacement


class TransferService:
    def __init__(self, db: Session):
        self.db = db

    def complete_transfer(self, player: models.Player, target_team_id: int, offer_amount: int, manager: models.Manager, source_team: models.Team):
        player.team_id = target_team_id
        player.is_active_roster = False
        source_team.budget += offer_amount
        manager.budget -= offer_amount
        self.db.flush()
        handle_ai_replacement(self.db, source_team.id, player.id)
