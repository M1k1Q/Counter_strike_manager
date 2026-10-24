from typing import Any, Mapping

import pandas as pd

from app.classifier import classify_players, FEATURE_COLS

from sqlalchemy.orm import Session

from app import models
from app.domain.player_roles import playing_role
from app.rating import calculate_rating

GROWTH_STOP_AGE = 32
MAX_PLAYER_RATING = 99
FORM_MIN = 0.8
FORM_MAX = 1.2
MAX_TRAINING_FORM_BONUS = 2.0
TRAINING_FORM_BONUS_DECAY = 0.65
MONTHLY_TRAINING_POINT_LIMITS = {
    "low": 3.0,
    "normal": 5.0,
    "high": 10.0,
}

ROLE_GROWTH_WEIGHTS: dict[str, dict[str, float]] = {
    "awper": {
        "sniping": 0.30,
        "firepower": 0.20,
        "impact": 0.20,
        "clutching": 0.15,
        "opening": 0.15,
    },
    "entry": {
        "entrying": 0.30,
        "opening": 0.25,
        "firepower": 0.20,
        "impact": 0.15,
        "trading": 0.10,
    },
    "lurker": {
        "clutching": 0.25,
        "trading": 0.20,
        "firepower": 0.15,
        "impact": 0.15,
        "opening": 0.15,
        "utility": 0.05,
        "entrying": 0.05,
    },
    "support": {
        "utility": 0.30,
        "trading": 0.20,
        "impact": 0.15,
        "clutching": 0.15,
        "entrying": 0.10,
        "opening": 0.05,
        "firepower": 0.05,
    },
}

TRAINABLE_STATS = {
    "firepower",
    "entrying",
    "opening",
    "clutching",
    "sniping",
    "trading",
    "utility",
    "impact",
}


def refresh_natural_roles(
    population: list[models.Player], targets: list[models.Player],
) -> None:
    """Reclassify changed players against the live population, keeping assignments.

    The original classifier ranks attributes across the full player pool. Omit
    Team so its seed-time IGL election cannot replace the manager's captain.
    """
    if not population or not targets:
        return
    frame = pd.DataFrame([
        {feature: getattr(player, feature.lower()) for feature in FEATURE_COLS}
        for player in population
    ])
    classified = classify_players(frame)
    target_objects = {id(player) for player in targets}
    for index, player in enumerate(population):
        if id(player) not in target_objects:
            continue
        result = classified.iloc[index]
        natural_role = str(result["role"])
        player.role = natural_role
        player.confidence = float(result["confidence"])
        player.igl_score = float(result["igl_score"])


def _player_role(player: models.Player) -> str:
    role = playing_role(player)
    for known_role in ROLE_GROWTH_WEIGHTS:
        if known_role in role:
            return known_role
    return "default"


def _rating(player: models.Player) -> int:
    return int(player.Rating or 70)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _monthly_training_point_limit(form: float) -> float:
    if form < 0.8:
        return MONTHLY_TRAINING_POINT_LIMITS["low"]
    if form > 1.0:
        return MONTHLY_TRAINING_POINT_LIMITS["high"]
    return MONTHLY_TRAINING_POINT_LIMITS["normal"]


def calculate_yearly_player_potential(
    player: models.Player,
    season_stats: Mapping[str, Any],
) -> int:
    """Grow potential for players whose individual season average exceeds 1.09."""
    current_rating = _rating(player)
    current_potential = max(current_rating, int(player.potential or current_rating))
    age = player.age if player.age is not None else 20
    season_rating = float(season_stats.get("rating", 0.0) or 0.0)
    if age >= GROWTH_STOP_AGE or season_rating <= 1.09:
        return current_potential

    age_factor = _clamp((GROWTH_STOP_AGE - age) / 10.0, 0.0, 1.0)
    performance_factor = _clamp((season_rating - 1.09) / 0.21, 0.0, 1.0)
    potential_gain = max(1, round(3.0 * age_factor * performance_factor))
    return min(MAX_PLAYER_RATING, current_potential + potential_gain)


def _apply_role_stat_growth(player: models.Player, overall_gain: int) -> None:
    role_weights = ROLE_GROWTH_WEIGHTS.get(
        _player_role(player),
        {
            "firepower": 0.25,
            "impact": 0.20,
            "opening": 0.15,
            "clutching": 0.10,
            "trading": 0.10,
            "entrying": 0.10,
            "utility": 0.05,
            "sniping": 0.05,
        },
    )
    for stat, weight in role_weights.items():
        current_value = getattr(player, stat)
        if current_value is None:
            current_value = 50.0
        setattr(player, stat, min(100.0, current_value + (2.0 * overall_gain * weight)))


def apply_yearly_progression(
    db: Session,
    year: int,
    season_stats: Mapping[int, Mapping[str, Any]],
) -> int:
    """Apply one idempotent season of age, potential, skill, and overall progression."""
    migration_key = f"player_development_{year}"
    if db.query(models.DataMigration).filter_by(migration_key=migration_key).first():
        return 0

    players = db.query(models.Player).all()

    developed_players = []
    for player in players:
        current_age = player.age if player.age is not None else 20
        stats = season_stats.get(player.id)
        if not stats or current_age >= GROWTH_STOP_AGE:
            player.age = current_age + 1
            continue

        season_rating = float(stats.get("rating", 0.0) or 0.0)
        if season_rating <= 1.09:
            player.age = current_age + 1
            continue

        current_rating = _rating(player)
        player.potential = calculate_yearly_player_potential(player, stats)
        if player.potential <= current_rating:
            player.age = current_age + 1
            continue

        overall_gain = min(player.potential - current_rating, 1)
        player.Rating = current_rating + overall_gain
        _apply_role_stat_growth(player, overall_gain)
        developed_players.append(player)
        player.age = current_age + 1

    refresh_natural_roles(players, developed_players)
    db.add(models.DataMigration(migration_key=migration_key))
    db.commit()
    return len(players)


def train_player(
    player: models.Player,
    stat: str,
    team_rank: int | None,
    max_rank: int,
    year: int,
    month: int,
    role_population: list[models.Player] | None = None,
) -> models.Player:
    """Train a selected attribute within the player's monthly form-based point budget."""
    if player.age is not None and player.age >= GROWTH_STOP_AGE:
        raise ValueError(f"Players cannot develop at age {GROWTH_STOP_AGE} or older")
    if stat not in TRAINABLE_STATS:
        raise ValueError("Unsupported training stat")
    current_value = getattr(player, stat)
    if current_value is not None and current_value >= 100:
        raise ValueError("This stat has reached its maximum")

    if current_value is None:
        current_value = 50.0
    form = player.form if player.form is not None else 1.0
    if (player.last_trained_year, player.last_trained_month) != (year, month):
        player.training_points_used = 0.0

    remaining_points = _monthly_training_point_limit(form) - (player.training_points_used or 0.0)
    if remaining_points < 1.0 - 1e-9:
        raise ValueError("This player's monthly training point limit has been reached")

    # Each click spends one point; form controls only the monthly allowance.
    stat_gain = min(1.0, 100.0 - current_value)
    setattr(player, stat, current_value + stat_gain)
    player.training_points_used = round(
        (player.training_points_used or 0.0) + 1.0,
        6,
    )
    player.last_trained_year = year
    player.last_trained_month = month

    if role_population is not None:
        refresh_natural_roles(role_population, [player])

    calculated_rating = calculate_rating(
        {
            "role": playing_role(player),
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
        },
        team_rank,
        max_rank=max_rank,
    )
    current_rating = _rating(player)
    rating_ceiling = max(current_rating, int(player.potential or current_rating))
    player.Rating = min(
        MAX_PLAYER_RATING,
        rating_ceiling,
        max(current_rating, calculated_rating),
    )
    return player


def train_player_form(player: models.Player) -> models.Player:
    """Refill the temporary match-rating training bonus to its two-point maximum."""
    player.training_form_bonus = MAX_TRAINING_FORM_BONUS
    return player


def update_player_form(player: models.Player, average_match_rating: float) -> None:
    """Smooth recent simulated performance into a bounded rating multiplier."""
    current_form = player.form if player.form is not None else 1.0
    target_form = _clamp(1.0 + (average_match_rating - 1.0) * 0.5, FORM_MIN, FORM_MAX)
    player.form = round(_clamp(current_form * 0.65 + target_form * 0.35, FORM_MIN, FORM_MAX), 3)
    current_training_bonus = player.training_form_bonus or 0.0
    player.training_form_bonus = round(
        current_training_bonus * TRAINING_FORM_BONUS_DECAY,
        3,
    )
