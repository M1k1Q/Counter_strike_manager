"""IGL is an appointment, independent of the player's tactical role."""
import random

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.api.routes.teams import update_player_role
from app.api.schemas.team_schema import PlayerRoleUpdate
from app.api.schemas.player_schema import PlayerResponse
from app.services.match_engine import MatchEngine


@pytest.fixture
def squad():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        team = models.Team(name='Test squad', ranking=10)
        db.add(team)
        db.flush()
        for index, role in enumerate(['entry', 'support', 'awper', 'lurker', 'entry']):
            db.add(models.Player(player=f'Player {index}', team_id=team.id,
                role=role, selected_role=role.title(), Rating=80, age=23,
                is_igl=index == 0, is_active_roster=True, form=1,
                firepower=60, opening=60, entrying=60, utility=60, impact=1.1))
        db.commit()
        yield db, team
    engine.dispose()


@pytest.mark.parametrize('index', [0, 1, 2, 3, 4])
def test_any_role_can_be_appointed_and_role_changes_preserve_captaincy(squad, index):
    db, team = squad
    player = team.players[index]
    natural, selected = player.role, player.selected_role
    result = update_player_role(player.id, PlayerRoleUpdate(is_igl=True), db)
    assert result.is_igl
    assert (result.role, result.selected_role) == (natural, selected)
    assert sum(p.is_igl for p in team.players) == 1
    update_player_role(player.id, PlayerRoleUpdate(role='Support'), db)
    assert player.is_igl
    assert player.selected_role == 'Support'
    update_player_role(player.id, PlayerRoleUpdate(is_igl=False), db)
    assert not player.is_igl
    assert player.selected_role == 'Support'


def test_legacy_igl_roles_do_not_create_stale_captains(squad):
    db, team = squad
    old, new = team.players[:2]
    old.role, old.selected_role = 'entry igl', 'IGL'
    db.commit()
    response = PlayerResponse.model_validate(old)
    assert response.role == 'entry'
    assert response.selected_role is None
    update_player_role(new.id, PlayerRoleUpdate(is_igl=True), db)
    assert not old.is_igl
    assert old.role == 'entry'
    assert old.selected_role is None
    assert new.role == 'support'
    assert MatchEngine._role_fit_firepower_bonus(old) == 0


def test_igl_flag_adds_team_synergy_without_changing_individual_role_weights(squad):
    db, team = squad
    engine = MatchEngine(db)
    roster = list(team.players)
    for player in roster:
        player.is_igl = False
    baseline = engine.compute_team_power(team, roster)
    state = random.getstate()
    try:
        random.seed(12)
        before = engine.distribute_frags(roster, roster, 13, 9)
        roster[2].is_igl = True  # AWPer retains their AWP behavior.
        random.seed(12)
        after = engine.distribute_frags(roster, roster, 13, 9)
    finally:
        random.setstate(state)
    assert engine.compute_team_power(team, roster) == pytest.approx(baseline + 3.5)
    assert [(s['kills'], s['rating']) for s in before] == [(s['kills'], s['rating']) for s in after]


def test_stale_role_suffix_does_not_enable_igl_synergy(squad):
    db, team = squad
    roster = list(team.players)
    for player in roster:
        player.is_igl = False
    engine = MatchEngine(db)
    baseline = engine.compute_team_power(team, roster)
    roster[0].role = 'entry igl'
    assert engine.compute_team_power(team, roster) == baseline
