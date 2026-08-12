import os
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Archetype profiles
# ---------------------------------------------------------------------------
ROLE_ARCHETYPES: dict[str, dict[str, tuple[float, float]]] = {
    "awper": {
        "Sniping":   (88.0, 5.0),   
        "Entrying":  (20.0, 1.5),   
        "Opening":   (50.0, 0.8),
        "Clutching": (65.0, 0.8),
        "Firepower": (55.0, 0.5),
        "Impact":    (60.0, 0.5),
        "Trading":   (40.0, 0.4),
        "Utility":   (40.0, 0.3),
    },
    "support": {
        "Utility":   (70.0, 3.0),
        "Trading":   (45.0, 2.0),
        "Opening":   (30.0, 2.0),
        "Entrying":  (45.0, 1.0),
        "Firepower": (45.0, 2.0),
        "Impact":    (45.0, 1.5),
        "Clutching": (45.0, 1.0),
        "Sniping":   (3.0, 0.2),
    },
    "entry": {
        "Entrying":  (85.0, 5.0), 
        "Opening":   (70.0, 1.8),   
        "Firepower": (55.0, 0.8),   
        "Impact":    (60.0, 0.8),
        "Sniping":   (3.0,  3.0),   
        "Trading":   (40.0, 0.5),
        "Clutching": (30.0, 0.4),
        "Utility":   (40.0, 0.3),
    },
    "lurker": {
        "Clutching": (55.0, 1.5),
        "Trading":   (45.0, 1.5),
        "Entrying":  (25.0, 3.0),
        "Opening":   (35.0, 2.0),
        "Sniping":   (3.0, 1.5),
        "Firepower": (60.0, 1.0),
        "Impact":    (60.0, 1.5),
        "Utility":   (50.0, 0.5),
    },
}

FEATURE_COLS = [
    "Sniping", "Entrying", "Opening", "Clutching",
    "Firepower", "Impact", "Trading", "Utility",
]

RAW_VALUE_FEATURES = {"Sniping"}
AWPER_SNIPING_THRESHOLD_RAW = 50.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in FEATURE_COLS + ["K/D", "Rating 3.0", "CT Rating", "T Rating", "Overall Rating"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _percentile_rank(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in FEATURE_COLS:
        if col in df.columns and col not in RAW_VALUE_FEATURES:
            df[col] = df[col].rank(pct=True) * 100.0
    return df


def _weighted_distance(player_pct: pd.Series, archetype: dict[str, tuple[float, float]]) -> float:
    sq_sum = 0.0
    for feat, (target, weight) in archetype.items():
        val = player_pct.get(feat)
        if pd.notna(val):
            sq_sum += weight * (val - target) ** 2
    return float(np.sqrt(sq_sum))


def calculate_igl_score(row: pd.Series) -> float:
    """
    Calculates an IGL potential score (0–100).
    Considers utility, opening/entry aggression, low sniping, and low firepower.
    """
    utility = row.get("Utility", 0.0)
    firepower = row.get("Firepower", 100.0)
    sniping = row.get("Sniping", 0.0)
    opening = row.get("Opening", 0.0)
    entrying = row.get("Entrying", 0.0)

    utility = float(utility) if pd.notna(utility) else 0.0
    firepower = float(firepower) if pd.notna(firepower) else 100.0
    sniping = float(sniping) if pd.notna(sniping) else 0.0
    opening = float(opening) if pd.notna(opening) else 0.0
    entrying = float(entrying) if pd.notna(entrying) else 0.0

    aggression = max(opening, entrying)
    score = (utility * 0.40) + (aggression * 0.20) + ((100.0 - firepower) * 0.20) + ((100.0 - sniping) * 0.20)
    return float(min(max(round(score), 0), 100))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_players(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = _parse_numeric(df_raw)
    df_pct = _percentile_rank(df)

    roles = list(ROLE_ARCHETYPES.keys())
    assigned_roles = []
    confidence_scores = []
    all_role_scores = []
    igl_scores = []

    for i in df_pct.index:
        row = df_pct.loc[i]

        distances: dict[str, float] = {
            role: _weighted_distance(row, archetype)
            for role, archetype in ROLE_ARCHETYPES.items()
        }
        
        # 1. Support boost: strictly for low-aggression, high-utility players
        if (
            row.get("Utility", 0) >= 60
            and row.get("Firepower", 100) <= 45
            and row.get("Opening", 100) <= 40
            and row.get("Entrying", 100) <= 50
            and row.get("Trading", 0) >= 25
        ):
            distances["support"] *= 0.3

        # 2. Entry boost: for players with dominant Entrying scores (e.g. karrigan = 89)
        if row.get("Entrying", 0) >= 70:
            distances["entry"] *= 0.5

        # Hard gate AWPer role if sniping stat is too low
        sniping_raw = row.get("Sniping", 0.0)
        if pd.isna(sniping_raw) or float(sniping_raw) < AWPER_SNIPING_THRESHOLD_RAW:
            distances["awper"] = float("inf")

        best_role = min(distances, key=lambda r: distances[r])

        finite_distances = {r: d for r, d in distances.items() if d != float("inf")}
        similarities = {r: 1.0 / (1.0 + d) for r, d in finite_distances.items()}

        for r in roles:
            if r not in similarities:
                similarities[r] = 0.0

        total_sim = sum(similarities.values())
        norm_sim = {r: round((s / total_sim) * 100, 1) if total_sim > 0 else 0.0
                    for r, s in similarities.items()}

        assigned_roles.append(best_role)
        confidence_scores.append(norm_sim[best_role])
        all_role_scores.append(norm_sim)
        igl_scores.append(calculate_igl_score(row))

    result = _parse_numeric(df_raw)
    result["role"] = assigned_roles
    result["confidence"] = [round(c, 1) for c in confidence_scores]
    result["role_scores"] = all_role_scores
    result["igl_score"] = igl_scores
    result["is_igl"] = False

    # Per-team IGL selection + Calling Style Assignment   
    if "Team" in result.columns:
        team_groups = result[result["Team"].notna() & (result["Team"] != "")].groupby("Team")
        for team, group in team_groups:
            if group.empty:
                continue
            
            best_igl_idx = group["igl_score"].idxmax()
            
            natural_role = result.at[best_igl_idx, "role"]
            result.at[best_igl_idx, "role"] = f"{natural_role} igl"
            result.at[best_igl_idx, "is_igl"] = True

    return result


def load_and_classify(csv_path: str = "hltv_team_player_stats_2026.csv") -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at path: {csv_path}")
    
    df = pd.read_csv(csv_path, engine="python", on_bad_lines="skip")
    return classify_players(df)