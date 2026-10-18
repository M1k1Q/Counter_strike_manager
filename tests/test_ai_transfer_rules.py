import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.api.routes.ai_buyouts import _execute_sale
from app.api.routes.teams import add_player_to_team
from app.services.negotiation_service import NegotiationService
from app.services.match_engine import MatchEngine
from app.services.tournament_service import TournamentService
from app.services.transfer_service import (
    TransferService,
    ensure_transfers_unlocked,
    handle_ai_replacement,
    reconcile_ai_rosters,
    transfer_lock_name,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def make_player(name, team_id, rating, role, overall_rating=1.0):
    return models.Player(
        player=name,
        team_id=team_id,
        Rating=rating,
        overall_rating=overall_rating,
        role=role,
    )


def test_ai_replacement_uses_free_agent_without_raiding_another_team(db):
    human_team = models.Team(name="Human", ranking=1, budget=1_000_000)
    ai_team = models.Team(name="AI Buyer", ranking=15, budget=500_000)
    seller = models.Team(name="AI Seller", ranking=30, budget=500_000)
    db.add_all([human_team, ai_team, seller])
    db.flush()
    db.add(models.Manager(name="Manager", team_id=human_team.id, budget=1_000_000))

    lost_player = make_player("Lost Support", human_team.id, 85, "support igl")
    matching_player = make_player("Support Fit", seller.id, 70, "support")
    higher_rated_free_agent = make_player("Entry Free Agent", None, 85, "entry")
    incumbents = [
        make_player(f"AI Starter {index}", ai_team.id, 70 + index, "entry")
        for index in range(4)
    ]
    db.add_all([lost_player, matching_player, higher_rated_free_agent, *incumbents])
    db.commit()

    handle_ai_replacement(db, ai_team.id, lost_player.id)
    db.refresh(matching_player)
    db.refresh(higher_rated_free_agent)

    assert matching_player.team_id == seller.id
    assert higher_rated_free_agent.team_id == ai_team.id
    assert sum(player.team_id == ai_team.id for player in db.query(models.Player).all()) == 5


def test_ai_replacement_falls_back_to_best_affordable_player(db):
    human_team = models.Team(name="Human", ranking=1, budget=1_000_000)
    ai_team = models.Team(name="AI Buyer", ranking=15, budget=500_000)
    db.add_all([human_team, ai_team])
    db.flush()
    db.add(models.Manager(name="Manager", team_id=human_team.id, budget=1_000_000))

    lost_player = make_player("Lost Support", human_team.id, 70, "support")
    best_available = make_player("Best Available", None, 99, "awper")
    other_available = make_player("Other Available", None, 90, "entry")
    in_range_but_weaker = make_player("In Range", None, 65, "entry")
    db.add_all([lost_player, best_available, other_available, in_range_but_weaker])
    db.commit()

    handle_ai_replacement(db, ai_team.id, lost_player.id)
    db.refresh(best_available)

    assert best_available.team_id == ai_team.id


def test_ai_buyout_replaces_lowest_player_in_incoming_role_and_caps_roster(db):
    human_team = models.Team(name="Human", ranking=1, budget=1_000_000)
    ai_team = models.Team(name="AI Buyer", ranking=15, budget=500_000)
    db.add_all([human_team, ai_team])
    db.flush()
    manager = models.Manager(name="Manager", team_id=human_team.id, budget=1_000_000)
    incoming_player = make_player("Incoming Support", human_team.id, 80, "support")
    ai_roster = [
        make_player("Weak Support", ai_team.id, 50, "support"),
        make_player("Strong Support", ai_team.id, 75, "support igl"),
        make_player("Entry", ai_team.id, 70, "entry"),
        make_player("AWPer", ai_team.id, 72, "awper"),
        make_player("Lurker", ai_team.id, 73, "lurker"),
    ]
    db.add_all([manager, incoming_player, *ai_roster])
    db.flush()
    offer = models.AIBuyoutOffer(
        player=incoming_player,
        ai_team=ai_team,
        current_offer=100_000,
        initial_offer=100_000,
        status="pending",
    )

    _execute_sale(db, offer, 100_000)
    db.flush()

    assert incoming_player.team_id == ai_team.id
    assert ai_roster[0].team_id is None
    assert sum(player.team_id == ai_team.id for player in db.query(models.Player).all()) == 5


def test_ranked_ai_team_replaces_transfer_loss_and_can_play_tournament(db):
    human_team = models.Team(name="Human", ranking=1, budget=1_000_000)
    stronger_team = models.Team(name="Stronger AI", ranking=2, budget=500_000)
    furia = models.Team(name="FURIA", ranking=6, budget=1_200_000)
    luminosity = models.Team(name="Luminosity", ranking=24, budget=879_595)
    db.add_all([human_team, stronger_team, furia, luminosity])
    db.flush()

    manager = models.Manager(name="Manager", team_id=human_team.id, budget=1_000_000)
    lost_player = make_player("AZUWU", furia.id, 82, "entry", overall_rating=1.02)
    protected_star = make_player("donk", luminosity.id, 94, "entry", overall_rating=1.38)
    replacement = make_player("Free Agent Entry", None, 85, "entry", overall_rating=1.0)
    remaining_roster = [
        make_player(f"FURIA Player {index}", furia.id, 80 - index, "entry", overall_rating=0.9)
        for index in range(4)
    ]
    for player in remaining_roster:
        player.is_active_roster = True
    lost_player.is_active_roster = True
    db.add_all([manager, lost_player, protected_star, replacement, *remaining_roster])
    db.commit()
    original_luminosity_budget = luminosity.budget

    TransferService(db).complete_transfer(
        lost_player,
        human_team.id,
        200_000,
        manager,
        furia,
    )
    db.commit()
    db.refresh(furia)

    furia_roster = db.query(models.Player).filter_by(team_id=furia.id).all()
    assert len(furia_roster) == 5
    assert replacement in furia_roster
    assert protected_star.team_id == luminosity.id
    assert luminosity.budget == original_luminosity_budget
    assert lost_player.team_id == human_team.id
    assert len(MatchEngine(db).get_active_roster(furia)) == 5


def test_elite_player_market_value_exceeds_weak_team_budget(db):
    luminosity = models.Team(name="Luminosity", ranking=24, budget=879_595)
    db.add(luminosity)
    db.flush()
    donk = models.Player(
        player="donk",
        team_id=luminosity.id,
        Rating=94,
        overall_rating=1.38,
        clutching=42,
        entrying=67,
        firepower=100,
        opening=96,
        sniping=0,
        trading=76,
        utility=32,
    )
    db.add(donk)
    db.flush()

    assert donk.price > 1_000_000
    assert donk.price > luminosity.budget


def test_roster_reconciliation_fills_existing_ai_vacancy_without_taking_manager_player(db):
    human_team = models.Team(name="Human", ranking=1, budget=1_000_000)
    furia = models.Team(name="FURIA", ranking=6, budget=300_000)
    db.add_all([human_team, furia])
    db.flush()

    manager = models.Manager(name="Manager", team_id=human_team.id, budget=1_000_000)
    manager_awper = make_player("Manager AWPer", human_team.id, 99, "awper")
    replacement_awper = make_player("Available AWPer", None, 85, "awper")
    furia_roster = [
        make_player("FURIA Entry", furia.id, 80, "entry"),
        make_player("FURIA Support", furia.id, 79, "support igl"),
        make_player("FURIA Lurker", furia.id, 78, "lurker"),
        make_player("FURIA Entry Two", furia.id, 77, "entry"),
    ]
    db.add_all([manager, manager_awper, replacement_awper, *furia_roster])
    db.commit()

    repaired = reconcile_ai_rosters(db)

    db.refresh(replacement_awper)
    assert repaired == 1
    assert replacement_awper.team_id == furia.id
    assert manager_awper.team_id == human_team.id
    assert len(db.query(models.Player).filter_by(team_id=furia.id).all()) == 5
    assert reconcile_ai_rosters(db) == 0


def test_reconciliation_prefers_free_agent_to_avoid_creating_another_vacancy(db):
    human_team = models.Team(name="Human", ranking=1, budget=1_000_000)
    ai_team = models.Team(name="AI Buyer", ranking=6, budget=1_000_000)
    other_ai_team = models.Team(name="Other AI", ranking=2, budget=1_000_000)
    db.add_all([human_team, ai_team, other_ai_team])
    db.flush()
    db.add(models.Manager(name="Manager", team_id=human_team.id, budget=1_000_000))

    lost_player = make_player("Lost AWPer", human_team.id, 80, "awper")
    higher_rated_team_player = make_player("Team AWPer", other_ai_team.id, 99, "awper")
    free_agent = make_player("Free Agent", None, 70, "entry")
    incumbents = [
        make_player(f"AI Player {index}", ai_team.id, 70 + index, "entry")
        for index in range(4)
    ]
    other_team_roster = [
        higher_rated_team_player,
        *[
            make_player(f"Other AI Player {index}", other_ai_team.id, 70 + index, "entry")
            for index in range(4)
        ],
    ]
    db.add_all([lost_player, free_agent, *incumbents, *other_team_roster])
    db.commit()

    repaired = reconcile_ai_rosters(db)

    assert repaired == 1
    assert free_agent.team_id == ai_team.id
    assert higher_rated_team_player.team_id == other_ai_team.id


def test_playing_a_match_does_not_change_active_tournament_rosters(db):
    underfilled_team = models.Team(name="Underfilled", ranking=1, budget=500_000)
    full_team = models.Team(name="Full", ranking=2, budget=500_000)
    db.add_all([underfilled_team, full_team])
    db.flush()
    underfilled_players = [
        make_player(f"Underfilled Player {index}", underfilled_team.id, 70 + index, "entry")
        for index in range(4)
    ]
    full_players = [
        make_player(f"Full Player {index}", full_team.id, 70 + index, "entry")
        for index in range(5)
    ]
    free_agent = make_player("Emergency AWPer", None, 75, "awper")
    tournament = models.Tournament(name="Active Event", status="active")
    db.add(tournament)
    db.flush()
    db.add_all([
        models.TournamentParticipant(
            tournament_id=tournament.id,
            team_id=underfilled_team.id,
            seed=1,
        ),
        models.TournamentParticipant(
            tournament_id=tournament.id,
            team_id=full_team.id,
            seed=2,
        ),
    ])
    match = models.Match(
        tournament_id=tournament.id,
        team1_id=underfilled_team.id,
        team2_id=full_team.id,
        format="Bo1",
        status="scheduled",
    )
    db.add_all([*underfilled_players, *full_players, free_agent, match])
    db.commit()

    played_match = TournamentService(db).play_match(match.id)

    assert played_match.status == "completed"
    assert free_agent.team_id is None
    assert len([stat for stat in played_match.player_stats if stat.team_id == underfilled_team.id]) == 4


def test_tournament_participants_are_transfer_locked_until_event_completion(db):
    participant_team = models.Team(name="Tournament Team", ranking=1, budget=500_000)
    outside_team = models.Team(name="Outside Team", ranking=20, budget=500_000)
    tournament = models.Tournament(name="Active Event", status="active")
    db.add_all([participant_team, outside_team, tournament])
    db.flush()
    db.add(models.TournamentParticipant(
        tournament_id=tournament.id,
        team_id=participant_team.id,
        seed=1,
    ))
    db.commit()

    assert transfer_lock_name(db, participant_team.id) == tournament.name
    assert transfer_lock_name(db, outside_team.id) is None
    with pytest.raises(HTTPException, match="Transfers are locked") as exc_info:
        ensure_transfers_unlocked(db, participant_team.id, outside_team.id)
    assert exc_info.value.status_code == 409

    tournament.status = "completed"
    db.commit()
    assert transfer_lock_name(db, participant_team.id) is None


def test_negotiation_rejects_transfer_when_manager_team_is_in_active_event(db):
    manager_team = models.Team(name="Manager Team", ranking=1, budget=500_000)
    source_team = models.Team(name="Source Team", ranking=20, budget=500_000)
    tournament = models.Tournament(name="Active Event", status="active")
    db.add_all([manager_team, source_team, tournament])
    db.flush()
    manager = models.Manager(name="Manager", team_id=manager_team.id, budget=1_000_000)
    player = make_player("Target Player", source_team.id, 70, "entry")
    db.add_all([
        manager,
        player,
        models.TournamentParticipant(
            tournament_id=tournament.id,
            team_id=manager_team.id,
            seed=1,
        ),
    ])
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        NegotiationService(db).start_negotiation(
            models.Negotiation(
                player_id=player.id,
                offer_amount=100_000,
            ),
            manager,
        )
    assert exc_info.value.status_code == 409
    assert player.team_id == source_team.id


def test_direct_free_agent_signing_is_rejected_for_active_participant(db):
    manager_team = models.Team(name="Manager Team", ranking=1, budget=500_000)
    tournament = models.Tournament(name="Active Event", status="active")
    db.add_all([manager_team, tournament])
    db.flush()
    free_agent = make_player("Available Player", None, 80, "awper")
    db.add_all([
        free_agent,
        models.TournamentParticipant(
            tournament_id=tournament.id,
            team_id=manager_team.id,
            seed=1,
        ),
    ])
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        add_player_to_team(manager_team.id, free_agent.id, db)

    assert exc_info.value.status_code == 409
    assert free_agent.team_id is None


def test_ai_buyout_sale_is_rejected_when_either_team_is_locked(db):
    manager_team = models.Team(name="Manager Team", ranking=1, budget=500_000)
    ai_team = models.Team(name="AI Team", ranking=20, budget=500_000)
    tournament = models.Tournament(name="Active Event", status="active")
    db.add_all([manager_team, ai_team, tournament])
    db.flush()
    manager = models.Manager(name="Manager", team_id=manager_team.id, budget=100_000)
    player = make_player("Manager Player", manager_team.id, 70, "entry")
    offer = models.AIBuyoutOffer(
        player=player,
        ai_team=ai_team,
        current_offer=100_000,
        initial_offer=100_000,
        status="pending",
    )
    db.add_all([
        manager,
        player,
        offer,
        models.TournamentParticipant(
            tournament_id=tournament.id,
            team_id=ai_team.id,
            seed=1,
        ),
    ])
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        _execute_sale(db, offer, 100_000)
    assert exc_info.value.status_code == 409
    assert offer.status == "pending"
    assert player.team_id == manager_team.id


def test_roster_reconciliation_skips_active_tournament_participants(db):
    manager_team = models.Team(name="Manager Team", ranking=1, budget=500_000)
    tournament_team = models.Team(name="Tournament Team", ranking=2, budget=500_000)
    tournament = models.Tournament(name="Active Event", status="active")
    db.add_all([manager_team, tournament_team, tournament])
    db.flush()
    db.add(models.Manager(name="Manager", team_id=manager_team.id, budget=500_000))
    roster = [
        make_player(f"Starter {index}", tournament_team.id, 70 + index, "entry")
        for index in range(4)
    ]
    free_agent = make_player("Available Player", None, 80, "awper")
    db.add_all([
        *roster,
        free_agent,
        models.TournamentParticipant(
            tournament_id=tournament.id,
            team_id=tournament_team.id,
            seed=1,
        ),
    ])
    db.commit()

    assert reconcile_ai_rosters(db) == 0
    assert free_agent.team_id is None
    assert len(db.query(models.Player).filter_by(team_id=tournament_team.id).all()) == 4


def test_ai_replacement_does_not_sign_from_an_active_tournament_team(db):
    manager_team = models.Team(name="Manager Team", ranking=1, budget=500_000)
    buying_team = models.Team(name="Buying Team", ranking=10, budget=500_000)
    tournament_team = models.Team(name="Tournament Team", ranking=2, budget=500_000)
    tournament = models.Tournament(name="Active Event", status="active")
    db.add_all([manager_team, buying_team, tournament_team, tournament])
    db.flush()
    db.add(models.Manager(name="Manager", team_id=manager_team.id, budget=500_000))
    lost_player = make_player("Lost Player", manager_team.id, 80, "support")
    protected_player = make_player("Protected Player", tournament_team.id, 85, "support")
    buying_roster = [
        make_player(f"Buyer Player {index}", buying_team.id, 70 + index, "entry")
        for index in range(4)
    ]
    db.add_all([
        lost_player,
        protected_player,
        *buying_roster,
        models.TournamentParticipant(
            tournament_id=tournament.id,
            team_id=tournament_team.id,
            seed=1,
        ),
    ])
    db.commit()

    handle_ai_replacement(db, buying_team.id, lost_player.id)

    assert protected_player.team_id == tournament_team.id
    assert len(db.query(models.Player).filter_by(team_id=buying_team.id).all()) == 4
