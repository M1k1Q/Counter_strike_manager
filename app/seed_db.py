import os
import sys
import pandas as pd

# Allow running directly via `python seed_db.py`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal, engine, Base
from app import models
from app.classifier import load_and_classify
from app.rating import calculate_rating, _team_rank_map




def _f(row, col):
    """Return float value or None if missing/NaN or non-numeric."""
    v = row.get(col)
    if pd.isna(v):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _get_overall_rating(row):
    """Extract HLTV overall rating checking fallback column names in CSV."""
    for col in ["Overall Rating", "Rating 3.0", "Rating"]:
        val = _f(row, col)
        if val is not None:
            return val
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

        team_rank_map = _team_rank_map(df)
        max_team_rank = max(team_rank_map.values(), default=16)
        for team_name in unique_teams:
            team_rank = team_rank_map.get(team_name)
            db_team = models.Team(
                name=team_name,
                ranking=team_rank,
                ranking_points=(
                    max(0, (max_team_rank + 1 - team_rank) * 100)
                    if team_rank is not None else 0
                ),
            )
            db.add(db_team)
            db.flush()
            team_map[team_name] = db_team.id

        # ------------------------------------------------------------------
        # 2. Players  — map CSV columns directly, no approximations
        # ------------------------------------------------------------------
        print("Seeding players...")
        team_active_roster_count: dict[int, int] = {}
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

            is_active = False
            if team_id is not None:
                current_count = team_active_roster_count.get(team_id, 0)
                if current_count < 5:
                    is_active = True
                    team_active_roster_count[team_id] = current_count + 1

            rating = calculate_rating(row, team_rank, max_rank=max_team_rank)
            age = _f(row, "Age")
            db_player = models.Player(
                player         = str(row["Player"]),
                team_id        = team_id,
                # HLTV ratings
                ct_rating      = _f(row, "CT Rating"),
                t_rating       = _f(row, "T Rating"),
                overall_rating = _get_overall_rating(row),
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
                is_active_roster = is_active,
                Rating         = rating,
                potential      = rating,
                age            = int(age) if age is not None else 20,
                form           = 1.0,
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
