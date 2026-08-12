from typing import List
from sqlalchemy.orm import Session

from app import models


class AIService:
    def __init__(self, db: Session):
        self.db = db

    def get_pending_buyouts(self):
        return self.db.query(models.AIBuyoutOffer).filter(models.AIBuyoutOffer.status == "pending").all()

    def generate_buyout_offers(self, manager: models.Manager) -> int:
        return 0
