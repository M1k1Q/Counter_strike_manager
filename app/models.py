from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
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

    #overall ingame rating
    Rating = Column(Integer , nullable=True)

    @property
    def price(self) -> int:
        base_price = 50_000
        
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
            
        final_price = base_price * rating_multiplier * stat_multiplier * team_multiplier
        return int(final_price)


class Team(Base):
    __tablename__ = "teams"

    id      = Column(Integer, primary_key=True, index=True)
    name    = Column(String(100), unique=True, nullable=False)
    ranking = Column(Integer, nullable=True)

    players = relationship("Player", backref="team", foreign_keys=[Player.team_id])


class Manager(Base):
    __tablename__ = "managers"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(50), nullable=False)
    team_id        = Column(Integer, ForeignKey("teams.id"), nullable=True)
    budget         = Column(Integer, default=1_000_000)
    career_points  = Column(Integer, default=0)

    team = relationship("Team")

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
        """Returns True if the player is a franchise star on a top team and offer is below top-tier threshold."""
        source_rank = self.source_team.ranking if self.source_team and self.source_team.ranking else 50
        if source_rank > 5 or not self.player:
            return False
        
        star_rating = self.player.Rating or (self.player.overall_rating * 70 if self.player.overall_rating else 75)
        if star_rating < 82:
            return False
            
        offer_ratio = self.offer_amount / max(self.player.price, 1)
        required_multiplier = 2.5 if source_rank <= 3 else 2.0
        return offer_ratio < required_multiplier

    def calculate_success(self) -> float:
        rounds = self.rounds if self.rounds is not None else 0
        source_rank = self.source_team.ranking if self.source_team and self.source_team.ranking else 50
        target_rank = self.target_team.ranking if self.target_team and self.target_team.ranking else 99
        
        base_price = max(self.player.price, 1) if self.player else 50000
        offer_ratio = self.offer_amount / base_price
        
        # 1. Minimum multiplier based on source team rank
        if source_rank <= 3:
            required_multiplier = 2.5
        elif source_rank <= 5:
            required_multiplier = 2.0
        elif source_rank <= 10:
            required_multiplier = 1.5
        else:
            required_multiplier = 1.1

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
            req_mult = 2.5 if source_rank <= 3 else 2.0
            min_val = int((self.player.price or 50000) * req_mult)
            return f"{source_name} considers {player_name} untouchable and will not entertain offers below ${min_val:,} ({req_mult}x market value)."
            
        if self.status == "rejected":
            return f"{source_name} rejected the offer for {player_name}. The offer did not meet their valuation or prestige expectations."
            
        return f"{source_name} is evaluating the offer of ${self.offer_amount:,}. Estimated acceptance chance: {self.success_chance}%."

    def get_status_explanation(self) -> str:
        return self.status_explanation

    def is_affordable(self):
        return self.manager.budget >= self.offer_amount

    
