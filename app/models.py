from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class Player(Base):
    __tablename__ = "players"

    id             = Column(Integer, primary_key=True, index=True)

    # Identity
    player         = Column(String(60), nullable=False)       # "Player" in CSV
    team_id        = Column(Integer, ForeignKey("teams.id"), nullable=True)

    # HLTV ratings
    ct_rating      = Column(Float, nullable=True)              # "CT Rating"
    t_rating       = Column(Float, nullable=True)              # "T Rating"
    overall_rating = Column(Float, nullable=True)              # "Overall Rating"

    # Role-skill percentiles (0–100 integers from HLTV)
    clutching      = Column(Float, nullable=True)              # "Clutching"
    entrying       = Column(Float, nullable=True)              # "Entrying"
    firepower      = Column(Float, nullable=True)              # "Firepower"
    impact         = Column(Float, nullable=True)              # "Impact"
    opening        = Column(Float, nullable=True)              # "Opening"
    sniping        = Column(Float, nullable=True)              # "Sniping"
    trading        = Column(Float, nullable=True)              # "Trading"
    utility        = Column(Float, nullable=True)              # "Utility"

    # Classifier outputs
    role           = Column(String(30), nullable=True)         # e.g. "entry igl"
    confidence     = Column(Float, default=0.0)                # 0-100 role fit %
    igl_score      = Column(Float, default=0.0)                # 0-100 IGL score
    is_igl         = Column(Boolean, default=False)            # designated team IGL?
    is_active_roster = Column(Boolean, default=False)          # true if in starting 5
    selected_role  = Column(String(30), nullable=True)         # manager-assigned role

    #overall ingame rating
    Rating = Column(Integer , nullable=True)

    @property
    def price(self) -> int:
        base_price = 200_000
        
        # 1. Rating multiplier (cubed to make higher ratings exponentially more expensive)
        # e.g., 1.0 rating -> 1x multiplier, 1.2 rating -> ~1.73x multiplier
        rating = self.overall_rating or 1.0
        rating_multiplier = max(0.1, rating) ** 3
        
        # 2. Role stats multiplier
        stats = [
            self.clutching, self.entrying, self.firepower, 
            self.impact, self.opening, self.sniping, 
            self.trading, self.utility
        ]
        valid_stats = [s for s in stats if s is not None]
        avg_stat = sum(valid_stats) / len(valid_stats) if valid_stats else 50.0
        stat_multiplier = max(0.1, avg_stat / 50.0)
        
        # 3. Team rank multiplier
        team_multiplier = 1.0
        if self.team and self.team.ranking:
            # Rank 1 -> 1.5, Rank 100 -> ~1.0
            team_multiplier = 1.0 + max(0, (100 - self.team.ranking) / 200.0)
            
        star_rating = self.Rating or 0
        star_multiplier = 1.5 if star_rating >= 90 else 1.0

        final_price = (
            base_price
            * rating_multiplier
            * stat_multiplier
            * team_multiplier
            * star_multiplier
        )
        return int(final_price)


class Team(Base):
    __tablename__ = "teams"

    id      = Column(Integer, primary_key=True, index=True)
    name    = Column(String(100), unique=True, nullable=False)
    ranking = Column(Integer, nullable=True)
    ranking_points = Column(Integer, default=0)
    budget  = Column(Integer, default=1_000_000)  # AI transfer budget

    players = relationship("Player", backref="team", foreign_keys=[Player.team_id])


class Manager(Base):
    __tablename__ = "managers"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(50), nullable=False)
    team_id        = Column(Integer, ForeignKey("teams.id"), nullable=True)
    budget         = Column(Integer, default=1_000_000)
    career_points  = Column(Integer, default=0)

    team = relationship("Team")


class DataMigration(Base):
    __tablename__ = "data_migrations"

    migration_key = Column(String(100), primary_key=True)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Negotiation(Base):
    __tablename__ = "negotiations"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    source_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    target_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    manager_id = Column(Integer, ForeignKey("managers.id"), nullable=False)

    offer_amount = Column(Integer, nullable=False)
    status = Column(String(30), default="pending")  # pending, accepted, rejected, failed
    success_chance = Column(Float, default=0.0)
    rounds = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player = relationship("Player")
    source_team = relationship("Team", foreign_keys=[source_team_id])
    target_team = relationship("Team", foreign_keys=[target_team_id])
    manager = relationship("Manager")

    @property
    def is_untouchable(self) -> bool:
        """Return whether a franchise player should reject a below-threshold offer."""
        source_rank = self.source_team.ranking if self.source_team and self.source_team.ranking else 50
        if not self.player:
            return False

        star_rating = (
            self.player.Rating
            or (self.player.overall_rating * 70 if self.player.overall_rating else 75)
        )
        if star_rating < 92 and (source_rank > 5 or star_rating < 82):
            return False

        offer_ratio = self.offer_amount / max(self.player.price, 1)
        required_multiplier = self.required_offer_multiplier
        return offer_ratio < required_multiplier

    @property
    def required_offer_multiplier(self) -> float:
        source_rank = self.source_team.ranking if self.source_team and self.source_team.ranking else 50
        star_rating = (
            self.player.Rating
            or (self.player.overall_rating * 70 if self.player.overall_rating else 75)
        ) if self.player else 0
        if star_rating >= 92:
            return 4.0
        if source_rank <= 3:
            return 2.5
        if source_rank <= 5:
            return 2.0
        if source_rank <= 10:
            return 1.5
        return 1.1

    def calculate_success(self) -> float:
        rounds = self.rounds if self.rounds is not None else 0
        source_rank = self.source_team.ranking if self.source_team and self.source_team.ranking else 50
        target_rank = self.target_team.ranking if self.target_team and self.target_team.ranking else 99
        
        base_price = max(self.player.price, 1) if self.player else 50000
        offer_ratio = self.offer_amount / base_price
        
        # 1. Minimum multiplier based on source team rank
        required_multiplier = self.required_offer_multiplier

        # 2. Check Untouchable status
        if self.is_untouchable:
            self.rounds = rounds
            self.success_chance = 0.0
            return 0.0

        # 3. Prestige gap penalty (transferring from high rank team to lower rank team)
        prestige_gap = max(0, target_rank - source_rank)
        prestige_penalty = min(35.0, prestige_gap * 0.4)

        # 4. Calculate chance based on offer ratio vs required multiplier
        ratio_performance = offer_ratio / required_multiplier
        if ratio_performance < 0.7:
            base_chance = ratio_performance * 10.0
        elif ratio_performance < 1.0:
            base_chance = 10.0 + (ratio_performance - 0.7) / 0.3 * 40.0
        else:
            base_chance = 50.0 + min(45.0, (ratio_performance - 1.0) * 35.0)

        round_penalty = rounds * 8.0
        chance = max(0.0, min(95.0, base_chance - prestige_penalty - round_penalty))
        
        self.rounds = rounds
        self.success_chance = round(chance, 1)
        return self.success_chance

    @property
    def status_explanation(self) -> str:
        source_name = self.source_team.name if self.source_team else "The selling team"
        player_name = self.player.player if self.player else "The player"
        source_rank = self.source_team.ranking if self.source_team and self.source_team.ranking else 50
        
        if self.status == "accepted":
            return f"{player_name} has accepted your offer of ${self.offer_amount:,} and joined your team!"
            
        if self.is_untouchable:
            req_mult = self.required_offer_multiplier
            min_val = int((self.player.price or 50000) * req_mult)
            return f"{source_name} considers {player_name} untouchable and will not entertain offers below ${min_val:,} ({req_mult}x market value)."
            
        if self.status == "rejected":
            return f"{source_name} rejected the offer for {player_name}. The offer did not meet their valuation or prestige expectations."
            
        return f"{source_name} is evaluating the offer of ${self.offer_amount:,}. Estimated acceptance chance: {self.success_chance}%."

    def get_status_explanation(self) -> str:
        return self.status_explanation

    def is_affordable(self):
        return self.manager.budget >= self.offer_amount


class AIBuyoutOffer(Base):
    """An AI team's proactive offer to buy a player from the human manager's team."""
    __tablename__ = "ai_buyout_offers"

    id             = Column(Integer, primary_key=True, index=True)
    player_id      = Column(Integer, ForeignKey("players.id"), nullable=False)
    ai_team_id     = Column(Integer, ForeignKey("teams.id"), nullable=False)

    # Current offer the AI is putting on the table
    current_offer  = Column(Integer, nullable=False)
    # Original offer when the negotiation started (used to cap AI raises)
    initial_offer  = Column(Integer, nullable=False)
    # How many counter-offer rounds have happened
    rounds         = Column(Integer, default=0)

    # pending | accepted | rejected | collapsed
    status         = Column(String(20), default="pending")

    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player   = relationship("Player")
    ai_team  = relationship("Team", foreign_keys=[ai_team_id])


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, index=True, nullable=False)
    email           = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active       = Column(Boolean, default=True)
    is_admin        = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=datetime.utcnow)

    manager_id      = Column(Integer, ForeignKey("managers.id"), nullable=True)
    manager         = relationship("Manager")


class Tournament(Base):
    __tablename__ = "tournaments"

    id                 = Column(Integer, primary_key=True, index=True)
    name               = Column(String(100), nullable=False)
    tier               = Column(String(30), default="S-Tier")  # Major, S-Tier, A-Tier
    prize_pool         = Column(Integer, default=500_000)
    year               = Column(Integer, default=2026)
    month              = Column(Integer, default=1)
    status             = Column(String(30), default="upcoming")  # upcoming, active, completed
    min_rank_required  = Column(Integer, default=8)  # top N teams invited
    format             = Column(String(20), default="Bo3")   # Bo1, Bo3, Bo5
    champion_id        = Column(Integer, ForeignKey("teams.id"), nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)

    champion     = relationship("Team", foreign_keys=[champion_id])
    participants = relationship("TournamentParticipant", back_populates="tournament", cascade="all, delete-orphan")
    matches      = relationship("Match", back_populates="tournament", cascade="all, delete-orphan")


class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"

    id            = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    team_id       = Column(Integer, ForeignKey("teams.id"), nullable=False)
    seed          = Column(Integer, nullable=False)
    group_name    = Column(String(10), nullable=True)  # "A", "B", "C", or "D"
    wins          = Column(Integer, default=0)
    losses        = Column(Integer, default=0)
    rounds_won    = Column(Integer, default=0)
    rounds_lost   = Column(Integer, default=0)
    eliminated    = Column(Boolean, default=False)
    placement     = Column(String(50), nullable=True)  # "Champion", "Runner-Up", "Semifinalist", "Group Stage"

    tournament = relationship("Tournament", back_populates="participants")
    team       = relationship("Team")


class Match(Base):
    __tablename__ = "matches"

    id            = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=True)
    stage         = Column(String(30), default="group_stage")  # group_stage, semi_final, grand_final
    group_name    = Column(String(10), nullable=True)          # "A"-"D" for group-stage matches
    round_name    = Column(String(50), nullable=True)          # e.g. "Group A - Round 1", "Semi-Final 1"
    team1_id      = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team2_id      = Column(Integer, ForeignKey("teams.id"), nullable=False)
    format        = Column(String(10), default="Bo3")          # Bo1, Bo3, Bo5
    status        = Column(String(30), default="scheduled")    # scheduled, in_progress, completed
    winner_id     = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team1_score   = Column(Integer, default=0)                 # Maps won by team 1
    team2_score   = Column(Integer, default=0)                 # Maps won by team 2
    created_at    = Column(DateTime, default=datetime.utcnow)

    tournament   = relationship("Tournament", back_populates="matches")
    team1        = relationship("Team", foreign_keys=[team1_id])
    team2        = relationship("Team", foreign_keys=[team2_id])
    winner       = relationship("Team", foreign_keys=[winner_id])
    maps         = relationship("MapResult", back_populates="match", cascade="all, delete-orphan")
    player_stats = relationship("PlayerMatchStat", back_populates="match", cascade="all, delete-orphan")


class MapResult(Base):
    __tablename__ = "map_results"

    id          = Column(Integer, primary_key=True, index=True)
    match_id    = Column(Integer, ForeignKey("matches.id"), nullable=False)
    map_number  = Column(Integer, default=1)
    map_name    = Column(String(50), nullable=False)
    team1_score = Column(Integer, default=0)  # rounds won
    team2_score = Column(Integer, default=0)  # rounds won
    overtime    = Column(Boolean, default=False)
    winner_id   = Column(Integer, ForeignKey("teams.id"), nullable=True)

    match        = relationship("Match", back_populates="maps")
    winner       = relationship("Team", foreign_keys=[winner_id])
    player_stats = relationship("PlayerMatchStat", back_populates="map_result", cascade="all, delete-orphan")


class PlayerMatchStat(Base):
    __tablename__ = "player_match_stats"

    id            = Column(Integer, primary_key=True, index=True)
    match_id      = Column(Integer, ForeignKey("matches.id"), nullable=False)
    map_result_id = Column(Integer, ForeignKey("map_results.id"), nullable=True)
    player_id     = Column(Integer, ForeignKey("players.id"), nullable=False)
    team_id       = Column(Integer, ForeignKey("teams.id"), nullable=False)

    kills   = Column(Integer, default=0)
    deaths  = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    adr     = Column(Float, default=0.0)
    rating  = Column(Float, default=1.0)
    is_mvp  = Column(Boolean, default=False)

    match      = relationship("Match", back_populates="player_stats")
    map_result = relationship("MapResult", back_populates="player_stats")
    player     = relationship("Player")
    team       = relationship("Team")


class CalendarState(Base):
    __tablename__ = "calendar_states"

    id                   = Column(Integer, primary_key=True, index=True)
    current_year         = Column(Integer, default=2026)
    current_month        = Column(Integer, default=1)
    manager_id           = Column(Integer, ForeignKey("managers.id"), nullable=True)
    active_tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=True)
    tournament_start_pending = Column(Boolean, default=False, nullable=False)

    manager           = relationship("Manager")
    active_tournament = relationship("Tournament", foreign_keys=[active_tournament_id])


class TournamentPlayerStatArchive(Base):
    __tablename__ = "tournament_player_stat_archives"
    __table_args__ = (
        UniqueConstraint("tournament_id", "player_id", name="uq_tournament_player_stat_archive"),
    )

    id            = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False, index=True)
    player_id     = Column(Integer, nullable=False)
    player_name   = Column(String(60), nullable=False)
    team_id       = Column(Integer, nullable=False)
    team_name     = Column(String(100), nullable=False)
    role          = Column(String(30), nullable=True)
    maps_played   = Column(Integer, nullable=False)
    kills         = Column(Integer, nullable=False)
    deaths        = Column(Integer, nullable=False)
    assists       = Column(Integer, nullable=False)
    kd_diff       = Column(Integer, nullable=False)
    kd_ratio      = Column(Float, nullable=False)
    adr           = Column(Float, nullable=False)
    rating        = Column(Float, nullable=False)
    reached_playoffs = Column(Boolean, nullable=False)
    is_finalist   = Column(Boolean, nullable=False)
    placement     = Column(String(50), nullable=True)
    award         = Column(String(20), nullable=True)


class YearEndPlayerArchive(Base):
    __tablename__ = "year_end_player_archives"
    __table_args__ = (
        UniqueConstraint("year", "player_id", name="uq_year_end_player_archive"),
    )

    id          = Column(Integer, primary_key=True, index=True)
    year        = Column(Integer, nullable=False, index=True)
    rank        = Column(Integer, nullable=False)
    player_id   = Column(Integer, nullable=False)
    player_name = Column(String(60), nullable=False)
    team_name   = Column(String(100), nullable=False)
    role        = Column(String(30), nullable=True)
    maps_played = Column(Integer, nullable=False)
    kills       = Column(Integer, nullable=False)
    deaths      = Column(Integer, nullable=False)
    assists     = Column(Integer, nullable=False)
    kd_diff     = Column(Integer, nullable=False)
    kd_ratio    = Column(Float, nullable=False)
    adr         = Column(Float, nullable=False)
    rating      = Column(Float, nullable=False)
    mvp_count   = Column(Integer, nullable=False)
    evp_count   = Column(Integer, nullable=False)
