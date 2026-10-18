from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.services.player_rating_service import migrate_player_ratings


def test_migrate_player_ratings_rescales_persisted_rows_once():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        top_team = models.Team(name="FURIA", ranking=4)
        lower_ranked_team = models.Team(name="FlyQuest", ranking=67)
        session.add_all([top_team, lower_ranked_team])
        session.flush()

        molodoy = models.Player(
            player="molodoy",
            team_id=top_team.id,
            role="awper",
            overall_rating=1.14,
            sniping=92,
            clutching=62,
            opening=73,
            firepower=84,
        )
        jks = models.Player(
            player="jks",
            team_id=lower_ranked_team.id,
            role="lurker",
            overall_rating=1.30,
            clutching=84,
            trading=39,
            firepower=94,
            opening=65,
        )
        session.add_all([molodoy, jks])
        session.commit()

        migrated_count = migrate_player_ratings(session)
        session.refresh(molodoy)
        session.refresh(jks)
        updated_ratings = (molodoy.Rating, jks.Rating)

        assert migrated_count == 2
        assert molodoy.Rating > jks.Rating
        assert migrate_player_ratings(session) == 0

        lower_ranked_team.ranking = 1
        session.commit()
        assert migrate_player_ratings(session) == 0
        session.refresh(jks)
        assert jks.Rating == updated_ratings[1]
    finally:
        session.close()
        engine.dispose()
