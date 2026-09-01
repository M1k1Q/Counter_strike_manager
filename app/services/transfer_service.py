from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models


class TransferService:
    def __init__(self, db: Session):
        self.db = db

    def complete_transfer(self, player: models.Player, target_team_id: int, offer_amount: int, manager: models.Manager, source_team: models.Team):
        player.team_id = target_team_id
        player.is_active_roster = False
        source_team.budget += offer_amount
        manager.budget -= offer_amount
        self.db.flush()
        handle_ai_replacement(self.db, source_team.id, player.id)


def handle_ai_replacement(db: Session, team_id: int, lost_player_id: int, depth: int = 0):
    """
    Future implementation would most likely be a whole proper transfer window implementation
    along with more fine tuning of the AI teams selecting PROPER replacements

    Called after an AI team loses a player to the human manager.
    Finds a suitable replacement according to the following rules:
      - Rating within [lost_player.Rating - 5, lost_player.Rating]
      - AI team must be able to afford the replacement (budget check)
      - Prioritise Free Agents; top-10 teams may also target top-10–20 teams
      - If the best candidate is on the human manager's team, skip (buyout system handles it)
      - Cascade up to depth 2 if the replacement comes from another AI team
    """
    if depth >= 2:
        return

    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    lost_player = db.query(models.Player).filter(models.Player.id == lost_player_id).first()

    if not team or not lost_player:
        return

    lost_rating = lost_player.Rating or 0
    if lost_rating == 0:
        return

    min_rating = lost_rating - 5
    max_rating = lost_rating

    # Identify the human manager's team to skip its players
    manager = db.query(models.Manager).first()
    manager_team_id = manager.team_id if manager else None

    candidate = _find_candidate(db, team, min_rating, max_rating, manager_team_id)

    # Expand search window if no match found
    if candidate is None:
        candidate = _find_candidate(db, team, min_rating - 3, max_rating, manager_team_id)

    if candidate is None:
        return  # No affordable replacement found — team plays short

    former_team_id = candidate.team_id  # None if free agent

    # Execute the transfer
    candidate.team_id = team.id
    candidate.is_active_roster = False  # Will need to be set by team management
    team.budget -= candidate.price

    db.flush()  # Persist before recursion

    # If replacement came from another AI team, that team now needs a replacement too
    if former_team_id is not None and former_team_id != manager_team_id:
        former_team = db.query(models.Team).filter(models.Team.id == former_team_id).first()
        if former_team:
            # Credit the selling AI team for the implicit transfer fee (player's price)
            former_team.budget += candidate.price
            db.flush()
            handle_ai_replacement(db, former_team.id, candidate.id, depth + 1)


def _find_candidate(
    db: Session,
    buying_team: models.Team,
    min_rating: int,
    max_rating: int,
    manager_team_id: int | None,
) -> models.Player | None:
    """
    Returns the best affordable candidate in the rating window for the given team.
    Priority order:
      1. Free agents in the rating window
      2. For top-10 teams: players on teams ranked between (buying_team.ranking + 1) and 20
      3. For all other teams: players from lower-ranked AI teams
    Skips the human manager's team (buyout system handles that path).
    """
    buying_rank = buying_team.ranking or 99

    base_query = (
        db.query(models.Player)
        .filter(
            models.Player.Rating >= min_rating,
            models.Player.Rating <= max_rating,
            or_(models.Player.team_id.is_(None), models.Player.team_id != buying_team.id),
        )
    )

    # Skip human manager's team — that path goes through the buyout system
    if manager_team_id is not None:
        base_query = base_query.filter(or_(models.Player.team_id.is_(None), models.Player.team_id != manager_team_id))

    # --- Pass 1: Free Agents ---
    free_agents = (
        base_query.filter(models.Player.team_id.is_(None))
        .order_by(models.Player.Rating.desc())
        .all()
    )
    for p in free_agents:
        if p.price <= buying_team.budget:
            return p

    # --- Pass 2: Paid transfers ---
    if buying_rank <= 10:
        # Top-10 team: can target players on teams ranked buying_rank+1 to 20
        pool = (
            base_query.join(models.Team, models.Player.team_id == models.Team.id)
            .filter(
                models.Team.ranking > buying_rank,
                models.Team.ranking <= 20,
            )
            .order_by(models.Player.Rating.desc())
            .all()
        )
    else:
        # Other teams: target players on lower-ranked AI teams
        pool = (
            base_query.join(models.Team, models.Player.team_id == models.Team.id)
            .filter(models.Team.ranking > buying_rank)
            .order_by(models.Player.Rating.desc())
            .all()
        )

    for p in pool:
        if p.price <= buying_team.budget:
            return p

    return None
