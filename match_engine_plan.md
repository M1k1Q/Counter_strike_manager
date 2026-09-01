# Match Engine Plan

## Goal

Build a lightweight match prediction system where a user-selected team can play against AI-controlled teams. The first version should focus on:

- opponent selection
- match format selection: BO1, BO3, BO5
- predicted match result
- predicted map scores
- CS-style score rules: first to 13 in regulation, overtime at 13-13, overtime win condition first to 4 in the overtime stage

This should be implemented as a skeleton first, so the stat formulas and decision logic are clear and easy to expand later.

---

## 1) Domain model

Keep the simulation logic separate from the current manager/transfer code and database models.

### Domain enum

The match format enum belongs in the domain layer, not in the API schema layer.

Recommended location:
- app/domain/enums.py

Example:

```python
from enum import Enum


class MatchFormat(str, Enum):
    BO1 = "BO1"
    BO3 = "BO3"
    BO5 = "BO5"
```

This is domain logic because it defines the rules of the game format, not the shape of an HTTP request or response.

---

## 2) Data structures to add

### 2.1 TeamStats

This is a domain value object used to represent a team before a prediction is made.

Purpose:
- store team identity
- hold player stat inputs
- hold role profile and ranking data
- provide a place to compute team power

Example skeleton:

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TeamStats:
    team_id: int
    team_name: str
    player_ratings: List[float] = field(default_factory=list)
    role_profile: Dict[str, float] = field(default_factory=dict)
    ranking: Optional[int] = None

    def compute_team_power(self) -> float:
        """
        Placeholder for future stat weighting.
        Example: combine average player rating, role strength, and ranking.
        """
        raise NotImplementedError("Implement team power calculation here.")

    def get_map_advantage(self, opponent: "TeamStats") -> float:
        """
        Placeholder for future map-level comparison logic.
        Positive means this team is favored.
        """
        raise NotImplementedError("Implement map advantage calculation here.")
```

This is the main skeleton for later stat work. The formula should be filled in by the project owner once the actual team-rating philosophy is decided.

---

### 2.2 MapResult

Represents the outcome of a single map.

Purpose:
- map winner
- final score
- whether overtime occurred

Example:

```python
from dataclasses import dataclass


@dataclass
class MapResult:
    winner: str
    score: str
    overtime: bool = False
```

This is the smallest prediction unit in the match engine.

---

### 2.3 SeriesResult

Represents the result of an entire best-of series.

Purpose:
- winner of the series
- final series score
- map-by-map results
- predicted win probability

Example:

```python
from dataclasses import dataclass, field
from typing import List


@dataclass
class SeriesResult:
    winner: str
    series_score: str
    map_results: List[MapResult] = field(default_factory=list)
    win_probability: float = 0.0
```

This is the domain-level representation of BO1/BO3/BO5 predictions.

---

### 2.4 MatchPrediction

This is an API-facing output object rather than a pure domain object.

Purpose:
- shape the response sent to the frontend
- provide a clean JSON contract for the match UI

Example:

```python
from pydantic import BaseModel
from typing import List


class MapPredictionResponse(BaseModel):
    winner: str
    score: str
    overtime: bool = False


class MatchPredictionResponse(BaseModel):
    winner: str
    series_score: str
    map_results: List[MapPredictionResponse]
    win_probability: float
```

This lives under the API schema layer, not the domain layer.

---

## 3) Match decision engine skeleton

The main service layer should hold the actual prediction logic. A service is the proper place for this because it keeps the API route thin and the domain logic testable.

Example skeleton:

```python
from dataclasses import dataclass


@dataclass
class MatchDecisionEngine:
    best_of: int

    def predict_map(self, home: TeamStats, away: TeamStats) -> MapResult:
        """
        Placeholder: predict a single map.
        Later this should compute a power difference,
        generate a scoreline, and handle overtime rules.
        """
        raise NotImplementedError("Implement map prediction here.")

    def predict_series(self, home: TeamStats, away: TeamStats) -> SeriesResult:
        """
        Placeholder: simulate BO1/BO3/BO5 series.
        Later this should loop through maps until a team reaches the series target.
        """
        raise NotImplementedError("Implement series prediction here.")
```

This keeps the logic intentionally simple and open-ended for future tuning.

---

## 4) Match format rules for the MVP

### BO1
- single map only
- first team to 13 in regulation
- if 13-13, overtime triggers

### BO3
- first team to 2 map wins
- maps continue until one team wins 2 maps

### BO5
- first team to 3 map wins
- maps continue until one team wins 3 maps

### Overtime rules
- regulation ends at 13-13
- overtime is an added mini series
- first to 4 wins the overtime stage
- if overtime itself is tied, continue with the chosen extended overtime format later

This is the initial CS-style rule set you described.

---

## 5) Implementation order

1. Create domain enum: MatchFormat
2. Add TeamStats domain skeleton
3. Add MapResult and SeriesResult domain objects
4. Add MatchDecisionEngine skeleton
5. Create API request/response models for prediction
6. Add match service route under the game API
7. Add opponent selection and format selector in the frontend
8. Fill in stat formulas and map prediction logic later

---

## 6) Where the logic should live

### Domain layer
- MatchFormat enum
- TeamStats
- MapResult
- SeriesResult

### Service layer
- MatchDecisionEngine
- match simulation orchestration
- map generation and series loop

### API/schema layer
- prediction request body
- prediction response body

### Database layer
- do not put match simulation logic here
- only use stored teams and player data as inputs

---

## 7) Important design note

The match engine should be a simulation prediction layer, not a full instant replay engine.

For v1, we are not trying to simulate every round, economy, buy phase, or player-level frag distribution. We are trying to answer:

- who is more likely to win?
- what series score is likely?
- what does a map score look like?

This is the right MVP for the project at this stage.

---

## 8) Summary

The key idea is:

- MatchFormat belongs in the domain layer
- TeamStats, MapResult, and SeriesResult are domain objects
- MatchPrediction is the API-facing response schema
- MatchDecisionEngine is the service that does the prediction work

This keeps everything modular and lets you fill in the actual stat math later without rewriting the structure.
