from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal, Optional


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
    Rating: int = Field(default=70, ge=70, le=99)
    is_active_roster: bool = False
    selected_role: Optional[str] = None
    age: int = Field(default=20, ge=16, le=60)
    potential: Optional[int] = Field(default=None, ge=0, le=99)
    form: float = 1.0
    last_trained_year: Optional[int] = None
    last_trained_month: Optional[int] = None


class PlayerCreate(PlayerBase):
    team_id: Optional[int] = None


class PlayerResponse(PlayerBase):
    @field_validator("role", "selected_role", mode="before")
    @classmethod
    def separate_igl_from_role(cls, value):
        from app.domain.player_roles import base_role
        return base_role(value)

    id: int
    team_id: Optional[int] = None
    price: int = 0
    is_transfer_listed: bool = False
    training_form_bonus: float = 0.0
    training_points_used: float = 0.0

    class Config:
        from_attributes = True


class PlayerTrainingRequest(BaseModel):
    stat: Literal[
        "firepower",
        "entrying",
        "opening",
        "clutching",
        "sniping",
        "trading",
        "utility",
        "impact",
    ]


class UserTeamYearlyPlayerRatingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    team_id: int
    team_name: str
    player_id: int
    player_name: str
    maps_played: int
    rating: float
    potential: int
