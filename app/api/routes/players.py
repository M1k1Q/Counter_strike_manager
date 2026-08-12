from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app import models
from app.api.schemas.player_schema import PlayerCreate, PlayerResponse
from app.database import get_db

router = APIRouter()


@router.post("/players", response_model=PlayerResponse)
def create_player(player: PlayerCreate, db: Session = Depends(get_db)):
    payload = player.model_dump()
    overall_rating = payload.get("overall_rating")
    if overall_rating is None:
        overall_rating = 0.0

    payload.pop("overall_rating", None)
    payload.pop("team_id", None)

    db_player = models.Player(**payload, overall_rating=overall_rating)
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player


@router.get("/players", response_model=List[PlayerResponse])
def get_players(db: Session = Depends(get_db)):
    return db.query(models.Player).all()
