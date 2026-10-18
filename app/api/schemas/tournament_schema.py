from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PlayerStatSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    player_name: str
    role: Optional[str] = None
    team_id: int
    team_name: str
    kills: int
    deaths: int
    assists: int
    adr: float
    rating: float
    is_mvp: bool


class MapResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    map_number: int
    map_name: str
    team1_score: int
    team2_score: int
    overtime: bool
    winner_id: Optional[int] = None
    winner_name: Optional[str] = None
    player_stats: List[PlayerStatSummary] = []


class MatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tournament_id: Optional[int] = None
    stage: str
    group_name: Optional[str] = None
    round_name: Optional[str] = None
    team1_id: int
    team1_name: str
    team1_rank: Optional[int] = None
    team2_id: int
    team2_name: str
    team2_rank: Optional[int] = None
    format: str
    status: str
    winner_id: Optional[int] = None
    winner_name: Optional[str] = None
    team1_score: int
    team2_score: int
    maps: List[MapResultResponse] = []


class TournamentParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    team_name: str
    team_rank: Optional[int] = None
    seed: int
    group_name: Optional[str] = None
    wins: int
    losses: int
    rounds_won: int
    rounds_lost: int
    round_diff: int
    eliminated: bool
    placement: Optional[str] = None


class TournamentSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tier: str
    prize_pool: int
    year: int
    month: int
    status: str
    min_rank_required: int
    format: str
    champion_id: Optional[int] = None
    champion_name: Optional[str] = None


class TournamentDetailResponse(TournamentSummaryResponse):
    participants: List[TournamentParticipantResponse] = []
    matches: List[MatchResponse] = []
    is_manager_invited: bool = False
    is_manager_participating: bool = False
    manager_invite_reason: str = ""


class CalendarStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_year: int
    current_month: int
    active_tournament_id: Optional[int] = None
    tournament_start_pending: bool = False
    active_tournament: Optional[TournamentDetailResponse] = None
    season_tournaments: List[TournamentSummaryResponse] = []
    manager_team_rank: Optional[int] = None
    manager_budget: int = 1_000_000
    manager_career_points: int = 0


class TeamRankingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ranking: Optional[int] = None
    ranking_points: int = 0
    is_user_team: bool = False


class EventPlayerStat(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    player_name: str
    team_id: int
    team_name: str
    role: Optional[str] = None
    maps_played: int
    kills: int
    deaths: int
    assists: int
    kd_diff: int
    kd_ratio: float
    adr: float
    rating: float
    reached_playoffs: bool = False
    is_finalist: bool = False
    placement: Optional[str] = None
    award: Optional[str] = None  # "MVP", "EVP #1", "EVP #2", etc.


class TournamentStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tournament_id: int
    tournament_name: str
    is_completed: bool
    mvp: Optional[EventPlayerStat] = None
    evps: List[EventPlayerStat] = []
    player_stats: List[EventPlayerStat] = []


class YearEndEventHonor(BaseModel):
    event_name: str
    month: int
    award: str
    event_rating: float
    placement: Optional[str] = None


class YearEndPlayerStat(BaseModel):
    rank: int
    player_id: int
    player_name: str
    team_name: str
    role: Optional[str] = None
    maps_played: int
    kills: int
    deaths: int
    assists: int
    kd_diff: int
    kd_ratio: float
    adr: float
    rating: float
    mvp_count: int
    evp_count: int
    honors: List[YearEndEventHonor] = Field(default_factory=list)


class YearEndTop20Response(BaseModel):
    year: int
    players: List[YearEndPlayerStat] = Field(default_factory=list)
