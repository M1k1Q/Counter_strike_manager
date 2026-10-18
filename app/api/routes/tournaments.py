from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.tournament_service import TournamentService
from app.services.match_engine import MatchEngine
from app.api.schemas.tournament_schema import (
    CalendarStateResponse,
    TournamentDetailResponse,
    TournamentSummaryResponse,
    MatchResponse,
    MapResultResponse,
    PlayerStatSummary,
    TournamentParticipantResponse,
    TeamRankingResponse,
    TournamentStatsResponse,
    YearEndTop20Response,
)

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


def _build_match_response(m: models.Match) -> MatchResponse:
    maps_data = []
    for map_res in m.maps:
        stats_data = []
        for stat in map_res.player_stats:
            stats_data.append(
                PlayerStatSummary(
                    player_id=stat.player_id,
                    player_name=stat.player.player if stat.player else "Unknown",
                    role=stat.player.selected_role or stat.player.role if stat.player else None,
                    team_id=stat.team_id,
                    team_name=stat.team.name if stat.team else "Unknown",
                    kills=stat.kills,
                    deaths=stat.deaths,
                    assists=stat.assists,
                    adr=stat.adr,
                    rating=stat.rating,
                    is_mvp=stat.is_mvp,
                )
            )

        # Sort stats by rating/kills descending
        stats_data.sort(key=lambda s: (s.kills, s.rating), reverse=True)

        maps_data.append(
            MapResultResponse(
                id=map_res.id,
                map_number=map_res.map_number,
                map_name=map_res.map_name,
                team1_score=map_res.team1_score,
                team2_score=map_res.team2_score,
                overtime=map_res.overtime,
                winner_id=map_res.winner_id,
                winner_name=map_res.winner.name if map_res.winner else None,
                player_stats=stats_data,
            )
        )

    return MatchResponse(
        id=m.id,
        tournament_id=m.tournament_id,
        stage=m.stage,
        group_name=m.group_name,
        round_name=m.round_name,
        team1_id=m.team1_id,
        team1_name=m.team1.name if m.team1 else "Team 1",
        team1_rank=m.team1.ranking if m.team1 else None,
        team2_id=m.team2_id,
        team2_name=m.team2.name if m.team2 else "Team 2",
        team2_rank=m.team2.ranking if m.team2 else None,
        format=m.format,
        status=m.status,
        winner_id=m.winner_id,
        winner_name=m.winner.name if m.winner else None,
        team1_score=m.team1_score,
        team2_score=m.team2_score,
        maps=maps_data,
    )


def _build_tournament_detail(t: models.Tournament, db: Session) -> TournamentDetailResponse:
    manager = db.query(models.Manager).first()
    user_team = manager.team if (manager and manager.team) else None

    # Participants
    part_list = []
    for p in t.participants:
        part_list.append(
            TournamentParticipantResponse(
                id=p.id,
                team_id=p.team_id,
                team_name=p.team.name if p.team else "Unknown",
                team_rank=p.team.ranking if p.team else None,
                seed=p.seed,
                group_name=p.group_name,
                wins=p.wins,
                losses=p.losses,
                rounds_won=p.rounds_won,
                rounds_lost=p.rounds_lost,
                round_diff=p.rounds_won - p.rounds_lost,
                eliminated=p.eliminated,
                placement=p.placement,
            )
        )

    # Sort participants by seed
    part_list.sort(key=lambda p: p.seed)

    # Matches
    match_list = [_build_match_response(m) for m in t.matches]

    invite_check = TournamentService(db).check_invite_status(t, user_team)

    return TournamentDetailResponse(
        id=t.id,
        name=t.name,
        tier=t.tier,
        prize_pool=t.prize_pool,
        year=t.year,
        month=t.month,
        status=t.status,
        min_rank_required=t.min_rank_required,
        format=t.format,
        champion_id=t.champion_id,
        champion_name=t.champion.name if t.champion else None,
        participants=part_list,
        matches=match_list,
        is_manager_invited=invite_check["invited"],
        is_manager_participating=bool(
            user_team and any(participant.team_id == user_team.id for participant in t.participants)
        ),
        manager_invite_reason=invite_check["reason"],
    )


@router.get("/calendar", response_model=CalendarStateResponse)
def get_calendar(db: Session = Depends(get_db)):
    svc = TournamentService(db)
    state = svc.get_or_create_calendar_state()

    manager = db.query(models.Manager).first()
    season_tournaments = (
        db.query(models.Tournament)
        .filter(models.Tournament.year == state.current_year)
        .order_by(models.Tournament.month.asc(), models.Tournament.prize_pool.desc())
        .all()
    )

    season_summaries = [
        TournamentSummaryResponse(
            id=t.id,
            name=t.name,
            tier=t.tier,
            prize_pool=t.prize_pool,
            year=t.year,
            month=t.month,
            status=t.status,
            min_rank_required=t.min_rank_required,
            format=t.format,
            champion_id=t.champion_id,
            champion_name=t.champion.name if t.champion else None,
        )
        for t in season_tournaments
    ]

    active_detail = None
    if state.active_tournament:
        if not state.tournament_start_pending and not state.active_tournament.participants:
            svc.initialize_tournament(state.active_tournament.id)
        active_detail = _build_tournament_detail(state.active_tournament, db)

    return CalendarStateResponse(
        current_year=state.current_year,
        current_month=state.current_month,
        active_tournament_id=state.active_tournament_id,
        tournament_start_pending=state.tournament_start_pending,
        active_tournament=active_detail,
        season_tournaments=season_summaries,
        manager_team_rank=manager.team.ranking if (manager and manager.team) else None,
        manager_budget=manager.budget if manager else 1_000_000,
        manager_career_points=manager.career_points if manager else 0,
    )


@router.post("/calendar/advance", response_model=CalendarStateResponse)
def advance_calendar(db: Session = Depends(get_db)):
    svc = TournamentService(db)
    try:
        svc.advance_calendar()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return get_calendar(db)


@router.post("/calendar/start", response_model=CalendarStateResponse)
def start_current_month_tournaments(db: Session = Depends(get_db)):
    svc = TournamentService(db)
    try:
        svc.start_current_month_tournaments()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return get_calendar(db)


@router.get("/history", response_model=List[TournamentSummaryResponse])
def get_tournament_history(db: Session = Depends(get_db)):
    tournaments = (
        db.query(models.Tournament)
        .filter(models.Tournament.status == "completed")
        .order_by(models.Tournament.year.desc(), models.Tournament.month.desc())
        .all()
    )
    return [
        TournamentSummaryResponse(
            id=t.id,
            name=t.name,
            tier=t.tier,
            prize_pool=t.prize_pool,
            year=t.year,
            month=t.month,
            status=t.status,
            min_rank_required=t.min_rank_required,
            format=t.format,
            champion_id=t.champion_id,
            champion_name=t.champion.name if t.champion else None,
        )
        for t in tournaments
    ]


@router.get("/yearly-top-20", response_model=List[YearEndTop20Response])
def get_yearly_top_20(db: Session = Depends(get_db)):
    return TournamentService(db).get_year_end_top_20()


@router.get("/{tournament_id}", response_model=TournamentDetailResponse)
def get_tournament_detail(tournament_id: int, db: Session = Depends(get_db)):
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    state = db.query(models.CalendarState).first()
    is_pending_current_event = bool(
        state
        and state.tournament_start_pending
        and state.active_tournament_id == tournament_id
    )
    if (
        tournament.status == "active"
        and not tournament.participants
        and not is_pending_current_event
    ):
        TournamentService(db).initialize_tournament(tournament_id)

    return _build_tournament_detail(tournament, db)


@router.get("/{tournament_id}/stats", response_model=TournamentStatsResponse)
def get_tournament_stats(tournament_id: int, db: Session = Depends(get_db)):
    svc = TournamentService(db)
    try:
        return svc.get_tournament_stats(tournament_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{tournament_id}/initialize", response_model=TournamentDetailResponse)
def initialize_tournament(tournament_id: int, db: Session = Depends(get_db)):
    svc = TournamentService(db)
    tournament = svc.initialize_tournament(tournament_id)
    return _build_tournament_detail(tournament, db)


@router.post("/matches/{match_id}/simulate", response_model=MatchResponse)
def simulate_match(match_id: int, db: Session = Depends(get_db)):
    svc = TournamentService(db)
    try:
        match = svc.play_match(match_id)
        return _build_match_response(match)
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 409
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{tournament_id}/simulate-ai-round")
def simulate_ai_round(tournament_id: int, db: Session = Depends(get_db)):
    svc = TournamentService(db)
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if tournament.status == "completed":
        raise HTTPException(status_code=409, detail="Tournament is already completed")

    try:
        count = svc.simulate_all_ai_matches(tournament_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"message": f"Simulated {count} AI matches", "count": count}


@router.get("/matches/{match_id}", response_model=MatchResponse)
def get_match_detail(match_id: int, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return _build_match_response(match)


@router.get("/rankings/global", response_model=List[TeamRankingResponse])
def get_global_rankings(db: Session = Depends(get_db)):
    manager = db.query(models.Manager).first()
    user_team_id = manager.team_id if manager else None

    teams = db.query(models.Team).order_by(models.Team.ranking.asc()).all()
    return [
        TeamRankingResponse(
            id=t.id,
            name=t.name,
            ranking=t.ranking,
            ranking_points=t.ranking_points or 0,
            is_user_team=(t.id == user_team_id),
        )
        for t in teams
    ]
