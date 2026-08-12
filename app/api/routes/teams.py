from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app import models
from app.api.schemas.team_schema import (
    TeamCreate,
    TeamResponse,
    TeamNeedsResponse,
    TeamRosterUpdate,
    PlayerRoleUpdate,
    AutoIGLResponse,
    CandidateSummaryResponse,
    RoleCountResponse,
    PlayerResponse,
)
from app.database import get_db
from app.services.roster_service import RosterService

router = APIRouter()


@router.post("/teams", response_model=TeamResponse)
def create_team(team: TeamCreate, db: Session = Depends(get_db)):
    db_team = models.Team(**team.model_dump())
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team


@router.get("/teams", response_model=List[TeamResponse])
def get_teams(db: Session = Depends(get_db)):
    return db.query(models.Team).all()


@router.post("/teams/{team_id}/add_player/{player_id}")
def add_player_to_team(team_id: int, player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    player.team_id = team_id
    db.commit()
    return {"message": f"Player {player.player} assigned to team {team.name}"}


@router.post("/teams/{team_id}/remove_player/{player_id}")
def remove_player_from_team(team_id: int, player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    player.team_id = None
    db.commit()
    return {"message": f"Player {player.player} removed from team"}


@router.get("/teams/{team_id}/needs", response_model=TeamNeedsResponse)
def get_team_needs(team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    roster_service = RosterService(db)
    team_analysis = roster_service.analyze(team)
    roles_count = team_analysis["roles_count"]

    standard_roles = ["entry", "support", "awper", "lurker", "igl"]
    missing_roles = [role for role in standard_roles if roles_count.get(role, 0) == 0]

    assigned_igl = None
    for player in team.players:
        if player.is_igl:
            assigned_igl = player.player
            break

    roster_status = "complete" if len(team.players) >= 5 and not missing_roles else "incomplete"

    return {
        "team_id": team.id,
        "team_name": team.name,
        "roster_status": roster_status,
        "roles_count": roles_count,
        "missing_roles": missing_roles,
        "assigned_igl": assigned_igl,
    }


@router.get("/teams/{team_id}/needs/candidates", response_model=List[PlayerResponse])
def get_team_needs_candidates(team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    roster_service = RosterService(db)
    team_analysis = roster_service.analyze(team)
    roles_count = team_analysis["roles_count"]

    standard_roles = ["entry", "support", "awper", "lurker", "igl"]
    missing_roles = [role for role in standard_roles if roles_count.get(role, 0) == 0]

    other_players = db.query(models.Player).filter((models.Player.team_id != team_id) | (models.Player.team_id.is_(None))).all()

    def sort_key(player):
        role = (player.role or "unknown").lower()
        matches_missing = any(role_item in role for role_item in missing_roles)
        if "igl" in missing_roles and "igl" in role:
            matches_missing = True
        rating = player.overall_rating or 0.0
        return (1 if matches_missing else 0, rating)

    candidates = sorted(other_players, key=sort_key, reverse=True)
    return candidates


@router.get("/teams/{team_id}/roster/analyze", response_model=RoleCountResponse)
def analyze_team_roster(team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    return RosterService(db).analyze(team)


@router.post("/teams/{team_id}/roster/auto_igl", response_model=AutoIGLResponse)
def auto_select_igl(team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    best_igl = RosterService(db).select_igl(team)
    if not best_igl:
        raise HTTPException(status_code=400, detail="Team has no players to select as IGL")

    return {"message": f"Player {best_igl.player} selected as IGL", "player_id": best_igl.id, "igl_score": best_igl.igl_score}


@router.get("/teams/{team_id}/roster/candidates", response_model=List[CandidateSummaryResponse])
def get_igl_candidates(team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    players = team.players
    if not players:
        return []

    max_score = float("-inf")
    best_igl = None
    for player in players:
        score = player.igl_score or 0.0
        if score > max_score:
            max_score = score
            best_igl = player

    candidates = []
    for player in players:
        candidates.append({
            "player_name": player.player,
            "role": player.role or "unknown",
            "igl_score": player.igl_score or 0.0,
            "confidence": player.confidence or 0.0,
            "is_best_igl": (player == best_igl),
        })

    candidates.sort(key=lambda item: item["igl_score"], reverse=True)
    return candidates


@router.put("/teams/{team_id}/roster", response_model=list[PlayerResponse])
def update_active_roster(team_id: int, roster_update: TeamRosterUpdate, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    active_ids = roster_update.active_player_ids
    if len(active_ids) != 5:
        raise HTTPException(status_code=400, detail=f"A formation must have exactly 5 active players. Got {len(active_ids)}.")

    team_player_ids = {player.id for player in team.players}
    invalid_ids = [player_id for player_id in active_ids if player_id not in team_player_ids]
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"Player IDs {invalid_ids} do not belong to this team.")

    for player in team.players:
        player.is_active_roster = player.id in set(active_ids)

    db.commit()
    db.refresh(team)
    return team.players


@router.patch("/players/{player_id}/role", response_model=PlayerResponse)
def update_player_role(player_id: int, role_update: PlayerRoleUpdate, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    new_role = role_update.role
    if new_role and new_role.lower() == "igl":
        player.is_igl = True
        player.selected_role = new_role

        if player.team_id:
            other_players = db.query(models.Player).filter(models.Player.team_id == player.team_id, models.Player.id != player.id).all()
            for other_player in other_players:
                other_player.is_igl = False
    else:
        player.selected_role = new_role

    db.commit()
    db.refresh(player)
    return player
