from pydantic import BaseModel
from typing import Optional

from app.api.schemas.team_schema import TeamResponse


class ManagerCreate(BaseModel):
    name: str


class ManagerResponse(BaseModel):
    id: int
    name: str
    team_id: Optional[int] = None
    budget: int
    career_points: int

    class Config:
        from_attributes = True


class GameStatus(BaseModel):
    manager: ManagerResponse
    team: Optional[TeamResponse] = None

    class Config:
        from_attributes = True
