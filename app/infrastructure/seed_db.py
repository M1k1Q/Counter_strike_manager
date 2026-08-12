import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.infrastructure.database import SessionLocal, engine, Base
from app import models
from app.classifier import load_and_classify
from app.rating import calculate_rating


def _f(row, col):
    v = row.get(col)
    if pd.isna(v):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _get_overall_rating(row):
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
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hltv_team_player_stats_2026.csv")
        if not os.path.exists(csv_path):
            print(f"[ERROR] CSV file not found at: {csv_path}")
            return

        print("Classifying players from CSV...")
        df = load_and_classify(csv_path)

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

        print("Seeding players...")
        team_rank_map = {team: idx + 1 for idx, team in enumerate(unique_teams)}
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
                player=str(row["Player"]),
                team_id=team_id,
                ct_rating=_f(row, "CT Rating"),
                t_rating=_f(row, "T Rating"),
                overall_rating=_get_overall_rating(row),
                clutching=_f(row, "Clutching"),
                entrying=_f(row, "Entrying"),
                firepower=_f(row, "Firepower"),
                impact=_f(row, "Impact"),
                opening=_f(row, "Opening"),
                sniping=_f(row, "Sniping"),
                trading=_f(row, "Trading"),
                utility=_f(row, "Utility"),
                role=str(row["role"]) if pd.notna(row.get("role")) else None,
                confidence=_f(row, "confidence") or 0.0,
                igl_score=_f(row, "igl_score") or 0.0,
                is_igl=bool(row.get("is_igl", False)),
                Rating=calculate_rating(row, team_rank),
            )
            db.add(db_player)

        db.commit()
        print(f"Database seeding complete — {len(df)} players, {len(team_map)} teams.")

    except Exception as exc:
        db.rollback()
        print(f"[ERROR] Seeding failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
