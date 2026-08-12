from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NegotiationBase(BaseModel):
    player_id: int
    target_team_id: int
    offer_amount: int
    message: Optional[str] = None


class NegotiationCreate(NegotiationBase):
    pass


class NegotiationOffer(BaseModel):
    offer_amount: int
    message: Optional[str] = None


class NegotiationResponse(NegotiationBase):
    id: int
    source_team_id: int
    manager_id: int
    status: str
    success_chance: float
    rounds: int
    status_explanation: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
