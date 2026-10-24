"""Entry attributes must matter independently of the overall/potential cap."""
import random

import pytest

from app import models
from app.services.match_engine import MatchEngine


def make_player(index=0, **overrides):
    fields = dict(
        id=index, player=f"Player {index}", Rating=83, potential=83,
        overall_rating=1.1, form=1.0, firepower=70, impact=1.1,
        utility=50, opening=50, entrying=50, role="entry" if index == 0 else "rifler",
    )
    fields.update(overrides)
    return models.Player(**fields)


@pytest.mark.parametrize("attribute", ["opening", "entrying"])
def test_each_entry_attribute_improves_power_and_simulated_performance(attribute):
    engine = MatchEngine(None)
    roster = [make_player(i) for i in range(5)]
    team = models.Team(name="Test", ranking=10)
    player = roster[0]
    original_random_state = random.getstate()

    def sample(value):
        setattr(player, attribute, value)
        power = engine.compute_team_power(team, roster)
        kills = ratings = 0
        for seed in range(600):
            random.seed(seed)
            result = engine.distribute_frags(roster, roster, 13, 9)[0]
            kills += result["kills"]
            ratings += result["rating"]
        return power, kills, ratings

    try:
        low = sample(20)
        high = sample(90)
    finally:
        random.setstate(original_random_state)

    assert high[0] > low[0]
    assert high[1] > low[1]
    assert high[2] > low[2]
    assert player.Rating == player.potential == 83


def test_entry_attributes_follow_selected_role_and_missing_values_are_neutral():
    player = make_player(opening=None, entrying=None)
    assert MatchEngine._entry_skill_edge(player) == 0
    player.opening = player.entrying = 100
    assert MatchEngine._entry_skill_edge(player) == 1
    player.selected_role = "support"
    assert MatchEngine._entry_skill_edge(player) == 0
    player.role = "rifler"
    player.selected_role = "entry"
    assert MatchEngine._entry_skill_edge(player) == 1

@pytest.mark.parametrize("role", ["support", "entry", "awper", "lurker"])
def test_firepower_improves_kills_and_rating_for_every_role(role):
    engine = MatchEngine(None)
    roster = [make_player(i) for i in range(5)]
    roster[0].role = role
    state = random.getstate()

    def sample(firepower):
        roster[0].firepower = firepower
        kills = rating = 0
        for seed in range(600):
            random.seed(seed)
            stats = engine.distribute_frags(roster, roster, 13, 9)[0]
            kills += stats["kills"]
            rating += stats["rating"]
        return kills, rating

    try:
        low = sample(30)
        high = sample(90)
    finally:
        random.setstate(state)
    assert high[0] > low[0]
    assert high[1] > low[1]
    assert roster[0].Rating == 83


def test_support_has_no_blanket_kill_penalty_against_neutral_rifler():
    engine = MatchEngine(None)
    roster = [make_player(i) for i in range(5)]
    state = random.getstate()
    try:
        roster[0].role = "support"
        random.seed(42)
        support = engine.distribute_frags(roster, roster, 13, 9)[0]
        roster[0].role = "rifler"
        random.seed(42)
        rifler = engine.distribute_frags(roster, roster, 13, 9)[0]
    finally:
        random.setstate(state)
    assert support["kills"] == rifler["kills"]
