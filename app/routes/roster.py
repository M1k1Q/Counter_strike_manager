from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app import models, schemas, database

router = APIRouter()

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def normalize_role(role: str) -> str:
    if not role:
        return "unknown"
    role = role.lower().strip()
    if "entry" in role:
        return "entry"
    elif "support" in role:
        return "support"
    elif "awper" in role:
        return "awper"
    elif "lurker" in role:
        return "lurker"
    return "unknown"

def analyze_roster(team: models.Team, db: Session) -> dict:
    roles_count = {"entry": 0, "support": 0, "awper": 0, "lurker": 0, "igl": 0, "unknown": 0}
    for p in team.players:
        if p.is_igl:
            roles_count["igl"] += 1
        
        n_role = normalize_role(p.role)
        if n_role in roles_count:
            roles_count[n_role] += 1
            
    return {
        "team_name": team.name,
        "team_id": team.id,
        "roles_count": roles_count
    }

def select_IGL(team: models.Team, db: Session):
    players = team.players 
    if not players:
        return None
        
    max_score = float('-inf')
    best_igl = None
    
    for p in players:
        p.is_igl = False
        score = p.igl_score or 0.0
        if score > max_score:
            max_score = score
            best_igl = p
            
    if best_igl:
        best_igl.is_igl = True
        
        # Ensure role reflects IGL
        current_role = best_igl.role or ""
        if "igl" not in current_role.lower():
            best_igl.role = f"{current_role} igl".strip()
            
    db.commit()
    return best_igl

@router.get("/teams/{team_id}/roster/analyze", response_model=schemas.RoleCountResponse)
def analyze_team_roster(team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return analyze_roster(team, db)

@router.post("/teams/{team_id}/roster/auto_igl", response_model=schemas.AutoIGLResponse)
def auto_select_igl(team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
        
    best_igl = select_IGL(team, db)
    if not best_igl:
        raise HTTPException(status_code=400, detail="Team has no players to select as IGL")
        
    return {"message": f"Player {best_igl.player} selected as IGL", "player_id": best_igl.id, "igl_score": best_igl.igl_score}

@router.get("/teams/{team_id}/roster/candidates", response_model=List[schemas.CandidateSummaryResponse])
def get_igl_candidates(team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
        
    players = team.players
    if not players:
        return []
        
    max_score = float('-inf')
    best_igl = None
    for p in players:
        score = p.igl_score or 0.0
        if score > max_score:
            max_score = score
            best_igl = p

    candidates = []
    for p in players:
        candidates.append({
            "player_name": p.player,
            "role": p.role or "unknown",
            "igl_score": p.igl_score or 0.0,
            "confidence": p.confidence or 0.0,
            "is_best_igl": (p == best_igl)
        })
        
    # Sort candidates by IGL score descending
    candidates.sort(key=lambda x: x["igl_score"], reverse=True)
    return candidates
