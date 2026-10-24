from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.api.routes.players import train_owned_player, train_owned_player_form
from app.api.schemas.player_schema import PlayerResponse, PlayerTrainingRequest
from app.database import Base
from app.services.player_development_service import (
    apply_yearly_progression,
    calculate_yearly_player_potential,
    train_player,
    train_player_form,
    update_player_form,
)


@pytest.fixture
def development_db() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_factory()
    yield db
    db.close()


def make_player(**overrides: Any) -> models.Player:
    values = {
        "player": "Young Star",
        "age": 19,
        "Rating": 94,
        "potential": 94,
        "role": "entry",
        "firepower": 80.0,
        "entrying": 80.0,
        "opening": 80.0,
        "impact": 80.0,
    }
    values.update(overrides)
    return models.Player(**values)


def test_potential_uses_age_and_season_rating():
    young_star = make_player()
    veteran = make_player(age=32)

    assert calculate_yearly_player_potential(young_star, {"rating": 1.3}) == 97
    assert calculate_yearly_player_potential(young_star, {"rating": 1.09}) == 94
    assert calculate_yearly_player_potential(young_star, {"rating": 1.10}) > 94
    assert calculate_yearly_player_potential(veteran, {"rating": 1.5}) == 94


def test_player_can_grow_at_31_but_not_at_32(development_db: Session):
    db = development_db
    player = make_player(age=31)
    db.add(player)
    db.commit()

    apply_yearly_progression(
        db,
        2026,
        {int(player.id): {"rating": 1.5, "maps_played": 40}},
    )

    assert player.age == 32
    assert player.Rating == 95
    assert player.potential > 94


def test_yearly_progression_is_incremental_role_based_and_idempotent(development_db: Session):
    db = development_db
    team = models.Team(name="Development Team", ranking=5)
    db.add(team)
    db.flush()

    player = make_player(team_id=team.id)
    db.add(player)
    db.commit()
    season_stats = {int(player.id): {"rating": 1.3, "maps_played": 50}}

    assert apply_yearly_progression(db, 2026, season_stats) == 1
    assert player.potential == 97
    assert player.Rating == 95
    assert player.age == 20
    assert player.entrying > 80.0
    assert player.opening > 80.0
    assert player.firepower > 80.0

    assert apply_yearly_progression(db, 2026, season_stats) == 0
    assert player.Rating == 95
    assert player.age == 20


def test_growth_stops_at_32_but_age_still_advances(development_db: Session):
    db = development_db
    player = make_player(age=32)
    db.add(player)
    db.commit()

    apply_yearly_progression(
        db,
        2026,
        {int(player.id): {"rating": 1.5, "maps_played": 40}},
    )

    assert player.age == 33
    assert player.Rating == 94
    assert player.potential == 94


def test_training_adds_one_at_potential_regardless_of_form():
    low_form = make_player(age=31, potential=94, form=0.8)
    neutral_form = make_player(potential=94, form=1.0)
    high_form = make_player(potential=94, form=1.2)

    train_player(low_form, "entrying", 5, 16, 2026, 1)
    train_player(low_form, "entrying", 5, 16, 2026, 1)
    train_player(neutral_form, "entrying", 5, 16, 2026, 1)
    train_player(high_form, "entrying", 5, 16, 2026, 1)

    assert low_form.entrying == pytest.approx(82.0)
    assert neutral_form.entrying == pytest.approx(81.0)
    assert high_form.entrying == pytest.approx(81.0)
    assert low_form.Rating == 94


@pytest.mark.parametrize(
    ("form", "monthly_limit", "expected_gain"),
    [
        (1.2, 10.0, 1.0),
        (1.0, 5.0, 1.0),
        (0.8, 5.0, 1.0),
        (0.9, 5.0, 1.0),
        (0.79, 3.0, 1.0),
    ],
)
def test_monthly_training_budget_tracks_attribute_growth(form, monthly_limit, expected_gain):
    player = make_player(form=form)
    year, month = 2026, 1
    gained = 0.0

    while gained + expected_gain <= monthly_limit + 1e-9:
        previous_value = player.firepower
        train_player(player, "firepower", 5, 16, year, month)
        gained += player.firepower - previous_value

    assert player.training_points_used == pytest.approx(monthly_limit)
    with pytest.raises(ValueError, match="monthly training point limit"):
        train_player(player, "firepower", 5, 16, year, month)


def test_monthly_training_budget_resets_when_game_month_changes():
    player = make_player(form=1.0)
    for _ in range(5):
        train_player(player, "firepower", 5, 16, 2026, 1)

    assert player.training_points_used == pytest.approx(5.0)
    train_player(player, "firepower", 5, 16, 2026, 2)
    assert player.training_points_used == pytest.approx(1.0)
    assert (player.last_trained_year, player.last_trained_month) == (2026, 2)


def test_training_rejects_only_invalid_or_maxed_stats():
    player = make_player(potential=98)

    with pytest.raises(ValueError, match="Unsupported"):
        train_player(player, "unknown", 5, 16, 2026, 1)

    player.firepower = 100
    with pytest.raises(ValueError, match="maximum"):
        train_player(player, "firepower", 5, 16, 2026, 1)

    with pytest.raises(ValueError, match="age 32"):
        train_player(make_player(age=32), "firepower", 5, 16, 2026, 1)


def test_training_endpoint_checks_ownership_and_returns_player_data(development_db: Session):
    db = development_db
    team = models.Team(name="Manager Team", ranking=5)
    db.add(team)
    db.flush()
    player = make_player(team_id=team.id, age=31, potential=94)
    db.add(player)
    manager = models.Manager(name="Manager", team_id=team.id)
    db.add(manager)
    db.flush()
    db.add(models.CalendarState(current_year=2026, current_month=4, manager_id=manager.id))
    db.commit()

    trained = train_owned_player(
        player.id,
        PlayerTrainingRequest(stat="entrying"),
        db,
    )
    response = PlayerResponse.model_validate(trained)

    assert response.age == 31
    assert response.potential == 94
    assert response.entrying > 80.0
    assert response.training_points_used == pytest.approx(1.0)
    assert (response.last_trained_year, response.last_trained_month) == (2026, 4)
    trained_again = train_owned_player(
        player.id,
        PlayerTrainingRequest(stat="entrying"),
        db,
    )
    assert trained_again.entrying > response.entrying


def test_match_form_is_a_smoothed_bounded_multiplier():
    player = make_player(form=1.0)
    update_player_form(player, 1.3)
    assert player.form == pytest.approx(1.052)

    player.form = 1.2
    update_player_form(player, 2.5)
    assert player.form == 1.2


def test_form_training_refills_to_two_and_decays_after_a_series():
    player = make_player(form=1.0, training_form_bonus=0.0)

    train_player_form(player)
    assert player.training_form_bonus == 2.0
    player.training_form_bonus = 0.5
    train_player_form(player)
    assert player.training_form_bonus == 2.0

    train_player_form(player)
    assert player.training_form_bonus == 2.0

    update_player_form(player, 1.0)
    assert player.training_form_bonus == pytest.approx(1.3)
    assert player.Rating == 94


def test_form_training_endpoint_checks_ownership_and_returns_bonus(development_db: Session):
    db = development_db
    team = models.Team(name="Manager Team", ranking=5)
    other_team = models.Team(name="Other Team", ranking=10)
    db.add_all([team, other_team])
    db.flush()
    player = make_player(team_id=team.id)
    other_player = make_player(player="Other Player", team_id=other_team.id)
    db.add_all([player, other_player])
    db.add(models.Manager(name="Manager", team_id=team.id))
    db.commit()

    trained = train_owned_player_form(player.id, db)
    response = PlayerResponse.model_validate(trained)
    assert response.training_form_bonus == 2.0
    assert response.Rating == 94

    with pytest.raises(HTTPException) as error:
        train_owned_player_form(other_player.id, db)
    assert error.value.status_code == 403


def test_training_refreshes_natural_role_without_overwriting_assignments():
    import pandas as pd
    from app.classifier import classify_players, FEATURE_COLS

    player = make_player(
        role="awper igl", is_igl=True, selected_role="Support",
        sniping=0, utility=65, trading=55, clutching=45,
    )
    peers = [make_player(
        player=f"Peer {i}", sniping=i * 10, entrying=i * 10,
        opening=i * 9, utility=i * 8, trading=i * 7,
        clutching=i * 6, firepower=i * 10, impact=i * 10,
    ) for i in range(10)]
    population = [player, *peers]
    original_peer_roles = [peer.role for peer in peers]

    train_player(player, "firepower", 5, 16, 2026, 1, role_population=population)

    expected = classify_players(pd.DataFrame([
        {feature: getattr(p, feature.lower()) for feature in FEATURE_COLS}
        for p in population
    ])).iloc[0]
    assert player.role == expected["role"]
    assert not player.role.startswith("awper")  # Raw sniping gate is preserved.
    assert player.confidence == expected["confidence"]
    assert player.igl_score == expected["igl_score"]
    assert player.selected_role == "Support"
    assert player.is_igl is True
    assert [peer.role for peer in peers] == original_peer_roles


def test_training_respects_cap_with_legacy_fractional_attributes():
    player = make_player(firepower=99.625, form=1.0)
    train_player(player, "firepower", 5, 16, 2026, 1)
    assert player.firepower == 100
    assert player.training_points_used == 1
    with pytest.raises(ValueError, match="maximum"):
        train_player(player, "firepower", 5, 16, 2026, 1)


def test_legacy_fractional_budget_cannot_buy_partial_training():
    player = make_player(form=1.0, training_points_used=3.5,
                         last_trained_year=2026, last_trained_month=1)
    train_player(player, "firepower", 5, 16, 2026, 1)
    assert player.firepower == 81
    assert player.training_points_used == 4.5
    with pytest.raises(ValueError, match="monthly training point limit"):
        train_player(player, "firepower", 5, 16, 2026, 1)
    assert player.firepower == 81
    train_player(player, "firepower", 5, 16, 2026, 2)
    assert player.firepower == 82
    assert player.training_points_used == 1
