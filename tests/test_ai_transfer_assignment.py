import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.services.transfer_service import handle_ai_replacement


def run_transfer_assignment_check():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        human_team = models.Team(name="Human Team", ranking=10, budget=1_000_000)
        ai_team = models.Team(name="AI Team", ranking=15, budget=300_000)
        db.add_all([human_team, ai_team])
        db.flush()

        manager = models.Manager(name="Human Manager", team_id=human_team.id, budget=1_000_000)
        db.add(manager)

        lost_player = models.Player(
            player="Lost Starter",
            team_id=ai_team.id,
            Rating=85,
            overall_rating=1.1,
        )

        better_free_agent = models.Player(
            player="Top Free Agent",
            team_id=None,
            Rating=84,
            overall_rating=1.0,
        )
        weaker_free_agent = models.Player(
            player="Backup Free Agent",
            team_id=None,
            Rating=82,
            overall_rating=1.0,
        )

        db.add_all([lost_player, better_free_agent, weaker_free_agent])
        db.flush()

        before_budget = ai_team.budget
        lost_player.team_id = human_team.id
        handle_ai_replacement(db, ai_team.id, lost_player.id)
        db.commit()
        db.refresh(ai_team)
        db.refresh(better_free_agent)

        assert better_free_agent.team_id == ai_team.id, (
            f"Expected replacement to be assigned to {ai_team.name}, got team_id={better_free_agent.team_id}"
        )
        assert ai_team.budget < before_budget, "AI team budget should decrease after signing a replacement"
        assert lost_player.team_id == human_team.id, "The transferred player should remain with the manager's team"

        print("AI transfer assignment check passed")
        print(f"- Replacement assigned: {better_free_agent.player}")
        print(f"- Team budget changed from {before_budget} to {ai_team.budget}")

    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    run_transfer_assignment_check()
