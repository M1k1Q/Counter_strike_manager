from sqlalchemy.orm import Session

from app import models
from app.rating import calculate_rating

RANK_SCALED_RATING_MIGRATION = "rank_scaled_player_ratings_v2"


def migrate_player_ratings(db: Session) -> int:
    """Recalculate persisted player ratings once using current team rankings."""
    migration = (
        db.query(models.DataMigration)
        .filter_by(migration_key=RANK_SCALED_RATING_MIGRATION)
        .first()
    )
    if migration:
        return 0

    teams = db.query(models.Team).all()
    teams_by_id = {team.id: team for team in teams}
    max_rank = max(
        (team.ranking for team in teams if team.ranking is not None),
        default=16,
    )
    players = db.query(models.Player).all()

    for player in players:
        team = teams_by_id.get(player.team_id)
        row = {
            "role": player.role,
            "is_igl": player.is_igl,
            "Overall Rating": player.overall_rating,
            "CT Rating": player.ct_rating,
            "T Rating": player.t_rating,
            "Clutching": player.clutching,
            "Entrying": player.entrying,
            "Firepower": player.firepower,
            "Impact": player.impact,
            "Opening": player.opening,
            "Sniping": player.sniping,
            "Trading": player.trading,
            "Utility": player.utility,
        }
        player.Rating = calculate_rating(
            row,
            team.ranking if team else None,
            max_rank=max_rank,
        )

    db.add(models.DataMigration(migration_key=RANK_SCALED_RATING_MIGRATION))
    db.commit()
    return len(players)
