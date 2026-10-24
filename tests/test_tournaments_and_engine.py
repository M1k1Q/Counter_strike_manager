import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models
from app.api.routes.tournaments import (
    get_pre_match_lineup,
    get_tournament_history,
    get_yearly_top_20,
)
from app.api.routes.players import get_user_team_yearly_ratings
from app.api.schemas.tournament_schema import YearEndTop20Response
from app.domain.enums import MatchFormats, TournamentTier, TournamentStatus, MatchStage, MatchStatus
from app.services.match_engine import MatchEngine
from app.services.transfer_service import transfer_lock_name
from app.services.tournament_service import (
    TournamentService,
    YEAR_END_MIN_MAPS,
    _year_end_ranking_score,
)


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


def test_match_rating_uses_training_bonus_without_changing_player_rating(test_db):
    engine = MatchEngine(test_db)
    player = test_db.query(models.Player).filter_by(team_id=1).first()
    player.Rating = 80
    player.training_form_bonus = 2.0
    player.form = 1.2

    assert engine._effective_player_rating(player) == pytest.approx((80 / 70) * 1.2 + (2 / 70))
    assert player.Rating == 80


def test_pre_match_lineup_only_exposes_training_bonus_for_user_roster(test_db):
    user_player = test_db.query(models.Player).filter_by(team_id=1).first()
    user_player.form = 1.08
    user_player.training_form_bonus = 1.5
    opponent_player = test_db.query(models.Player).filter_by(team_id=2).first()
    opponent_player.form = 0.92
    opponent_player.training_form_bonus = 2.0
    match = models.Match(team1_id=1, team2_id=2, status=MatchStatus.SCHEDULED.value)
    test_db.add(match)
    test_db.commit()

    lineup = get_pre_match_lineup(match.id, test_db)

    assert lineup.user_team.id == 1
    assert lineup.opponent_team.id == 2
    assert len(lineup.user_team.players) == 5
    assert len(lineup.opponent_team.players) == 5
    assert lineup.user_team.players[0].training_form_bonus == 1.5
    assert lineup.user_team.players[0].form == pytest.approx(1.08)
    assert lineup.opponent_team.players[0].form == pytest.approx(0.92)
    assert not hasattr(lineup.opponent_team.players[0], "training_form_bonus")


def test_formation_role_fit_is_a_temporary_firepower_modifier(test_db):
    engine = MatchEngine(test_db)
    player = test_db.query(models.Player).filter_by(team_id=1).first()
    base_firepower = player.firepower
    base_overall_rating = player.overall_rating
    base_rating = player.Rating
    player.role = "entry igl"
    player.is_igl = True

    player.selected_role = None
    neutral_power = engine.compute_team_power(player.team, [player])
    player.selected_role = "Entry"
    assert engine._role_fit_firepower_bonus(player) == 1
    assert engine._effective_firepower(player) == min(100.0, base_firepower + 1)
    assert engine.compute_team_power(player.team, [player]) == pytest.approx(neutral_power + 0.2)

    player.selected_role = "Lurker"
    assert engine._role_fit_firepower_bonus(player) == -1
    assert engine._effective_firepower(player) == max(0.0, base_firepower - 1)
    assert engine.compute_team_power(player.team, [player]) == pytest.approx(neutral_power - 0.2)

    player.selected_role = None
    assert engine._role_fit_firepower_bonus(player) == 0
    assert engine._effective_firepower(player) == base_firepower
    assert player.overall_rating == base_overall_rating
    assert player.Rating == base_rating


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
    1. Seeding 16 teams into four groups of four
    2. Group stage matches played (24 matches total)
    3. Top two from each group advance to Quarter-Finals (4 matches, Bo3)
    4. Advancement to Semi-Finals (2 matches, Bo3)
    5. Grand Final (1 match, Bo5) and crowning champion
    6. Tournament MVP & EVPs awarded
    """
    svc = TournamentService(test_db)
    state = svc.get_or_create_calendar_state()

    assert state.current_year == 2026
    assert state.current_month == 1
    assert state.active_tournament is not None

    # Start the season's opening tournament.
    state = svc.start_current_month_tournaments()
    tournament = state.active_tournament
    assert tournament is not None

    # 16 participants seeded
    assert len(tournament.participants) == 16
    assert {
        group_name: sum(p.group_name == group_name for p in tournament.participants)
        for group_name in ["A", "B", "C", "D"]
    } == {"A": 4, "B": 4, "C": 4, "D": 4}

    # 24 group stage matches created (6 per group)
    group_matches = [m for m in tournament.matches if m.stage == MatchStage.GROUP_STAGE.value]
    assert len(group_matches) == 24
    assert {
        group_name: sum(m.group_name == group_name for m in group_matches)
        for group_name in ["A", "B", "C", "D"]
    } == {"A": 6, "B": 6, "C": 6, "D": 6}

    # Simulate all group stage matches
    for m in group_matches:
        svc.play_match(m.id)

    test_db.refresh(tournament)

    # Quarter-finals should have been automatically generated (4 matches)!
    qf_matches = [m for m in tournament.matches if m.stage == MatchStage.QUARTER_FINAL.value]
    assert len(qf_matches) == 4
    assert sum(not p.eliminated for p in tournament.participants) == 8
    sorted_groups = {}
    for group_name in ["A", "B", "C", "D"]:
        sorted_groups[group_name] = sorted(
            (p for p in tournament.participants if p.group_name == group_name),
            key=lambda participant: (
                participant.wins,
                participant.rounds_won - participant.rounds_lost,
                -participant.seed,
            ),
            reverse=True,
        )
        assert all(not p.eliminated for p in sorted_groups[group_name][:2])
        assert all(p.eliminated for p in sorted_groups[group_name][2:])
    assert {
        frozenset((match.team1_id, match.team2_id))
        for match in qf_matches
    } == {
        frozenset((sorted_groups["A"][0].team_id, sorted_groups["B"][1].team_id)),
        frozenset((sorted_groups["B"][0].team_id, sorted_groups["A"][1].team_id)),
        frozenset((sorted_groups["C"][0].team_id, sorted_groups["D"][1].team_id)),
        frozenset((sorted_groups["D"][0].team_id, sorted_groups["C"][1].team_id)),
    }

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

    with pytest.raises(ValueError, match="already completed"):
        svc.play_match(gf_matches[0].id)
    with pytest.raises(ValueError, match="already completed"):
        svc.simulate_all_ai_matches(tournament.id)

    # Advance calendar
    new_state = svc.advance_calendar()
    assert new_state.current_month == 2


def test_tournament_skips_underfilled_team_and_invites_next_ranked_team(test_db):
    underfilled_team = test_db.query(models.Team).filter_by(ranking=16).one()
    removed_player = (
        test_db.query(models.Player)
        .filter_by(team_id=underfilled_team.id)
        .first()
    )
    test_db.delete(removed_player)

    next_ranked_team = models.Team(
        name="Team 17",
        ranking=17,
        ranking_points=0,
        budget=1_000_000,
    )
    test_db.add(next_ranked_team)
    test_db.flush()
    test_db.add_all([
        models.Player(
            player=f"Player_17_{player_number}",
            team_id=next_ranked_team.id,
            overall_rating=1.0,
            is_active_roster=True,
        )
        for player_number in range(1, 6)
    ])
    test_db.commit()

    service = TournamentService(test_db)
    service.get_or_create_calendar_state()
    state = service.start_current_month_tournaments()
    tournament = state.active_tournament
    assert tournament is not None

    participant_team_ids = {participant.team_id for participant in tournament.participants}
    assert len(participant_team_ids) == 16
    assert underfilled_team.id not in participant_team_ids
    assert next_ranked_team.id in participant_team_ids


def test_major_evps_bias_toward_deeper_playoff_runs(test_db):
    tournament = models.Tournament(
        name="Test Major",
        tier=TournamentTier.MAJOR.value,
        year=2026,
        month=5,
        status=TournamentStatus.COMPLETED.value,
        champion_id=1,
    )
    test_db.add(tournament)
    test_db.flush()

    placements = {
        1: "Champion",
        2: "Runner-Up",
        3: "Semifinals",
        4: "Semifinals",
        5: "Quarterfinalist",
        6: "Quarterfinalist",
        7: "Quarterfinalist",
        8: "Quarterfinalist",
    }
    for team_id in range(1, 17):
        test_db.add(models.TournamentParticipant(
            tournament_id=tournament.id,
            team_id=team_id,
            seed=team_id,
            group_name="A",
            placement=placements.get(team_id, "Group Stage"),
        ))

    qf_pairs = [(1, 8), (2, 7), (3, 6), (4, 5)]
    qf_matches = []
    for team1_id, team2_id in qf_pairs:
        match = models.Match(
            tournament_id=tournament.id,
            stage=MatchStage.QUARTER_FINAL.value,
            team1_id=team1_id,
            team2_id=team2_id,
            status=MatchStatus.COMPLETED.value,
        )
        test_db.add(match)
        qf_matches.append(match)
    test_db.flush()

    semi_matches = []
    for team1_id, team2_id in [(1, 3), (2, 4)]:
        match = models.Match(
            tournament_id=tournament.id,
            stage=MatchStage.SEMI_FINAL.value,
            team1_id=team1_id,
            team2_id=team2_id,
            status=MatchStatus.COMPLETED.value,
        )
        test_db.add(match)
        semi_matches.append(match)

    final = models.Match(
        tournament_id=tournament.id,
        stage=MatchStage.GRAND_FINAL.value,
        team1_id=1,
        team2_id=2,
        status=MatchStatus.COMPLETED.value,
    )
    test_db.add(final)
    test_db.flush()

    player_ratings = {
        1: [0.98, 0.95, 0.80, 0.80, 0.80],
        2: [0.98, 0.80, 0.80, 0.80, 0.80],
        3: [1.10, 1.20, 0.80, 0.80, 0.80],
        4: [1.10, 0.80, 0.80, 0.80, 0.80],
        5: [1.30, 0.80, 0.80, 0.80, 0.80],
        6: [1.30, 0.80, 0.80, 0.80, 0.80],
        7: [1.30, 0.80, 0.80, 0.80, 0.80],
        8: [1.30, 0.80, 0.80, 0.80, 0.80],
    }
    qf_match_by_team = {
        team_id: match
        for match, pair in zip(qf_matches, qf_pairs)
        for team_id in pair
    }
    semi_match_by_team = {
        team_id: match
        for match, pair in zip(semi_matches, [(1, 3), (2, 4)])
        for team_id in pair
    }

    for team_id, ratings in player_ratings.items():
        if team_id in (1, 2):
            match = final
        elif team_id in (3, 4):
            match = semi_match_by_team[team_id]
        else:
            match = qf_match_by_team[team_id]

        team = test_db.query(models.Team).filter_by(id=team_id).one()
        for player, rating in zip(team.players, ratings):
            test_db.add(models.PlayerMatchStat(
                match_id=match.id,
                player_id=player.id,
                team_id=team_id,
                kills=20,
                deaths=15,
                assists=5,
                adr=85.0,
                rating=rating,
            ))
    test_db.commit()

    svc = TournamentService(test_db)
    major_stats = svc.get_tournament_stats(tournament.id)
    semifinalist_player_id = test_db.query(models.Player).filter_by(team_id=3).all()[1].id
    quarterfinal_star_id = test_db.query(models.Player).filter_by(team_id=5).first().id
    major_evp_ids = [player["player_id"] for player in major_stats["evps"]]

    assert major_stats["mvp"]["team_id"] == tournament.champion_id
    assert semifinalist_player_id in major_evp_ids
    assert all(player["rating"] >= 1.15 for player in major_stats["evps"])
    assert major_evp_ids.index(semifinalist_player_id) < major_evp_ids.index(quarterfinal_star_id)

    tournament.tier = TournamentTier.S_TIER.value
    test_db.commit()
    non_major_stats = svc.get_tournament_stats(tournament.id)
    non_major_evp_ids = [player["player_id"] for player in non_major_stats["evps"]]
    assert all(player["rating"] >= 1.15 for player in non_major_stats["evps"])
    assert non_major_evp_ids.index(quarterfinal_star_id) < non_major_evp_ids.index(semifinalist_player_id)


def test_tournament_history_lists_completed_events_newest_first(test_db):
    completed_events = [
        models.Tournament(
            name="Older Event",
            tier=TournamentTier.S_TIER.value,
            year=2025,
            month=12,
            status=TournamentStatus.COMPLETED.value,
        ),
        models.Tournament(
            name="Newer Event",
            tier=TournamentTier.MAJOR.value,
            year=2026,
            month=5,
            status=TournamentStatus.COMPLETED.value,
        ),
    ]
    upcoming_event = models.Tournament(
        name="Upcoming Event",
        tier=TournamentTier.S_TIER.value,
        year=2026,
        month=7,
        status=TournamentStatus.UPCOMING.value,
    )
    test_db.add_all([*completed_events, upcoming_event])
    test_db.commit()

    history = get_tournament_history(test_db)

    assert [event.name for event in history] == ["Newer Event", "Older Event"]


def test_calendar_month_advance_opens_transfers_until_tournament_start(test_db):
    service = TournamentService(test_db)
    state = service.get_or_create_calendar_state()
    finished_event = state.active_tournament
    assert state.tournament_start_pending
    assert finished_event is not None
    assert not finished_event.participants

    finished_event.status = TournamentStatus.COMPLETED.value
    state.tournament_start_pending = False
    test_db.commit()

    state = service.advance_calendar()
    next_event = state.active_tournament
    assert state.current_month == 2
    assert state.tournament_start_pending
    assert next_event is not None
    assert next_event.status == TournamentStatus.UPCOMING.value
    assert not next_event.participants
    assert transfer_lock_name(test_db, 1) is None

    state = service.start_current_month_tournaments()
    next_event = state.active_tournament
    assert not state.tournament_start_pending
    assert next_event is not None
    assert next_event.status == TournamentStatus.ACTIVE.value
    assert any(participant.team_id == 1 for participant in next_event.participants)
    assert transfer_lock_name(test_db, 1) == next_event.name


def test_calendar_skips_months_without_scheduled_tournaments(test_db):
    service = TournamentService(test_db)
    state = service.get_or_create_calendar_state()
    march_event = (
        test_db.query(models.Tournament)
        .filter_by(year=2026, month=3)
        .first()
    )
    assert march_event is not None
    march_event.status = TournamentStatus.COMPLETED.value
    state.current_month = 3
    state.active_tournament_id = march_event.id
    state.tournament_start_pending = False
    test_db.commit()

    state = service.advance_calendar()

    assert (state.current_year, state.current_month) == (2026, 5)
    assert state.tournament_start_pending
    assert state.active_tournament is not None
    assert state.active_tournament.month == 5


def _add_completed_series_maps(
    db,
    *,
    tournament_id: int,
    team1_id: int,
    team2_id: int,
    map_count: int,
    rating_for_player,
    stage=MatchStage.GRAND_FINAL.value,
):
    """Seed a completed match with map_count PlayerMatchStat rows per roster player."""
    match = models.Match(
        tournament_id=tournament_id,
        stage=stage,
        status=MatchStatus.COMPLETED.value,
        team1_id=team1_id,
        team2_id=team2_id,
        winner_id=team1_id,
    )
    db.add(match)
    db.flush()

    for map_number in range(1, map_count + 1):
        map_result = models.MapResult(
            match_id=match.id,
            map_number=map_number,
            map_name="Mirage",
            winner_id=team1_id,
        )
        db.add(map_result)
        db.flush()
        for team_id in (team1_id, team2_id):
            team = db.query(models.Team).filter_by(id=team_id).one()
            for player in team.players:
                db.add(models.PlayerMatchStat(
                    match_id=match.id,
                    map_result_id=map_result.id,
                    player_id=player.id,
                    team_id=team_id,
                    kills=25,
                    deaths=15,
                    assists=6,
                    adr=90.0,
                    rating=rating_for_player(player),
                ))
    return match


def test_year_end_archive_tracks_awards_and_compacts_match_stats(test_db):
    tournament = models.Tournament(
        name="Year-End Test Event",
        tier=TournamentTier.S_TIER.value,
        year=2026,
        month=12,
        status=TournamentStatus.COMPLETED.value,
        champion_id=1,
    )
    test_db.add(tournament)
    test_db.flush()
    test_db.add_all([
        models.TournamentParticipant(
            tournament_id=tournament.id,
            team_id=1,
            seed=1,
            placement="Champion",
        ),
        models.TournamentParticipant(
            tournament_id=tournament.id,
            team_id=2,
            seed=2,
            placement="Runner-Up",
        ),
    ])
    superstar = test_db.query(models.Player).filter_by(team_id=1).first()
    _add_completed_series_maps(
        test_db,
        tournament_id=tournament.id,
        team1_id=1,
        team2_id=2,
        map_count=20,
        rating_for_player=lambda player: 1.40 if player.id == superstar.id else 1.20,
    )
    test_db.add(models.CalendarState(
        current_year=2026,
        current_month=12,
        manager_id=1,
        active_tournament_id=tournament.id,
    ))
    test_db.commit()

    service = TournamentService(test_db)
    state = service.advance_calendar()

    assert (state.current_year, state.current_month) == (2027, 1)
    assert test_db.query(models.PlayerMatchStat).count() == 0
    assert test_db.query(models.TournamentPlayerStatArchive).filter_by(
        tournament_id=tournament.id
    ).count() == 10

    season = get_yearly_top_20(test_db)[0]
    assert season["year"] == 2026
    assert len(season["players"]) == 10
    assert season["players"][0]["player_id"] == superstar.id
    assert season["players"][0]["mvp_count"] == 1
    assert sum(player["evp_count"] for player in season["players"]) == 9
    validated_season = YearEndTop20Response.model_validate(season)
    assert validated_season.players[0].rank == 1
    superstar_honors = validated_season.players[0].honors
    assert len(superstar_honors) == 1
    assert superstar_honors[0].event_name == tournament.name
    assert superstar_honors[0].award == "MVP"
    assert superstar_honors[0].month == 12
    runner_up_player = next(player for player in season["players"] if player["player_id"] != superstar.id)
    assert runner_up_player["honors"][0]["award"].startswith("EVP #")

    archived_event = service.get_tournament_stats(tournament.id)
    assert archived_event["mvp"]["player_id"] == superstar.id
    assert len(archived_event["player_stats"]) == 10

    service.archive_year_end_stats(2026)
    test_db.commit()
    assert test_db.query(models.YearEndPlayerArchive).filter_by(year=2026).count() == 10


def test_year_end_tracks_only_user_team_ratings_and_grows_potential_after_109(test_db):
    tournament = models.Tournament(
        name="User Team Development Event",
        tier=TournamentTier.B_TIER.value,
        year=2026,
        month=12,
        status=TournamentStatus.COMPLETED.value,
        champion_id=2,
    )
    test_db.add(tournament)
    test_db.flush()
    user_players = test_db.query(models.Player).filter_by(team_id=1).all()
    starting_ratings = {player.id: player.Rating for player in user_players}
    _add_completed_series_maps(
        test_db,
        tournament_id=tournament.id,
        team1_id=2,
        team2_id=1,
        map_count=3,
        rating_for_player=lambda player: 1.10 if player.team_id == 1 else 1.40,
    )
    test_db.commit()

    TournamentService(test_db).archive_year_end_stats(2026)
    archived = get_user_team_yearly_ratings(test_db)

    assert len(archived) == 5
    assert {entry.team_id for entry in archived} == {1}
    assert {entry.player_id for entry in archived} == {player.id for player in user_players}
    assert all(entry.rating == pytest.approx(1.10) for entry in archived)
    assert all(entry.maps_played == 3 for entry in archived)
    assert all(entry.potential > starting_ratings[entry.player_id] for entry in archived)

    TournamentService(test_db).archive_year_end_stats(2026)
    assert len(get_user_team_yearly_ratings(test_db)) == 5


def test_year_end_top_20_eligibility_and_sample_size(test_db):
    full_campaign = test_db.query(models.Player).filter_by(team_id=1).first()
    short_spike = test_db.query(models.Player).filter_by(team_id=3).first()
    a_plus_event = models.Tournament(
        name="A-Tier Campaign",
        tier=TournamentTier.A_TIER.value,
        year=2026,
        month=1,
        status=TournamentStatus.COMPLETED.value,
    )
    short_event = models.Tournament(
        name="S-Tier Spike",
        tier=TournamentTier.S_TIER.value,
        year=2026,
        month=2,
        status=TournamentStatus.COMPLETED.value,
    )
    test_db.add_all([a_plus_event, short_event])
    test_db.flush()

    _add_completed_series_maps(
        test_db,
        tournament_id=a_plus_event.id,
        team1_id=1,
        team2_id=2,
        map_count=YEAR_END_MIN_MAPS,
        rating_for_player=lambda player: 1.30 if player.id == full_campaign.id else 1.20,
    )
    _add_completed_series_maps(
        test_db,
        tournament_id=short_event.id,
        team1_id=3,
        team2_id=4,
        map_count=3,
        rating_for_player=lambda player: 1.98 if player.id == short_spike.id else 1.20,
    )

    service = TournamentService(test_db)
    service.archive_year_end_stats(2026)

    archived = {
        row.player_id: row
        for row in test_db.query(models.YearEndPlayerArchive).filter_by(year=2026).all()
    }
    assert full_campaign.id in archived
    assert archived[full_campaign.id].rating == 1.30
    assert short_spike.id not in archived
    assert _year_end_ranking_score(1.30, YEAR_END_MIN_MAPS) > _year_end_ranking_score(1.98, 3)


def test_year_end_top_20_ignores_b_and_c_tiers_but_keeps_progression_totals(
    test_db, monkeypatch
):
    a_plus_player = test_db.query(models.Player).filter_by(team_id=1).first()
    lower_tier_star = test_db.query(models.Player).filter_by(team_id=3).first()
    tournaments = [
        models.Tournament(
            name="A-Tier Event",
            tier=TournamentTier.A_TIER.value,
            year=2026,
            month=1,
            status=TournamentStatus.COMPLETED.value,
        ),
        models.Tournament(
            name="B-Tier Event",
            tier=TournamentTier.B_TIER.value,
            year=2026,
            month=2,
            status=TournamentStatus.COMPLETED.value,
        ),
        models.Tournament(
            name="C-Tier Event",
            tier=TournamentTier.C_TIER.value,
            year=2026,
            month=3,
            status=TournamentStatus.COMPLETED.value,
        ),
    ]
    test_db.add_all(tournaments)
    test_db.flush()

    _add_completed_series_maps(
        test_db,
        tournament_id=tournaments[0].id,
        team1_id=1,
        team2_id=2,
        map_count=YEAR_END_MIN_MAPS,
        rating_for_player=lambda player: 1.20,
    )
    for tournament in tournaments[1:]:
        _add_completed_series_maps(
            test_db,
            tournament_id=tournament.id,
            team1_id=3,
            team2_id=4,
            map_count=15,
            rating_for_player=lambda player: 1.98 if player.id == lower_tier_star.id else 1.20,
        )

    progression_totals = {}
    monkeypatch.setattr(
        "app.services.tournament_service.apply_yearly_progression",
        lambda db, year, totals: progression_totals.update(totals),
    )
    TournamentService(test_db).archive_year_end_stats(2026)

    archived_player_ids = {
        row.player_id
        for row in test_db.query(models.YearEndPlayerArchive).filter_by(year=2026).all()
    }
    assert a_plus_player.id in archived_player_ids
    assert lower_tier_star.id not in archived_player_ids
    assert progression_totals[lower_tier_star.id]["maps_played"] == 30


def test_year_end_sos_rewards_maps_against_top_20_teams(test_db):
    lower_sos_player = test_db.query(models.Player).filter_by(team_id=1).first()
    higher_sos_player = test_db.query(models.Player).filter_by(team_id=3).first()
    outside_top_20 = models.Team(
        name="Team 21",
        ranking=21,
        ranking_points=0,
        budget=1_000_000,
    )
    event = models.Tournament(
        name="SOS Test Event",
        tier=TournamentTier.S_TIER.value,
        year=2026,
        month=1,
        status=TournamentStatus.COMPLETED.value,
    )
    test_db.add_all([outside_top_20, event])
    test_db.flush()

    _add_completed_series_maps(
        test_db,
        tournament_id=event.id,
        team1_id=1,
        team2_id=outside_top_20.id,
        map_count=YEAR_END_MIN_MAPS,
        rating_for_player=lambda player: 1.20,
    )
    _add_completed_series_maps(
        test_db,
        tournament_id=event.id,
        team1_id=3,
        team2_id=2,
        map_count=YEAR_END_MIN_MAPS,
        rating_for_player=lambda player: 1.20,
    )

    TournamentService(test_db).archive_year_end_stats(2026)

    archived = {
        row.player_id: row
        for row in test_db.query(models.YearEndPlayerArchive).filter_by(year=2026).all()
    }
    assert (
        archived[higher_sos_player.id].maps_played
        == archived[lower_sos_player.id].maps_played
        == YEAR_END_MIN_MAPS
    )
    assert archived[higher_sos_player.id].rating == archived[lower_sos_player.id].rating == 1.20
    assert archived[higher_sos_player.id].rank < archived[lower_sos_player.id].rank


def test_december_advance_finishes_bracket_before_archiving(test_db):
    tournament = models.Tournament(
        name="December Final",
        tier=TournamentTier.S_TIER.value,
        year=2026,
        month=12,
        status=TournamentStatus.ACTIVE.value,
    )
    test_db.add(tournament)
    test_db.flush()
    test_db.add(models.CalendarState(
        current_year=2026,
        current_month=12,
        manager_id=1,
        active_tournament_id=tournament.id,
    ))
    test_db.commit()

    state = TournamentService(test_db).advance_calendar()

    assert (state.current_year, state.current_month) == (2027, 1)
    assert tournament.status == TournamentStatus.COMPLETED.value
    assert test_db.query(models.Match).filter_by(
        tournament_id=tournament.id,
        status=MatchStatus.SCHEDULED.value,
    ).count() == 0
    assert test_db.query(models.TournamentPlayerStatArchive).filter_by(
        tournament_id=tournament.id
    ).count() > 0
    assert test_db.query(models.TournamentPlayerStatArchive).filter(
        models.TournamentPlayerStatArchive.tournament_id == tournament.id,
        models.TournamentPlayerStatArchive.maps_played >= YEAR_END_MIN_MAPS,
    ).count() == 0
    assert test_db.query(models.YearEndPlayerArchive).filter_by(year=2026).count() == 0
    assert test_db.query(models.PlayerMatchStat).filter(
        models.PlayerMatchStat.match_id.in_(
            test_db.query(models.Match.id).filter_by(tournament_id=tournament.id)
        )
    ).count() == 0
