from collections import Counter

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.domain.enums import MatchStage, MatchStatus, TournamentStatus
from app.services.tournament_service import TournamentService


@pytest.fixture
def major_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        for rank in range(1, 34):
            team = models.Team(name=f'Team {rank}', ranking=rank, ranking_points=0, budget=0)
            db.add(team)
            db.flush()
            db.add_all([models.Player(player=f'P{rank}_{i}', team_id=team.id,
                       Rating=80, age=23, is_active_roster=True) for i in range(5)])
        manager = models.Manager(name='Manager', team_id=32, budget=0, career_points=0)
        event = models.Tournament(name='Test Major', tier='Major', year=2026, month=5,
                    min_rank_required=32, prize_pool=1_250_000, status='upcoming', format='Bo5')
        db.add_all([manager, event])
        db.commit()
        yield db, event, manager
    engine.dispose()


def test_major_has_32_teams_in_eight_balanced_groups(major_db):
    db, event, manager = major_db
    service = TournamentService(db)
    service.initialize_tournament(event.id)
    assert len(event.participants) == 32
    assert Counter(p.group_name for p in event.participants) == dict.fromkeys('ABCDEFGH', 4)
    assert {p.team_id for p in event.participants} == set(range(1, 33))
    assert len(event.matches) == 48
    assert all(m.format == 'Bo3' for m in event.matches)
    appearances = Counter(team_id for m in event.matches for team_id in (m.team1_id, m.team2_id))
    assert set(appearances.values()) == {3}
    assert service.check_invite_status(event, manager.team)['invited']
    assert not service.check_invite_status(event, db.get(models.Team, 33))['invited']
    service.initialize_tournament(event.id)
    assert len(event.matches) == 48


@pytest.mark.parametrize("managed_placement", ["Group Stage", "Round of 16", "Champion"])
def test_full_major_progression_and_prizes(major_db, monkeypatch, managed_placement):
    db, event, manager = major_db
    service = TournamentService(db)
    service.initialize_tournament(event.id)

    def complete(match):
        match.winner_id = match.team1_id
        match.team1_score = 3 if match.format == 'Bo5' else 2
        match.team2_score = 0
        match.status = MatchStatus.COMPLETED.value
        db.commit()
    monkeypatch.setattr(service.match_engine, 'simulate_series', complete)

    for stage, count in [('group_stage', 48), ('round_of_16', 8),
                         ('quarter_final', 4), ('semi_final', 2), ('grand_final', 1)]:
        matches = [m for m in event.matches if m.stage == stage]
        assert len(matches) == count
        if stage == 'round_of_16':
            assert sum(not p.eliminated for p in event.participants) == 16
            groups = {p.team_id: p.group_name for p in event.participants}
            assert all(groups[m.team1_id] != groups[m.team2_id] for m in matches)
        if stage == 'grand_final':
            manager.team_id = (matches[0].team1_id if managed_placement == 'Champion' else
                next(p.team_id for p in event.participants if p.placement == managed_placement))
            db.commit()
        for match in matches:
            service.play_match(match.id)
        service.check_and_advance_stage(event)  # Repeated checks cannot duplicate rounds.

    assert event.status == TournamentStatus.COMPLETED.value
    assert Counter(p.placement for p in event.participants) == {
        'Champion': 1, 'Runner-Up': 1, 'Semifinals': 2, 'Quarterfinalist': 4,
        'Round of 16': 8, 'Group Stage': 16,
    }
    assert sum(p.team.budget for p in event.participants) == event.prize_pool
    shares = {'Champion': .4, 'Runner-Up': .2, 'Semifinals': .1,
              'Quarterfinalist': .03, 'Round of 16': .01, 'Group Stage': 0}
    for participant in event.participants:
        assert participant.team.budget == int(event.prize_pool * shares[participant.placement])
        if participant.placement == 'Group Stage':
            assert participant.team.ranking_points == 0
        elif participant.placement == 'Round of 16':
            assert participant.team.ranking_points == 90
    own = next(p for p in event.participants if p.team_id == manager.team_id)
    assert manager.budget == own.team.budget
    assert manager.career_points == own.team.ranking_points
    before = (manager.budget, manager.career_points, sum(p.team.budget for p in event.participants))
    final = next(m for m in event.matches if m.stage == MatchStage.GRAND_FINAL.value)
    service.conclude_tournament(event, final)
    assert before == (manager.budget, manager.career_points, sum(p.team.budget for p in event.participants))


def test_major_refuses_to_silently_shrink_to_16_teams(major_db):
    db, event, _ = major_db
    for player in db.query(models.Player).filter(models.Player.team_id >= 17):
        db.delete(player)
    db.commit()
    with pytest.raises(ValueError, match='requires 32'):
        TournamentService(db).initialize_tournament(event.id)
    assert not event.participants


def test_round_of_16_is_exposed_by_api_and_runs_through_real_engine(major_db):
    from app.api.routes.tournaments import _build_tournament_detail

    db, event, _ = major_db
    service = TournamentService(db)
    service.initialize_tournament(event.id)
    for match in event.matches:
        match.status = 'completed'
        match.winner_id = match.team1_id
    db.commit()
    service.check_and_advance_stage(event)
    round16 = next(m for m in event.matches if m.stage == 'round_of_16')
    service.play_match(round16.id)
    detail = _build_tournament_detail(event, db)
    assert len(detail.participants) == 32
    serialized = next(m for m in detail.matches if m.id == round16.id)
    assert serialized.stage == 'round_of_16'
    assert serialized.status == 'completed'
    assert len(serialized.maps) >= 2
