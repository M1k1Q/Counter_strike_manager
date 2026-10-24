import math
import os
import sys
import pandas as pd
import numpy as np

# Allow running directly or as module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# 1. Role-stat weight tables
# ---------------------------------------------------------------------------
ROLE_WEIGHTS: dict[str, dict[str, float]] = {
    "awper": {
        "Sniping":   0.35,
        "Clutching": 0.20,
        "Opening":   0.15,
        "Firepower": 0.15,
        "Impact":    0.15,
    },
    "entry": {
        "Entrying":  0.35,
        "Opening":   0.25,
        "Firepower": 0.20,
        "Impact":    0.20,
    },
    "lurker": {
        "Clutching": 0.30,
        "Trading":   0.20,
        "Firepower": 0.30,
        "Impact":    0.10,
        "Opening":   0.10,
    },
    "support": {
        "Utility":   0.35,
        "Trading":   0.20,
        "Impact":    0.20,
        "Clutching": 0.15,
        "Entrying":  0.10,
    },
    # Dynamic IGL Calling Style weight mappings
    "support igl": {
        "Utility":   0.35,
        "Trading":   0.20,
        "Impact":    0.15,
        "Clutching": 0.15,
        "Opening":   0.15,
    },
    "entry igl": {
        "Utility":   0.20,
        "Entrying":  0.30,
        "Opening":   0.20,
        "Impact":    0.15,
        "Firepower": 0.15,
    },
    "lurker igl": {
        "Utility":   0.25,
        "Clutching": 0.25,
        "Trading":   0.20,
        "Firepower": 0.15,
        "Impact":    0.15,
    },
    "awper igl": {
        "Sniping":   0.30,
        "Utility":   0.25,
        "Clutching": 0.15,
        "Firepower": 0.15,
        "Impact":    0.15,
    },
}

FALLBACK_WEIGHTS: dict[str, float] = {
    "Firepower": 0.25, "Impact": 0.25, "Opening": 0.20,
    "Clutching": 0.15, "Trading": 0.15,
}

# ---------------------------------------------------------------------------
# 2. Blend coefficients
# ---------------------------------------------------------------------------
W_ROLE    = 0.45
W_HLTV    = 0.40
W_RANKING = 0.46

HLTV_MIN = 0.60
HLTV_MAX = 1.39

# ---------------------------------------------------------------------------
# 3. Helpers
# ---------------------------------------------------------------------------
def _normalise_impact(val: float) -> float:
    """Map raw HLTV Impact rating (0.50 - 1.70) to 0 - 100."""
    if pd.isna(val):
        return 50.0
    return max(0.0, min(100.0, (val - 0.50) / 1.20 * 100.0))


def _normalise_hltv(row: pd.Series | dict) -> float:
    """Extract and normalise overall HLTV rating with fallback columns."""
    val = row.get("Overall Rating")
    if pd.isna(val):
        val = row.get("Rating 3.0")
    if pd.isna(val):
        val = row.get("Rating")
        
    val = pd.to_numeric(val, errors="coerce")
    if pd.isna(val):
        return 50.0
    return max(0.0, min(100.0, (val - HLTV_MIN) / (HLTV_MAX - HLTV_MIN) * 100.0))


def _ranking_adjustment(rank: int | None, max_rank: int = 17) -> float:
    # Tier 1 (1 - 20)
    # Tier 2 (21 - 40)
    # Tier 3 (41+)
    if rank is None:
        return -25.0
    if rank <= 3:
        return 45.0 - (rank - 1) * 3.5
    elif rank <= 10:
        return 38.0 - (rank - 3) * 3.0
    elif rank <= 20:
        return 17.0 - (rank - 10) * 1.7
    elif rank <= 40:
        # Tier 2: gentle gradual slope
        return 0.0 - (rank - 20) * 1.5
    else:
        # Tier 3: capped floor
        return -30.0 - min(25.0, (rank - 40) * 0.8)


def _post_scale(raw: float) -> int:
    raw = max(0.0, min(100.0, raw))
    # Minimum rating ~70, elite peak ~96-97
    scaled = 70.0 + (math.pow(raw / 100.0, 1.25) * 27.0)
    return int(round(max(70.0, min(97.0, scaled))))


def _role_score(row: pd.Series | dict, role: str) -> float:
    weights = ROLE_WEIGHTS.get(role, None)
    if weights is None:
        for base in ("awper", "entry", "lurker", "support"):
            if base in role:
                weights = ROLE_WEIGHTS.get(base)
                break
    if weights is None:
        weights = FALLBACK_WEIGHTS

    score = 0.0
    for stat, w in weights.items():
        val = pd.to_numeric(row.get(stat), errors="coerce")
        if pd.isna(val):
            val = 50.0
        elif stat == "Impact":
            val = _normalise_impact(val)
            
        score += w * val
    return score


# ---------------------------------------------------------------------------
# 4. Main calculation
# ---------------------------------------------------------------------------
def calculate_rating(row: pd.Series | dict, team_rank: int | None = None, max_rank: int = 16) -> int:
    role = str(row.get("role", "")) if pd.notna(row.get("role")) else ""
    is_igl = bool(row.get("is_igl", False))
    if is_igl and "igl" not in role.lower().split():
        role = f"{role} igl".strip()
    
    rs   = _role_score(row, role)
    hltv = _normalise_hltv(row)
    
    # Base performance score
    perf_raw = (W_ROLE / (W_ROLE + W_HLTV)) * rs + (W_HLTV / (W_ROLE + W_HLTV)) * hltv
    
    # Ranking modifier
    rank_mod = _ranking_adjustment(team_rank, max_rank=max_rank)
    
    raw = (1.0 - W_RANKING) * perf_raw + (W_RANKING * (50.0 + rank_mod))
    
    # IGL Low-Fragging Penalty
    if is_igl and hltv < 45.0:
        raw -= 8.0

    return _post_scale(raw)


def _team_rank_map(df: pd.DataFrame) -> dict[str, int]:
    """Use scraped world ranks when available, falling back to CSV team order."""
    if "Team_Rank" in df.columns:
        team_ranks: dict[str, int] = {}
        for team, raw_rank in zip(df["Team"], df["Team_Rank"]):
            if pd.isna(team) or str(team).strip() == "":
                continue
            rank = pd.to_numeric(raw_rank, errors="coerce")
            if pd.notna(rank):
                team_ranks.setdefault(str(team), int(rank))
        return team_ranks

    unique_teams = [
        team for team in df["Team"].dropna().unique()
        if str(team).strip() != ""
    ]
    return {str(team): rank for rank, team in enumerate(unique_teams, 1)}


# ---------------------------------------------------------------------------
# 5. Execution
# ---------------------------------------------------------------------------
def main():
    from app.classifier import load_and_classify

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hltv_team_player_stats_2026.csv")
    print(f"Loading: {csv_path}\n")
    df = load_and_classify(csv_path)

    team_rank = _team_rank_map(df)
    max_rank = max(team_rank.values(), default=20)

    ratings = []
    for _, row in df.iterrows():
        t    = row.get("Team")
        rank = team_rank.get(t) if pd.notna(t) else None
        ratings.append(calculate_rating(row, rank, max_rank=max_rank))

    df["Rating"] = ratings

    display_cols = ["Team", "Team_Rank", "Player", "role", "Rating", "igl_score",
                    "Overall Rating", "Firepower", "Impact", "Opening",
                    "Entrying", "Clutching", "Trading", "Utility", "Sniping"]
    display_cols = [c for c in display_cols if c in df.columns]

    pd.set_option("display.max_rows", 200)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_colwidth", 24)

    print("=" * 140)
    print("  PLAYER IN-GAME RATINGS (TEAM-WISE BREAKDOWN)")
    print("=" * 140)

    rostered_df = df[df["Team"].notna()].copy()
    no_team_df = df[df["Team"].isna()].copy()

    rostered_df["Team_Rank"] = rostered_df["Team"].map(team_rank)
    sorted_rostered = rostered_df.sort_values(by=["Team_Rank", "Rating"], ascending=[True, False])
    
    for team, group in sorted_rostered.groupby("Team", sort=False):
        rank = team_rank.get(team)
        rank_label = f"#{rank}" if rank is not None else "unranked"
        print(f"\n[ Rank {rank_label} ]  {team.upper()}")
        print("-" * 140)
        print(group[display_cols].to_string(index=False))
        print("-" * 140)

    if not no_team_df.empty:
        print("\n" + "=" * 140)
        print("  NO-TEAM PLAYERS / FREE AGENTS")
        print("=" * 140)
        sorted_no_team = no_team_df.sort_values(by="Rating", ascending=False)
        print(sorted_no_team[display_cols].to_string(index=False))
        print("=" * 140)

    known_igls = ["apEX", "karrigan", "Aleksib", "FalleN", "HooXi", "bLitz", "Twistzz", "xertioN"]
    print("\n  IGL STYLE & RATINGS (sanity check)")
    igl_check = df[df["Player"].isin(known_igls)][["Player", "Team", "role", "Rating", "igl_score"]]
    print(igl_check.to_string(index=False))

    print("\n[Done]\n")


if __name__ == "__main__":
    main()
