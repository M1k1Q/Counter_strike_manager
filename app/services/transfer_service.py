from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models

MAX_AI_ROSTER_SIZE = 5
ACTIVE_TOURNAMENT_STATUS = "active"


def active_tournament_team_ids(db: Session) -> set[int]:
    return {
        team_id
        for (team_id,) in (
            db.query(models.TournamentParticipant.team_id)
            .join(
                models.Tournament,
                models.Tournament.id == models.TournamentParticipant.tournament_id,
            )
            .filter(models.Tournament.status == ACTIVE_TOURNAMENT_STATUS)
            .distinct()
            .all()
        )
    }


def transfer_lock_name(db: Session, *team_ids: int | None) -> str | None:
    relevant_team_ids = {team_id for team_id in team_ids if team_id is not None}
    if not relevant_team_ids:
        return None

    locked_tournament = (
        db.query(models.Tournament.name)
        .join(
            models.TournamentParticipant,
            models.TournamentParticipant.tournament_id == models.Tournament.id,
        )
        .filter(
            models.Tournament.status == ACTIVE_TOURNAMENT_STATUS,
            models.TournamentParticipant.team_id.in_(relevant_team_ids),
        )
        .order_by(models.Tournament.year.desc(), models.Tournament.month.desc())
        .first()
    )
    return locked_tournament[0] if locked_tournament else None


def ensure_transfers_unlocked(db: Session, *team_ids: int | None) -> None:
    event_name = transfer_lock_name(db, *team_ids)
    if event_name:
        raise HTTPException(
            status_code=409,
            detail=f"Transfers are locked for teams participating in {event_name}.",
        )


def withdraw_pending_buyout_offers(db: Session, player_id: int) -> None:
    pending_offers = db.query(models.AIBuyoutOffer).filter(
        models.AIBuyoutOffer.player_id == player_id,
        models.AIBuyoutOffer.status == "pending",
    ).all()
    for offer in pending_offers:
        offer.status = "withdrawn"
        offer.updated_at = datetime.utcnow()


def _normalize_role(role: str | None) -> str | None:
    if not role:
        return None
    lowered = role.lower()
    for position in ("awper", "entry", "support", "lurker"):
        if position in lowered:
            return position
    return None


def _player_role(player: models.Player) -> str | None:
    return _normalize_role(player.selected_role) or _normalize_role(player.role)


def _release_ai_roster_slot(db: Session, team: models.Team, incoming_player: models.Player) -> None:
    roster = db.query(models.Player).filter(models.Player.team_id == team.id).all()
    incoming_role = _player_role(incoming_player)
    while len(roster) >= MAX_AI_ROSTER_SIZE:
        same_role = [
            player for player in roster
            if incoming_role and _player_role(player) == incoming_role
        ]
        release_pool = same_role or roster
        released = min(release_pool, key=lambda player: (player.Rating or 0, player.id))
        released.team_id = None
        released.is_active_roster = False
        released.is_igl = False
        roster.remove(released)


def add_player_to_ai_roster(db: Session, team: models.Team, player: models.Player) -> None:
    _release_ai_roster_slot(db, team, player)
    player.team_id = team.id
    player.is_active_roster = False
    player.is_transfer_listed = False
    db.flush()


def reconcile_ai_rosters(db: Session) -> int:
    """Fill under-strength AI rosters when the career loads."""
    manager = db.query(models.Manager).first()
    manager_team_id = manager.team_id if manager else None
    teams_query = db.query(models.Team)
    if manager_team_id is not None:
        teams_query = teams_query.filter(models.Team.id != manager_team_id)
    teams = teams_query.order_by(models.Team.ranking.asc()).all()
    repaired = 0

    for team in teams:
        if transfer_lock_name(db, team.id):
            continue

        while True:
            roster = db.query(models.Player).filter(models.Player.team_id == team.id).all()
            if len(roster) >= MAX_AI_ROSTER_SIZE:
                break

            occupied_roles = {_player_role(player) for player in roster}
            preferred_role = next(
                (role for role in ("awper", "entry", "support", "lurker") if role not in occupied_roles),
                None,
            )
            candidate = _find_candidate(
                db,
                team,
                None,
                manager_team_id,
                preferred_role=preferred_role,
                prefer_free_agents=True,
            )
            if candidate is None:
                break

            transfer_fee = candidate.price
            add_player_to_ai_roster(db, team, candidate)
            team.budget -= transfer_fee
            repaired += 1

    db.commit()
    return repaired


class TransferService:
    def __init__(self, db: Session):
        self.db = db

    def complete_transfer(
        self,
        player: models.Player,
        target_team_id: int,
        offer_amount: int,
        manager: models.Manager,
        source_team: models.Team,
    ) -> None:
        ensure_transfers_unlocked(self.db, source_team.id, target_team_id)
        player.team_id = target_team_id
        player.is_active_roster = False
        player.is_transfer_listed = False
        withdraw_pending_buyout_offers(self.db, player.id)
        source_team.budget += offer_amount
        manager.budget -= offer_amount
        self.db.flush()
        handle_ai_replacement(self.db, source_team.id, player.id)


def handle_ai_replacement(
    db: Session,
    team_id: int,
    lost_player_id: int,
) -> None:
    """Replace a lost AI player with a role-compatible free agent, without poaching."""
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    lost_player = db.query(models.Player).filter(models.Player.id == lost_player_id).first()
    if not team or not lost_player:
        return
    if transfer_lock_name(db, team.id):
        return

    manager = db.query(models.Manager).first()
    manager_team_id = manager.team_id if manager else None
    candidate = _find_candidate(
        db,
        team,
        lost_player,
        manager_team_id,
        preferred_role=_player_role(lost_player),
        prefer_free_agents=True,
    )
    if candidate is None:
        return

    transfer_fee = candidate.price
    add_player_to_ai_roster(db, team, candidate)
    team.budget -= transfer_fee


def _find_candidate(
    db: Session,
    buying_team: models.Team,
    lost_player: models.Player | None,
    manager_team_id: int | None,
    excluded_team_ids: frozenset[int] = frozenset(),
    preferred_role: str | None = None,
    prefer_free_agents: bool = False,
) -> models.Player | None:
    locked_team_ids = active_tournament_team_ids(db)
    available_query = db.query(models.Player).filter(
        (models.Player.team_id.is_(None)) | (models.Player.team_id != buying_team.id),
    )
    if locked_team_ids:
        available_query = available_query.filter(
            (models.Player.team_id.is_(None))
            | (~models.Player.team_id.in_(locked_team_ids))
        )
    if lost_player is not None:
        available_query = available_query.filter(models.Player.id != lost_player.id)
    if manager_team_id is not None:
        available_query = available_query.filter(
            (models.Player.team_id.is_(None)) | (models.Player.team_id != manager_team_id)
        )
    candidates = [
        player for player in available_query.all()
        if player.team_id is None or player.team_id not in excluded_team_ids
    ]

    affordable = [
        player for player in candidates
        if player.price <= (buying_team.budget or 0)
    ]
    if not affordable:
        return None
    if prefer_free_agents:
        free_agents = [player for player in affordable if player.team_id is None]
        if not free_agents:
            return None
        affordable = free_agents

    lost_role = preferred_role
    if lost_role is None and lost_player is not None:
        lost_role = _player_role(lost_player)
    role_fits = [
        player for player in affordable
        if lost_role and _player_role(player) == lost_role
    ]
    if role_fits:
        return max(role_fits, key=lambda player: (player.team_id is None, player.Rating or 0))

    return max(
        affordable,
        key=lambda player: (
            player.team_id is None,
            player.Rating or 0,
        ),
    )
