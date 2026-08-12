from pydantic import BaseModel
from typing import List, Optional

from app.api.schemas.player_schema import PlayerResponse


class TeamCreate(BaseModel):
    name: str
    ranking: Optional[int] = None


class TeamRosterUpdate(BaseModel):
    active_player_ids: List[int]


class TeamResponse(TeamCreate):
    id: int
    players: List[PlayerResponse] = []

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
