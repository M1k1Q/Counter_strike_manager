import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import models
from app.database import Base
from app.services.tournament_service import TournamentService, LOWER_TIER_EVENTS


@pytest.fixture
def ranked_pool():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        for rank in range(1, 42):
            team = models.Team(name=f'Team {rank}', ranking=rank)
            db.add(team)
            db.flush()
            db.add_all([models.Player(player=f'P{rank}_{i}', team_id=team.id, age=23) for i in range(5)])
        db.commit()
        yield db
    engine.dispose()


@pytest.mark.parametrize('tier', ['B-Tier', 'C-Tier'])
@pytest.mark.parametrize('rank,invited', [(1, False), (16, False), (17, True), (40, True), (41, False), (None, False)])
def test_lower_tier_invites_have_a_two_sided_rank_boundary(tier, rank, invited):
    event = models.Tournament(name='Custom lower event', tier=tier, min_rank_required=40)
    result = TournamentService(None).check_invite_status(event, models.Team(name='Test', ranking=rank))
    assert result['invited'] is invited
    assert '#17' in result['reason']


@pytest.mark.parametrize('manager_rank', [1, 16, 17, 35])
def test_lower_tier_seeding_excludes_top16_even_when_no_other_event_is_running(ranked_pool, manager_rank):
    db = ranked_pool
    db.add(models.Manager(name='Manager', team_id=manager_rank))
    event = models.Tournament(name='Stake Ranked Open Spring', tier='C-Tier', year=2030,
                             month=4, min_rank_required=60, status='upcoming')
    db.add(event)
    db.commit()
    TournamentService(db).initialize_tournament(event.id)
    ranks = {participant.team.ranking for participant in event.participants}
    assert len(event.participants) == 16
    assert all(rank >= 17 for rank in ranks)
    assert (manager_rank in ranks) is (manager_rank >= 17)


def test_lower_event_never_backfills_outside_its_rank_band(ranked_pool):
    db = ranked_pool
    event = models.Tournament(name='Small event', tier='B-Tier', year=2030,
                             month=4, min_rank_required=25, status='upcoming')
    db.add(event)
    db.commit()
    TournamentService(db).initialize_tournament(event.id)
    assert not event.participants
    assert event.status == 'completed'


def test_elite_events_keep_their_top16_invitations():
    service = TournamentService(None)
    event = models.Tournament(name='IEM', tier='S-Tier', min_rank_required=16)
    assert service.check_invite_status(event, models.Team(name='Top', ranking=1))['invited']
    assert not service.check_invite_status(event, models.Team(name='Lower', ranking=17))['invited']
    assert all(event['max_rank'] == 17 for event in LOWER_TIER_EVENTS)
