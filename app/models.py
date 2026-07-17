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

    def calculate_success(self):
        rounds = self.rounds if self.rounds is not None else 0
        base = (self.player.Rating or self.player.overall_rating or 1.0) * 10
        team_penalty = max(0, (self.source_team.ranking or 50) - 50) * 0.3
        round_penalty = rounds * 5
        chance = max(5, min(95, base - team_penalty - round_penalty))
        self.rounds = rounds
        self.success_chance = chance
        return chance

    def is_affordable(self):
        return self.manager.budget >= self.offer_amount
    
