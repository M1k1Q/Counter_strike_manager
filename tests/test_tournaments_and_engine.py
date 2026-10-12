import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models
from app.domain.enums import MatchFormats, TournamentTier, TournamentStatus, MatchStage, MatchStatus
from app.services.match_engine import MatchEngine
from app.services.tournament_service import TournamentService


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    # Seed 16 test teams with 5 players each
    for i in range(1, 17):
        team = models.Team(
            name=f"Team {i}",
            ranking=i,
            ranking_points=(17 - i) * 100,
            budget=1_000_000,
        )
        db.add(team)
        db.flush()

        # Add 5 players per team
        # Team 1 will have a super star (donk-like) with rating 1.40, fp 99
        for p_idx in range(1, 6):
            if i == 1 and p_idx == 1:
                rating = 1.40
                fp = 99.0
                impact = 1.60
                role = "star awper"
            elif p_idx == 5:
                rating = 0.85
                fp = 25.0
                impact = 0.70
                role = "igl"
            else:
                rating = 1.05 - (p_idx * 0.05)
                fp = 60.0 - (p_idx * 5)
                impact = 1.0
                role = "rifler"

            player = models.Player(
                player=f"Player_{i}_{p_idx}",
                team_id=team.id,
                overall_rating=rating,
                firepower=fp,
                impact=impact,
                role=role,
                is_active_roster=True,
                Rating=int(rating * 70),
            )
            db.add(player)

    # Manager
    manager = models.Manager(name="TestManager", team_id=1, budget=1_000_000, career_points=0)
    db.add(manager)
    db.commit()

    yield db
    db.close()


def test_match_formats_odd_logic():
    """Verify MatchFormats and best-of X odd logic."""
    assert MatchFormats.get_best_of_count("Bo1") == 1
    assert MatchFormats.get_maps_to_win("Bo1") == 1

    assert MatchFormats.get_best_of_count("Bo3") == 3
    assert MatchFormats.get_maps_to_win("Bo3") == 2

    assert MatchFormats.get_best_of_count("Bo5") == 5
    assert MatchFormats.get_maps_to_win("Bo5") == 3

    assert MatchFormats.get_best_of_count("Bo7") == 7
    assert MatchFormats.get_maps_to_win("Bo7") == 4

    # Even format defaults to 1
    assert MatchFormats.get_best_of_count("Bo2") == 1


def test_match_engine_frag_distribution(test_db):
    """
    Test frag distribution and statistics:
    1. Higher rated players are significantly more likely to top frag.
    2. Frags do not exceed realistic map maximums.
    3. Total kills for a team are properly distributed across the 5 players.
    """
    engine = MatchEngine(test_db)
    team1 = test_db.query(models.Team).filter(models.Team.id == 1).first()
    team2 = test_db.query(models.Team).filter(models.Team.id == 2).first()

    star_player = [p for p in team1.players if p.overall_rating == 1.40][0]

    star_top_frag_count = 0
    total_maps_tested = 25

    for _ in range(total_maps_tested):
        map_res = engine.simulate_map(team1, team2, "Mirage", 1)

        # Verify score: either won at 13 in regulation or reached OT
        t1 = map_res["team1_score"]
        t2 = map_res["team2_score"]
        tot_rounds = t1 + t2

        if not map_res["overtime"]:
            assert max(t1, t2) == 13
            assert min(t1, t2) <= 11
        else:
            assert max(t1, t2) >= 16
            assert abs(t1 - t2) >= 2

        # Check frag limits
        for stat in map_res["stats1"]:
            kills = stat["kills"]
            assert kills <= int(1.35 * tot_rounds + 5)
            assert kills >= 1
            # Check realistic ADR and rating
            assert 30.0 <= stat["adr"] <= 145.0
            assert 0.30 <= stat["rating"] <= 2.50

        # Check if star top fragged on team 1
        t1_kills = {s["player"].id: s["kills"] for s in map_res["stats1"]}
        top_killer_id = max(t1_kills, key=t1_kills.get)
        if top_killer_id == star_player.id:
            star_top_frag_count += 1

    top_frag_rate = star_top_frag_count / total_maps_tested
    assert top_frag_rate >= 0.60, f"Star player top frag rate was {top_frag_rate:.2f}, expected >= 0.60"


def test_series_simulation_bo3(test_db):
    """Test full Bo3 series simulation requiring 2 map wins."""
    engine = MatchEngine(test_db)

    match = models.Match(
        team1_id=1,
        team2_id=2,
        format="Bo3",
        status="scheduled",
    )
    test_db.add(match)
    test_db.commit()

    simulated = engine.simulate_series(match)
    assert simulated.status == MatchStatus.COMPLETED
    assert max(simulated.team1_score, simulated.team2_score) == 2
    assert min(simulated.team1_score, simulated.team2_score) in [0, 1]
    assert simulated.winner_id in [1, 2]
    assert len(simulated.maps) in [2, 3]

    # Check each map has 10 player stats records (5 from each team)
    for m in simulated.maps:
        assert len(m.player_stats) == 10


def test_tournament_calendar_lifecycle(test_db):
    """
    Test full 16-team tournament calendar workflow:
    1. Seeding 16 teams into Group A and Group B (8 teams each)
    2. Group stage matches played (56 matches total)
    3. Advancement to Quarter-Finals (4 matches, Bo3)
    4. Advancement to Semi-Finals (2 matches, Bo3)
    5. Grand Final (1 match, Bo5) and crowning champion
    6. Tournament MVP & EVPs awarded
    """
    svc = TournamentService(test_db)
    state = svc.get_or_create_calendar_state()

    assert state.current_year == 2026
    assert state.current_month == 1
    assert state.active_tournament is not None

    tournament = state.active_tournament

    # Initialize tournament
    svc.initialize_tournament(tournament.id)

    # 16 participants seeded
    assert len(tournament.participants) == 16
    group_a = [p for p in tournament.participants if p.group_name == "A"]
    group_b = [p for p in tournament.participants if p.group_name == "B"]
    assert len(group_a) == 8
    assert len(group_b) == 8

    # 56 group stage matches created (28 per group)
    group_matches = [m for m in tournament.matches if m.stage == MatchStage.GROUP_STAGE.value]
    assert len(group_matches) == 56

    # Simulate all group stage matches
    for m in group_matches:
        svc.play_match(m.id)

    test_db.refresh(tournament)

    # Quarter-finals should have been automatically generated (4 matches)!
    qf_matches = [m for m in tournament.matches if m.stage == MatchStage.QUARTER_FINAL.value]
    assert len(qf_matches) == 4

    # Play all quarter-finals
    for m in qf_matches:
        svc.play_match(m.id)

    test_db.refresh(tournament)

    # Semi-finals should have been automatically generated (2 matches)!
    semi_matches = [m for m in tournament.matches if m.stage == MatchStage.SEMI_FINAL.value]
    assert len(semi_matches) == 2

    # Play both semi-finals
    for m in semi_matches:
        svc.play_match(m.id)

    test_db.refresh(tournament)

    # Grand final generated (Bo5 format)!
    gf_matches = [m for m in tournament.matches if m.stage == MatchStage.GRAND_FINAL.value]
    assert len(gf_matches) == 1
    assert gf_matches[0].format == "Bo5"

    # Play grand final
    svc.play_match(gf_matches[0].id)

    test_db.refresh(tournament)
    assert tournament.status == TournamentStatus.COMPLETED.value
    assert tournament.champion_id is not None

    # Check Event Statistics, MVP, and EVPs
    stats = svc.get_tournament_stats(tournament.id)
    assert stats["is_completed"] is True
    assert stats["mvp"] is not None
    assert stats["mvp"]["award"] == "MVP"
    # MVP must be from one of the two finalist teams
    assert stats["mvp"]["team_id"] in [gf_matches[0].team1_id, gf_matches[0].team2_id]
    assert len(stats["evps"]) <= 10
    assert len(stats["evps"]) > 0
    # Every EVP must have reached playoffs
    for evp in stats["evps"]:
        assert evp["reached_playoffs"] is True
        assert evp["award"].startswith("EVP #")

    # Advance calendar
    new_state = svc.advance_calendar()
    assert new_state.current_month == 2
