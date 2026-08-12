from typing import Optional
from sqlalchemy.orm import Session

from app import models


class TeamRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, team_id: int) -> Optional[models.Team]:
        return self.db.query(models.Team).filter(models.Team.id == team_id).first()

    def get_all(self):
        return self.db.query(models.Team).all()

    def get_by_ids(self, team_ids):
        return self.db.query(models.Team).filter(models.Team.id.in_(team_ids)).all()
