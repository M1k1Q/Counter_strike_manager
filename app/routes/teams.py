from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas, database
from app.routes.roster import analyze_roster

router = APIRouter()

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/teams" , response_model=schemas.TeamResponse)
def create_team(team: schemas.TeamCreate, db: Session = Depends(get_db)):
    db_team = models.Team(**team.model_dump())
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team  

@router.get("/teams", response_model=List[schemas.TeamResponse])
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

@router.get("/teams/{team_id}/needs", response_model=schemas.TeamNeedsResponse)
def get_team_needs(team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team_analysis = analyze_roster(team, db)
    roles_count = team_analysis["roles_count"]
    
    standard_roles = ["entry", "support", "awper", "lurker", "igl"]
    missing_roles = [role for role in standard_roles if roles_count.get(role, 0) == 0]
    
    assigned_igl = None
    for p in team.players:
        if p.is_igl:
            assigned_igl = p.player
            break
            
    roster_status = "complete" if len(team.players) >= 5 and not missing_roles else "incomplete"
    
    return {
        "team_id": team.id,
        "team_name": team.name,
        "roster_status": roster_status,
        "roles_count": roles_count,
        "missing_roles": missing_roles,
        "assigned_igl": assigned_igl
    }

@router.get("/teams/{team_id}/needs/candidates", response_model=List[schemas.PlayerResponse])
def get_team_needs_candidates(team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
        
    team_analysis = analyze_roster(team, db)
    roles_count = team_analysis["roles_count"]
    
    standard_roles = ["entry", "support", "awper", "lurker", "igl"]
    missing_roles = [role for role in standard_roles if roles_count.get(role, 0) == 0]
    
    # Get all players not in this team
    other_players = db.query(models.Player).filter(
        (models.Player.team_id != team_id) | (models.Player.team_id == None)
    ).all()
    
    # Prioritize those that match missing roles
    # We will score them: 1 if their primary role is in missing_roles, 0 otherwise
    # and sort by this score descending, then by overall rating descending
    def sort_key(p):
        role = (p.role or "unknown").lower()
        matches_missing = any(m in role for m in missing_roles)
        # If the missing role is IGL, we can also check if they are an IGL candidate
        if "igl" in missing_roles and "igl" in role:
            matches_missing = True
            
        rating = p.overall_rating or 0.0
        return (1 if matches_missing else 0, rating)
        
    candidates = sorted(other_players, key=sort_key, reverse=True)
    return candidates