from pydantic import BaseModel
from typing import Optional


class PlayerBase(BaseModel):
    player: str
    ct_rating: Optional[float] = None
    t_rating: Optional[float] = None
    overall_rating: Optional[float] = None
    clutching: Optional[float] = None
    entrying: Optional[float] = None
    firepower: Optional[float] = None
    impact: Optional[float] = None
    opening: Optional[float] = None
    sniping: Optional[float] = None
    trading: Optional[float] = None
    utility: Optional[float] = None
    role: Optional[str] = None
    confidence: float = 0.0
    igl_score: float = 0.0
    is_igl: bool = False
    Rating: int = 0
    is_active_roster: bool = False
    selected_role: Optional[str] = None


class PlayerCreate(PlayerBase):
    team_id: Optional[int] = None


class PlayerResponse(PlayerBase):
    id: int
    team_id: Optional[int] = None
    price: int = 0

    class Config:
        from_attributes = True
