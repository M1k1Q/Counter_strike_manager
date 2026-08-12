from typing import Optional
from sqlalchemy.orm import Session

from app import models


class PlayerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, player_id: int) -> Optional[models.Player]:
        return self.db.query(models.Player).filter(models.Player.id == player_id).first()

    def get_all(self):
        return self.db.query(models.Player).all()

    def get_by_team(self, team_id: int):
        return self.db.query(models.Player).filter(models.Player.team_id == team_id).all()

    def get_free_agents(self):
        return self.db.query(models.Player).filter(models.Player.team_id.is_(None)).all()
