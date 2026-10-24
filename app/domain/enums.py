from enum import Enum


class NegotiationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    COLLAPSED = "collapsed"

class MatchFormats(str, Enum):
    Bo1 = "Bo1"
    Bo3 = "Bo3"
    Bo5 = "Bo5"

    @classmethod
    def get_best_of_count(cls, value: str) -> int:
        """Return the odd integer count X for a BoX format, defaulting to 1."""
        if not value:
            return 1
        cleaned = value.strip().lower()
        if cleaned.startswith("bo"):
            try:
                num = int(cleaned[2:])
                if num > 0 and num % 2 == 1:
                    return num
            except ValueError:
                pass
        return 1

    @classmethod
    def get_maps_to_win(cls, value: str) -> int:
        """Returns the number of map wins needed in a best-of-X series."""
        count = cls.get_best_of_count(value)
        return (count + 1) // 2


class TournamentTier(str, Enum):
    MAJOR = "Major"
    S_TIER = "S-Tier"
    A_TIER = "A-Tier"
    B_TIER = "B-Tier"
    C_TIER = "C-Tier"


class TournamentStatus(str, Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"


class MatchStage(str, Enum):
    GROUP_STAGE = "group_stage"
    ROUND_OF_16 = "round_of_16"
    QUARTER_FINAL = "quarter_final"
    SEMI_FINAL = "semi_final"
    GRAND_FINAL = "grand_final"


class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
