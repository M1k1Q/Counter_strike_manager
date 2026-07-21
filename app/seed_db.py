import os
import sys
import pandas as pd

# Allow running directly via `python seed_db.py`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal, engine, Base
from app import models


def load_and_classify(csv_path):
    """Load the scraped CSV and add simple classification columns if absent."""
    with open(csv_path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    cleaned_lines = []
    for line in lines:
        if line.strip():
            cleaned_lines.append(line.rstrip("\n"))

    if not cleaned_lines:
        return pd.DataFrame()

    header = cleaned_lines[0].split(",")
    rows = []
    for line in cleaned_lines[1:]:
        parts = line.split(",")
        if len(parts) != len(header):
            if len(parts) > len(header):
                parts = parts[:len(header)]
            else:
                parts = parts + [""] * (len(header) - len(parts))
        rows.append(parts)

    df = pd.DataFrame(rows, columns=header)
    # Convert the string "None" to actual NaN for team column
    df["Team"] = df["Team"].apply(lambda x: None if x == "None" or x == "" else x)
    if "role" not in df.columns:
        df["role"] = None
    if "confidence" not in df.columns:
        df["confidence"] = 0.0
    if "igl_score" not in df.columns:
        df["igl_score"] = 0.0
    if "is_igl" not in df.columns:
        df["is_igl"] = False
    if "Overall Rating" not in df.columns:
        df["Overall Rating"] = None
    return df


def calculate_rating(row, team_rank):
    """Compute a simple in-game rating from available metrics and team rank."""
    def _safe(value):
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _normalize_hltv(value):
        value = _safe(value)
        if value is None:
            return None
        return max(0.0, min(100.0, value * 50.0))

    metrics = []
    for col in ["CT Rating", "T Rating", "Overall Rating"]:
        normalized = _normalize_hltv(row.get(col))
        if normalized is not None:
            metrics.append(normalized)

    for col in [
        "Impact",
        "Firepower",
        "Opening",
        "Entrying",
        "Clutching",
        "Sniping",
        "Trading",
        "Utility",
    ]:
        val = _safe(row.get(col))
        if val is not None:
            metrics.append(max(0.0, min(100.0, val)))

    if not metrics:
        return 0.0

    base_score = sum(metrics) / len(metrics)
    penalty = (team_rank or 0) * 0.25
    return round(min(100.0, max(0.0, base_score - penalty)), 2)

def _f(row, col):
    """Return float value or None if missing/NaN or non-numeric."""
    v = row.get(col)
    if pd.isna(v):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def seed_database():
    print("Dropping all existing tables...")
    Base.metadata.drop_all(bind=engine)

    print("Creating all tables with current schema...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "hltv_team_player_stats_2026.csv",
        )
        if not os.path.exists(csv_path):
            print(f"[ERROR] CSV file not found at: {csv_path}")
            return

        print("Classifying players from CSV...")
        df = load_and_classify(csv_path)

        # ------------------------------------------------------------------
        # 1. Teams
        # ------------------------------------------------------------------
        print("Seeding teams...")
        team_map: dict[str, int] = {}
        raw_teams = [team_name.strip() if isinstance(team_name, str) else team_name for team_name in df["Team"].tolist()]
        unique_teams = []
        for team_name in raw_teams:
            if pd.isna(team_name) or str(team_name).strip() == "":
                continue
            if str(team_name) not in unique_teams:
                unique_teams.append(str(team_name))

        for rank, team_name in enumerate(unique_teams, 1):
            db_team = models.Team(name=team_name, ranking=rank)
            db.add(db_team)
            db.flush()
            team_map[team_name] = db_team.id

        # ------------------------------------------------------------------
        # 2. Players  — map CSV columns directly, no approximations
        # ------------------------------------------------------------------
        print("Seeding players...")
        team_rank_map = {t: i + 1 for i, t in enumerate(unique_teams)}
        for _, row in df.iterrows():
            raw_team_name = row.get("Team")
            if pd.isna(raw_team_name) or str(raw_team_name).strip() == "":
                team_name = None
                team_id = None
                team_rank = None
            else:
                team_name = str(raw_team_name)
                team_id = team_map.get(team_name)
                team_rank = team_rank_map.get(team_name)

            db_player = models.Player(
                player         = str(row["Player"]),
                team_id        = team_id,
                # HLTV ratings
                ct_rating      = _f(row, "CT Rating"),
                t_rating       = _f(row, "T Rating"),
                overall_rating = _f(row, "Overall Rating"),
                # Skill percentiles
                clutching      = _f(row, "Clutching"),
                entrying       = _f(row, "Entrying"),
                firepower      = _f(row, "Firepower"),
                impact         = _f(row, "Impact"),
                opening        = _f(row, "Opening"),
                sniping        = _f(row, "Sniping"),
                trading        = _f(row, "Trading"),
                utility        = _f(row, "Utility"),
                # Classifier outputs
                role           = str(row["role"])       if pd.notna(row.get("role"))       else None,
                confidence     = _f(row, "confidence")  or 0.0,
                igl_score      = _f(row, "igl_score")   or 0.0,
                is_igl         = bool(row.get("is_igl", False)),
                #calculating ingame rating based on stats out of 100, role and team ranking
                Rating         = calculate_rating(row, team_rank)
            )
            db.add(db_player)

        db.commit()
        print(f"Database seeding complete — {len(df)} players, {len(team_map)} teams.")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
