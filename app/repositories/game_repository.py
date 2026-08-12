from sqlalchemy.orm import Session

from app import models


class GameRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_manager(self) -> models.Manager | None:
        return self.db.query(models.Manager).first()

    def create_manager(self, name: str) -> models.Manager:
        manager = models.Manager(name=name, budget=1_000_000, career_points=0)
        self.db.add(manager)
        self.db.commit()
        self.db.refresh(manager)
        return manager
