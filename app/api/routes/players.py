from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app import models
from app.api.schemas.player_schema import (
    PlayerCreate,
    PlayerResponse,
    PlayerTrainingRequest,
    UserTeamYearlyPlayerRatingResponse,
)
from app.database import get_db
from app.services.player_development_service import train_player, train_player_form
from app.services.transfer_service import (
    ensure_transfers_unlocked,
    withdraw_pending_buyout_offers,
)

router = APIRouter()


@router.post("/players", response_model=PlayerResponse)
def create_player(player: PlayerCreate, db: Session = Depends(get_db)):
    payload = player.model_dump()
    overall_rating = payload.get("overall_rating")
    if overall_rating is None:
        overall_rating = 0.0

    payload.pop("overall_rating", None)
    payload.pop("team_id", None)
    payload["potential"] = max(payload["Rating"], payload.get("potential") or payload["Rating"])

    db_player = models.Player(**payload, overall_rating=overall_rating)
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player


@router.get("/players", response_model=List[PlayerResponse])
def get_players(db: Session = Depends(get_db)):
    return db.query(models.Player).all()


@router.get(
    "/players/development/yearly-ratings",
    response_model=List[UserTeamYearlyPlayerRatingResponse],
)
def get_user_team_yearly_ratings(db: Session = Depends(get_db)):
    manager = db.query(models.Manager).first()
    if not manager or not manager.team_id:
        raise HTTPException(status_code=409, detail="Start a career and select a team to view yearly ratings")

    return (
        db.query(models.UserTeamYearlyPlayerRating)
        .order_by(
            models.UserTeamYearlyPlayerRating.year.desc(),
            models.UserTeamYearlyPlayerRating.rating.desc(),
            models.UserTeamYearlyPlayerRating.player_name.asc(),
        )
        .all()
    )


@router.post("/players/{player_id}/transfer-list", response_model=PlayerResponse)
def list_player_for_transfer(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    manager = db.query(models.Manager).first()
    if not manager or not manager.team_id:
        raise HTTPException(status_code=409, detail="Start a career and select a team before listing players")
    if player.team_id != manager.team_id:
        raise HTTPException(status_code=403, detail="You can only list players on your team")

    ensure_transfers_unlocked(db, manager.team_id)
    player.is_transfer_listed = True
    db.commit()
    db.refresh(player)
    return player


@router.delete("/players/{player_id}/transfer-list", response_model=PlayerResponse)
def remove_player_from_transfer_list(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    manager = db.query(models.Manager).first()
    if not manager or not manager.team_id:
        raise HTTPException(status_code=409, detail="Start a career and select a team before managing transfer listings")
    if player.team_id != manager.team_id:
        raise HTTPException(status_code=403, detail="You can only manage listings for players on your team")

    player.is_transfer_listed = False
    withdraw_pending_buyout_offers(db, player.id)

    db.commit()
    db.refresh(player)
    return player


@router.post("/players/{player_id}/train", response_model=PlayerResponse)
def train_owned_player(
    player_id: int,
    request: PlayerTrainingRequest,
    db: Session = Depends(get_db),
):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    manager = db.query(models.Manager).first()
    if not manager or not manager.team_id:
        raise HTTPException(status_code=409, detail="Start a career and select a team before training players")
    if player.team_id != manager.team_id:
        raise HTTPException(status_code=403, detail="You can only train players on your team")

    teams = db.query(models.Team).all()
    max_rank: int = int(
        max(
            (int(team.ranking) for team in teams if team.ranking is not None),
            default=16,
        )
    )
    team = db.query(models.Team).filter(models.Team.id == player.team_id).first()
    team_rank = int(team.ranking) if team and team.ranking is not None else None
    calendar_state = db.query(models.CalendarState).first()
    if not calendar_state:
        calendar_state = models.CalendarState(
            current_year=2026,
            current_month=1,
            manager_id=manager.id,
        )
        db.add(calendar_state)
        db.flush()
    try:
        train_player(
            player=player,
            stat=request.stat,
            team_rank=team_rank,
            max_rank=max_rank,
            year=calendar_state.current_year,
            month=calendar_state.current_month,
            role_population=db.query(models.Player).all(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.commit()
    db.refresh(player)
    return player


@router.post("/players/{player_id}/form-train", response_model=PlayerResponse)
def train_owned_player_form(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    manager = db.query(models.Manager).first()
    if not manager or not manager.team_id:
        raise HTTPException(status_code=409, detail="Start a career and select a team before training players")
    if player.team_id != manager.team_id:
        raise HTTPException(status_code=403, detail="You can only train players on your team")

    try:
        train_player_form(player)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.commit()
    db.refresh(player)
    return player
