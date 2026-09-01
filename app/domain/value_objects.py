from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlayerSummary:
    id: int
    name: str
    team_id: Optional[int]
    rating: Optional[int]
    price: int