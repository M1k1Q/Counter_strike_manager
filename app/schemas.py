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
    is_active_roster: bool = False
    selected_role: Optional[str] =None

class PlayerCreate(PlayerBase):
    team_id: Optional[int] = None


class PlayerResponse(PlayerBase):
    id:      int
    team_id: Optional[int] = None
    price:   int = 0
    is_active_roster: bool = False
    selected_role: Optional[str] =None
    
    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------

class TeamCreate(BaseModel):
    name:    str
    ranking: Optional[int] = None

class TeamRosterUpdate(BaseModel):
    active_player_ids: List[int]

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


class RoleCountResponse(BaseModel):
    team_id: int
    roles_count: dict
    team_name: str
    class Config:
        from_attributes = True

class AutoIGLResponse(BaseModel):
    message: str
    player_id: int
    igl_score: float

    class Config:
        from_attributes = True

class CandidateSummaryResponse(BaseModel):
    player_name: str
    role: str
    igl_score: float
    confidence: float
    is_best_igl: bool = False

    class Config:
        from_attributes = True

class TeamNeedsResponse(BaseModel):
    team_id: int
    team_name: str
    roster_status: str
    roles_count: dict
    missing_roles: List[str]
    assigned_igl: Optional[str] = None

    class Config:
        from_attributes = True

class PlayerRoleUpdate(BaseModel):
    role: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Auth / User Schemas
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username_or_email: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    manager_id: Optional[int] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    username: Optional[str] = None

        