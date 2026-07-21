from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class PlayerBase(BaseModel):
    player:         str
    ct_rating:      Optional[float] = None
    t_rating:       Optional[float] = None
    overall_rating: Optional[float] = None
    clutching:      Optional[float] = None
    entrying:       Optional[float] = None
    firepower:      Optional[float] = None
    impact:         Optional[float] = None
    opening:        Optional[float] = None
    sniping:        Optional[float] = None
    trading:        Optional[float] = None
    utility:        Optional[float] = None
    role:           Optional[str]   = None
    confidence:     float           = 0.0
    igl_score:      float           = 0.0
    is_igl:         bool            = False
    Rating:         int             = 0


class PlayerCreate(PlayerBase):
    team_id: Optional[int] = None


class PlayerResponse(PlayerBase):
    id:      int
    team_id: Optional[int] = None
    price:   int = 0

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------

class TeamCreate(BaseModel):
    name:    str
    ranking: Optional[int] = None


class TeamResponse(TeamCreate):
    id: int
    players: List[PlayerResponse] = []

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class ManagerCreate(BaseModel):
    name: str


class ManagerResponse(BaseModel):
    id:            int
    name:          str
    team_id:       Optional[int] = None
    budget:        int
    career_points: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------

class GameStatus(BaseModel):
    manager: ManagerResponse
    team:    Optional[TeamResponse] = None


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

