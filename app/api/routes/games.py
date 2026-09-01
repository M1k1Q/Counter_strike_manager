from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.api.schemas.manager_schema import ManagerCreate, ManagerResponse, GameStatus
from app.api.schemas.team_schema import TeamCreate
from app.database import get_db
from app.repositories.game_repository import GameRepository

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/start", response_model=ManagerResponse)
def start_career(manager: ManagerCreate, db: Session = Depends(get_db)):
    game_repository = GameRepository(db)
    manager_record = game_repository.get_manager()
    if manager_record:
        db.query(models.Manager).delete()
    return game_repository.create_manager(manager.name)


@router.get("/status", response_model=GameStatus)
def get_game_status(db: Session = Depends(get_db)):
    manager = db.query(models.Manager).first()
    if not manager:
        raise HTTPException(status_code=404, detail="No active career found")

    return {"manager": manager, "team": manager.team}


@router.post("/select-team/{team_id}", response_model=ManagerResponse)
def select_team(team_id: int, db: Session = Depends(get_db)):
    manager = db.query(models.Manager).first()
    if not manager:
        raise HTTPException(status_code=404, detail="No active career found")

    team = db.query(models.Team).filter(models.Team.id == team_id).first    ()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    manager.team_id = team_id
    db.commit()
    db.refresh(manager)
    return manager


@router.post("/create-team", response_model=ManagerResponse)
def create_custom_team(team_data: TeamCreate, db: Session = Depends(get_db)):
    manager = db.query(models.Manager).first()
    if not manager:
        raise HTTPException(status_code=404, detail="No active career found")

    new_team = models.Team(name=team_data.name, ranking=99)
    db.add(new_team)
    db.commit()
    db.refresh(new_team)

    manager.team_id = new_team.id
    db.commit()
    db.refresh(manager)
    return manager
