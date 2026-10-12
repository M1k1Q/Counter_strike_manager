from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app import models
from app.domain.enums import MatchStage, MatchStatus, TournamentStatus, TournamentTier, MatchFormats
from app.services.match_engine import MatchEngine

CIRCUIT_EVENTS = [
    {"month": 1, "name": "IEM Katowice 2026", "tier": TournamentTier.S_TIER, "prize": 1_000_000, "min_rank": 16, "format": "Bo5"},
    {"month": 2, "name": "BLAST Premier Spring Groups", "tier": TournamentTier.A_TIER, "prize": 400_000, "min_rank": 16, "format": "Bo5"},
    {"month": 3, "name": "ESL Pro League Spring", "tier": TournamentTier.S_TIER, "prize": 750_000, "min_rank": 16, "format": "Bo5"},
    {"month": 5, "name": "PGL CS2 Major", "tier": TournamentTier.MAJOR, "prize": 1_250_000, "min_rank": 16, "format": "Bo5"},
    {"month": 6, "name": "BLAST Premier Spring Final", "tier": TournamentTier.S_TIER, "prize": 500_000, "min_rank": 16, "format": "Bo5"},
    {"month": 7, "name": "IEM Cologne - Cathedral of CS", "tier": TournamentTier.S_TIER, "prize": 1_000_000, "min_rank": 16, "format": "Bo5"},
    {"month": 8, "name": "Roobet Cup Global", "tier": TournamentTier.A_TIER, "prize": 350_000, "min_rank": 16, "format": "Bo5"},
    {"month": 9, "name": "ESL Pro League Autumn", "tier": TournamentTier.S_TIER, "prize": 750_000, "min_rank": 16, "format": "Bo5"},
    {"month": 10, "name": "Thunderpick World Championship", "tier": TournamentTier.A_TIER, "prize": 600_000, "min_rank": 16, "format": "Bo5"},
    {"month": 11, "name": "Perfect World Winter Major", "tier": TournamentTier.MAJOR, "prize": 1_250_000, "min_rank": 16, "format": "Bo5"},
    {"month": 12, "name": "BLAST Premier World Final", "tier": TournamentTier.S_TIER, "prize": 1_000_000, "min_rank": 16, "format": "Bo5"},
]


class TournamentService:
    def __init__(self, db: Session):
        self.db = db
        self.match_engine = MatchEngine(db)

    def get_or_create_calendar_state(self) -> models.CalendarState:
        """Get or initialize the calendar state for the career."""
        manager = self.db.query(models.Manager).first()
        state = self.db.query(models.CalendarState).first()
        if not state:
            state = models.CalendarState(
                current_year=2026,
                current_month=1,
                manager_id=manager.id if manager else None,
            )
            self.db.add(state)
            self.db.commit()
            self.db.refresh(state)

        # Make sure circuit tournaments exist for this year
        self.ensure_circuit_tournaments(state.current_year)

        # Set active tournament if not set
        if not state.active_tournament_id:
            active_t = self.get_tournament_for_month(state.current_year, state.current_month)
            if active_t:
                state.active_tournament_id = active_t.id
                active_t.status = TournamentStatus.ACTIVE
                self.db.commit()
                self.db.refresh(state)

        return state

    def ensure_circuit_tournaments(self, year: int) -> List[models.Tournament]:
        """Ensure all events for the season year exist in the database."""
        existing = self.db.query(models.Tournament).filter(models.Tournament.year == year).all()
        if len(existing) >= len(CIRCUIT_EVENTS):
            return existing

        created = []
        for event in CIRCUIT_EVENTS:
            t = (
                self.db.query(models.Tournament)
                .filter(models.Tournament.year == year, models.Tournament.month == event["month"])
                .first()
            )
            if not t:
                t = models.Tournament(
                    name=event["name"],
                    tier=event["tier"].value,
                    prize_pool=event["prize"],
                    year=year,
                    month=event["month"],
                    min_rank_required=event["min_rank"],
                    format=event["format"],
                    status=TournamentStatus.UPCOMING.value,
                )
                self.db.add(t)
                created.append(t)

        self.db.commit()
        return self.db.query(models.Tournament).filter(models.Tournament.year == year).order_by(models.Tournament.month.asc()).all()

    def get_tournament_for_month(self, year: int, month: int) -> Optional[models.Tournament]:
        """Find tournament for a given month or the closest upcoming tournament in that year."""
        t = (
            self.db.query(models.Tournament)
            .filter(models.Tournament.year == year, models.Tournament.month == month)
            .first()
        )
        if not t:
            t = (
                self.db.query(models.Tournament)
                .filter(models.Tournament.year == year, models.Tournament.month >= month)
                .order_by(models.Tournament.month.asc())
                .first()
            )
        return t

    def check_invite_status(self, tournament: models.Tournament, team: Optional[models.Team]) -> Dict[str, Any]:
        """Check if a team is invited to a tournament based on ranking cutoff."""
        if not team:
            return {"invited": False, "reason": "No team selected", "cutoff": tournament.min_rank_required}

        cutoff = tournament.min_rank_required or 8
        is_invited = bool(team.ranking and team.ranking <= cutoff)
        return {
            "invited": is_invited,
            "team_rank": team.ranking,
            "cutoff": cutoff,
            "reason": (
                f"Rank #{team.ranking} qualifies (Top {cutoff} invited)"
                if is_invited
                else f"Rank #{team.ranking} is outside the Top {cutoff} invite cutoff"
            ),
        }

    def initialize_tournament(self, tournament_id: int) -> models.Tournament:
        """
        Seed teams and generate group stage matches for a 16-team tournament.
        Uses snake seeding:
          Group A: Seeds 1, 4, 5, 8, 9, 12, 13, 16
          Group B: Seeds 2, 3, 6, 7, 10, 11, 14, 15
        Generates 7 rounds of round-robin matches within each group (28 matches per group).
        """
        tournament = self.db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")

        # If already has participants, return
        if tournament.participants:
            return tournament

        # Get all teams ordered by ranking
        all_teams = self.db.query(models.Team).order_by(models.Team.ranking.asc()).all()
        if len(all_teams) < 16:
            raise ValueError("Not enough teams to populate tournament (requires at least 16)")

        manager = self.db.query(models.Manager).first()
        user_team = manager.team if (manager and manager.team) else None

        cutoff = tournament.min_rank_required or 16

        # Determine 16 invited teams:
        # Check if user team qualifies or gets invited
        invited_teams = []
        user_included = False

        if user_team and user_team.ranking and user_team.ranking <= cutoff:
            invited_teams.append(user_team)
            user_included = True

        for t in all_teams:
            if len(invited_teams) >= 16:
                break
            if user_included and t.id == user_team.id:
                continue
            invited_teams.append(t)

        # Sort invited teams by ranking to assign Seeds 1..16
        invited_teams.sort(key=lambda t: t.ranking if t.ranking else 999)

        # Snake seeding into Group A and Group B
        # Seed indices (0-indexed):
        # Group A: seeds 0, 3, 4, 7, 8, 11, 12, 15 (Seeds 1, 4, 5, 8, 9, 12, 13, 16)
        # Group B: seeds 1, 2, 5, 6, 9, 10, 13, 14 (Seeds 2, 3, 6, 7, 10, 11, 14, 15)
        group_a_indices = {0, 3, 4, 7, 8, 11, 12, 15}

        participants = []
        for seed_idx, team in enumerate(invited_teams, 1):
            zero_idx = seed_idx - 1
            grp = "A" if zero_idx in group_a_indices else "B"

            part = models.TournamentParticipant(
                tournament_id=tournament.id,
                team_id=team.id,
                seed=seed_idx,
                group_name=grp,
                wins=0,
                losses=0,
                rounds_won=0,
                rounds_lost=0,
                eliminated=False,
                placement="Group Stage",
            )
            self.db.add(part)
            participants.append(part)

        self.db.flush()

        # Generate Group Stage Matches (Round-Robin within each group of 8 teams)
        # Berger tables for 8 teams (7 rounds x 4 matches = 28 matches per group)
        round_pairings = [
            [(0, 7), (1, 6), (2, 5), (3, 4)],  # Round 1
            [(7, 4), (5, 3), (6, 2), (0, 1)],  # Round 2
            [(1, 7), (2, 0), (3, 6), (4, 5)],  # Round 3
            [(7, 5), (6, 4), (0, 3), (1, 2)],  # Round 4
            [(2, 7), (3, 1), (4, 0), (5, 6)],  # Round 5
            [(7, 6), (0, 5), (1, 4), (2, 3)],  # Round 6
            [(3, 7), (4, 2), (5, 1), (6, 0)],  # Round 7
        ]

        for grp_name in ["A", "B"]:
            grp_teams = [p.team_id for p in participants if p.group_name == grp_name]
            for round_num, pairings in enumerate(round_pairings, 1):
                for idx1, idx2 in pairings:
                    match = models.Match(
                        tournament_id=tournament.id,
                        stage=MatchStage.GROUP_STAGE.value,
                        group_name=grp_name,
                        round_name=f"Group {grp_name} - Round {round_num}",
                        team1_id=grp_teams[idx1],
                        team2_id=grp_teams[idx2],
                        format="Bo1" if "Major" not in tournament.tier else "Bo3",
                        status=MatchStatus.SCHEDULED.value,
                    )
                    self.db.add(match)

        tournament.status = TournamentStatus.ACTIVE.value
        self.db.commit()
        self.db.refresh(tournament)
        return tournament

    def play_match(self, match_id: int) -> models.Match:
        """Simulate a match and advance tournament bracket state if needed."""
        match = self.db.query(models.Match).filter(models.Match.id == match_id).first()
        if not match:
            raise ValueError(f"Match {match_id} not found")

        if match.status == MatchStatus.COMPLETED.value:
            return match

        # Simulate through match engine
        self.match_engine.simulate_series(match)

        # Update participant statistics if tournament match
        if match.tournament_id:
            tournament = self.db.query(models.Tournament).filter(models.Tournament.id == match.tournament_id).first()
            p1 = (
                self.db.query(models.TournamentParticipant)
                .filter(models.TournamentParticipant.tournament_id == match.tournament_id, models.TournamentParticipant.team_id == match.team1_id)
                .first()
            )
            p2 = (
                self.db.query(models.TournamentParticipant)
                .filter(models.TournamentParticipant.tournament_id == match.tournament_id, models.TournamentParticipant.team_id == match.team2_id)
                .first()
            )

            # Sum rounds from map results
            for m in match.maps:
                if p1:
                    p1.rounds_won += m.team1_score
                    p1.rounds_lost += m.team2_score
                if p2:
                    p2.rounds_won += m.team2_score
                    p2.rounds_lost += m.team1_score

            if match.winner_id == match.team1_id:
                if p1: p1.wins += 1
                if p2: p2.losses += 1
            else:
                if p2: p2.wins += 1
                if p1: p1.losses += 1

            self.db.commit()

            # Check if current stage is fully resolved and advance to next stage
            self.check_and_advance_stage(tournament)

        return match

    def simulate_all_ai_matches(self, tournament_id: int) -> int:
        """Simulate pending matches between two AI teams."""
        tournament = self.db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
        if not tournament:
            return 0

        manager = self.db.query(models.Manager).first()
        user_team_id = manager.team_id if manager else None

        pending_matches = (
            self.db.query(models.Match)
            .filter(
                models.Match.tournament_id == tournament_id,
                models.Match.status == MatchStatus.SCHEDULED.value,
            )
            .all()
        )

        simulated_count = 0
        for m in pending_matches:
            # Skip if user team is in this match
            if user_team_id and (m.team1_id == user_team_id or m.team2_id == user_team_id):
                continue
            self.play_match(m.id)
            simulated_count += 1

        return simulated_count

    def check_and_advance_stage(self, tournament: models.Tournament) -> None:
        """
        Check if current tournament stage is complete and advance to next:
        1. Group Stage (56 matches) -> Create Quarter-Finals (4 matches, Bo3)
        2. Quarter-Finals (4 matches) -> Create Semi-Finals (2 matches, Bo3)
        3. Semi-Finals (2 matches) -> Create Grand Final (1 match, Bo5)
        4. Grand Final (1 match) -> Conclude tournament & assign MVP/EVP
        """
        matches = tournament.matches

        # 1. Check Group Stage
        group_matches = [m for m in matches if m.stage == MatchStage.GROUP_STAGE.value]
        if group_matches and all(m.status == MatchStatus.COMPLETED.value for m in group_matches):
            playoff_matches = [
                m for m in matches
                if m.stage in [MatchStage.QUARTER_FINAL.value, MatchStage.SEMI_FINAL.value, MatchStage.GRAND_FINAL.value]
            ]
            if not playoff_matches:
                self.create_quarterfinals(tournament)
                return

        # 2. Check Quarter-Finals
        qf_matches = [m for m in matches if m.stage == MatchStage.QUARTER_FINAL.value]
        if qf_matches and len(qf_matches) == 4 and all(m.status == MatchStatus.COMPLETED.value for m in qf_matches):
            semi_matches = [m for m in matches if m.stage == MatchStage.SEMI_FINAL.value]
            if not semi_matches:
                self.create_semifinals(tournament, qf_matches)
                return

        # 3. Check Semi-Finals
        semi_matches = [m for m in matches if m.stage == MatchStage.SEMI_FINAL.value]
        if semi_matches and len(semi_matches) == 2 and all(m.status == MatchStatus.COMPLETED.value for m in semi_matches):
            gf_matches = [m for m in matches if m.stage == MatchStage.GRAND_FINAL.value]
            if not gf_matches:
                self.create_grand_final(tournament, semi_matches)
                return

        # 4. Check Grand Final
        gf_matches = [m for m in matches if m.stage == MatchStage.GRAND_FINAL.value]
        if gf_matches and all(m.status == MatchStatus.COMPLETED.value for m in gf_matches):
            if tournament.status != TournamentStatus.COMPLETED.value:
                self.conclude_tournament(tournament, gf_matches[0])

    def create_quarterfinals(self, tournament: models.Tournament) -> None:
        """Calculate group standings and pair Group A top 4 with Group B top 4."""
        participants = tournament.participants

        group_a = [p for p in participants if p.group_name == "A"]
        group_b = [p for p in participants if p.group_name == "B"]

        # Sort by: wins DESC, round differential DESC, seed ASC
        def sort_group(p: models.TournamentParticipant):
            round_diff = p.rounds_won - p.rounds_lost
            return (p.wins, round_diff, -p.seed)

        sorted_a = sorted(group_a, key=sort_group, reverse=True)
        sorted_b = sorted(group_b, key=sort_group, reverse=True)

        if len(sorted_a) < 4 or len(sorted_b) < 4:
            return

        # Mark bottom 4 of each group as eliminated in Group Stage
        for p in sorted_a[4:] + sorted_b[4:]:
            p.eliminated = True
            p.placement = "Group Stage"

        # Top 4 of each group reach Quarter-Finals
        for p in sorted_a[:4] + sorted_b[:4]:
            p.placement = "Quarterfinalist"

        a1, a2, a3, a4 = sorted_a[0], sorted_a[1], sorted_a[2], sorted_a[3]
        b1, b2, b3, b4 = sorted_b[0], sorted_b[1], sorted_b[2], sorted_b[3]

        # Standard IEM / Major Playoffs Bracket:
        # QF1: A1 vs B4
        # QF2: B2 vs A3
        # QF3: B1 vs A4
        # QF4: A2 vs B3
        qf1 = models.Match(
            tournament_id=tournament.id,
            stage=MatchStage.QUARTER_FINAL.value,
            round_name="Quarter-Final 1 (A1 vs B4)",
            team1_id=a1.team_id,
            team2_id=b4.team_id,
            format="Bo3",
            status=MatchStatus.SCHEDULED.value,
        )
        qf2 = models.Match(
            tournament_id=tournament.id,
            stage=MatchStage.QUARTER_FINAL.value,
            round_name="Quarter-Final 2 (B2 vs A3)",
            team1_id=b2.team_id,
            team2_id=a3.team_id,
            format="Bo3",
            status=MatchStatus.SCHEDULED.value,
        )
        qf3 = models.Match(
            tournament_id=tournament.id,
            stage=MatchStage.QUARTER_FINAL.value,
            round_name="Quarter-Final 3 (B1 vs A4)",
            team1_id=b1.team_id,
            team2_id=a4.team_id,
            format="Bo3",
            status=MatchStatus.SCHEDULED.value,
        )
        qf4 = models.Match(
            tournament_id=tournament.id,
            stage=MatchStage.QUARTER_FINAL.value,
            round_name="Quarter-Final 4 (A2 vs B3)",
            team1_id=a2.team_id,
            team2_id=b3.team_id,
            format="Bo3",
            status=MatchStatus.SCHEDULED.value,
        )

        self.db.add_all([qf1, qf2, qf3, qf4])
        self.db.commit()

    def create_semifinals(self, tournament: models.Tournament, qf_matches: List[models.Match]) -> None:
        """Pair QF1 winner vs QF2 winner, and QF3 winner vs QF4 winner."""
        # Find matches by round name number
        qf_map = {}
        for m in qf_matches:
            for num in ["1", "2", "3", "4"]:
                if f"Quarter-Final {num}" in m.round_name:
                    qf_map[num] = m
                    break

        qf1 = qf_map.get("1", qf_matches[0])
        qf2 = qf_map.get("2", qf_matches[1])
        qf3 = qf_map.get("3", qf_matches[2])
        qf4 = qf_map.get("4", qf_matches[3])

        # Mark QF losers as eliminated (Quarterfinalist)
        for qf in [qf1, qf2, qf3, qf4]:
            loser_id = qf.team1_id if qf.winner_id == qf.team2_id else qf.team2_id
            for p in tournament.participants:
                if p.team_id == loser_id:
                    p.eliminated = True
                    p.placement = "Quarterfinalist"

        # Mark QF winners as Semifinalist
        for qf in [qf1, qf2, qf3, qf4]:
            winner_id = qf.winner_id
            for p in tournament.participants:
                if p.team_id == winner_id:
                    p.placement = "Semifinalist"

        # SF1: Winner QF1 vs Winner QF2 (Bo3)
        sf1 = models.Match(
            tournament_id=tournament.id,
            stage=MatchStage.SEMI_FINAL.value,
            round_name="Semi-Final 1 (QF1 vs QF2)",
            team1_id=qf1.winner_id,
            team2_id=qf2.winner_id,
            format="Bo3",
            status=MatchStatus.SCHEDULED.value,
        )

        # SF2: Winner QF3 vs Winner QF4 (Bo3)
        sf2 = models.Match(
            tournament_id=tournament.id,
            stage=MatchStage.SEMI_FINAL.value,
            round_name="Semi-Final 2 (QF3 vs QF4)",
            team1_id=qf3.winner_id,
            team2_id=qf4.winner_id,
            format="Bo3",
            status=MatchStatus.SCHEDULED.value,
        )

        self.db.add_all([sf1, sf2])
        self.db.commit()

    def create_grand_final(self, tournament: models.Tournament, semi_matches: List[models.Match]) -> None:
        """Create Grand Final between the two semi-final winners, BO5 format."""
        sf1, sf2 = semi_matches[0], semi_matches[1]
        w1_id = sf1.winner_id
        w2_id = sf2.winner_id

        # Mark losers of semis as eliminated
        l1_id = sf1.team1_id if sf1.winner_id == sf1.team2_id else sf1.team2_id
        l2_id = sf2.team1_id if sf2.winner_id == sf2.team2_id else sf2.team2_id

        for p in tournament.participants:
            if p.team_id in [l1_id, l2_id]:
                p.eliminated = True
                p.placement = "Semifinals"
            elif p.team_id in [w1_id, w2_id]:
                p.placement = "Runner-Up"  # At least runner up

        # Finals should be BO5
        gf = models.Match(
            tournament_id=tournament.id,
            stage=MatchStage.GRAND_FINAL.value,
            round_name="Grand Final",
            team1_id=w1_id,
            team2_id=w2_id,
            format="Bo5",
            status=MatchStatus.SCHEDULED.value,
        )

        self.db.add(gf)
        self.db.commit()

    def conclude_tournament(self, tournament: models.Tournament, gf_match: models.Match) -> None:
        """Crown champion, distribute prize pool, update career stats, and recalculate world rankings."""
        champion_id = gf_match.winner_id
        runner_up_id = gf_match.team1_id if gf_match.winner_id == gf_match.team2_id else gf_match.team2_id

        tournament.champion_id = champion_id
        tournament.status = TournamentStatus.COMPLETED.value

        prize_total = tournament.prize_pool or 1_000_000

        # Update placement for participants
        for p in tournament.participants:
            if p.team_id == champion_id:
                p.placement = "Champion"
                p.eliminated = False
            elif p.team_id == runner_up_id:
                p.placement = "Runner-Up"
                p.eliminated = True

        # Check if manager's team won prize money & career points
        manager = self.db.query(models.Manager).first()
        if manager and manager.team_id:
            m_team_id = manager.team_id
            if m_team_id == champion_id:
                manager.budget += int(prize_total * 0.50)
                manager.career_points += 1000
            elif m_team_id == runner_up_id:
                manager.budget += int(prize_total * 0.25)
                manager.career_points += 600
            elif any(p.team_id == m_team_id and p.placement == "Semifinals" for p in tournament.participants):
                manager.budget += int(prize_total * 0.10)
                manager.career_points += 350
            elif any(p.team_id == m_team_id and p.placement == "Quarterfinalist" for p in tournament.participants):
                manager.budget += int(prize_total * 0.025)
                manager.career_points += 175
            elif any(p.team_id == m_team_id for p in tournament.participants):
                manager.budget += int(prize_total * 0.005)
                manager.career_points += 50

        # Award ranking points to participating teams
        for p in tournament.participants:
            team = p.team
            if not team:
                continue
            curr_pts = team.ranking_points or 0
            if p.placement == "Champion":
                team.ranking_points = curr_pts + 1000
            elif p.placement == "Runner-Up":
                team.ranking_points = curr_pts + 600
            elif p.placement == "Semifinals":
                team.ranking_points = curr_pts + 350
            elif p.placement == "Quarterfinalist":
                team.ranking_points = curr_pts + 175
            else:
                team.ranking_points = curr_pts + 50

        self.db.flush()

        # Recalculate global team rankings 1 to N based on accumulated ranking points
        all_teams = self.db.query(models.Team).order_by(models.Team.ranking_points.desc()).all()
        for idx, t in enumerate(all_teams, 1):
            t.ranking = idx

        self.db.commit()

    def get_tournament_stats(self, tournament_id: int) -> Dict[str, Any]:
        """
        Compute event player statistics, determine the Tournament MVP (best player
        from the 2 Grand Finalist teams), and top 10 EVPs among playoff participants.
        """
        tournament = self.db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")

        # Get all matches in tournament
        match_ids = [m.id for m in tournament.matches]
        if not match_ids:
            return {
                "tournament_id": tournament.id,
                "tournament_name": tournament.name,
                "is_completed": tournament.status == TournamentStatus.COMPLETED.value,
                "mvp": None,
                "evps": [],
                "player_stats": [],
            }

        # Query all PlayerMatchStats for this tournament
        stats_rows = (
            self.db.query(models.PlayerMatchStat)
            .filter(models.PlayerMatchStat.match_id.in_(match_ids))
            .all()
        )

        # Identify playoff teams (Quarterfinals, Semifinals, Grand Final)
        playoff_team_ids = set()
        for m in tournament.matches:
            if m.stage in [MatchStage.QUARTER_FINAL.value, MatchStage.SEMI_FINAL.value, MatchStage.GRAND_FINAL.value]:
                if m.team1_id:
                    playoff_team_ids.add(m.team1_id)
                if m.team2_id:
                    playoff_team_ids.add(m.team2_id)

        # Identify Grand Finalist teams
        gf_match = next((m for m in tournament.matches if m.stage == MatchStage.GRAND_FINAL.value), None)
        finalist_team_ids = set()
        if gf_match:
            if gf_match.team1_id:
                finalist_team_ids.add(gf_match.team1_id)
            if gf_match.team2_id:
                finalist_team_ids.add(gf_match.team2_id)
        elif tournament.champion_id:
            finalist_team_ids.add(tournament.champion_id)

        # Participant placements map
        placements_map = {p.team_id: p.placement for p in tournament.participants}

        # Group by player_id
        player_map: Dict[int, Dict[str, Any]] = {}
        for s in stats_rows:
            pid = s.player_id
            if pid not in player_map:
                player_map[pid] = {
                    "player_id": pid,
                    "player_name": s.player.player if s.player else "Unknown",
                    "team_id": s.team_id,
                    "team_name": s.team.name if s.team else "Unknown",
                    "role": s.player.selected_role or s.player.role if s.player else None,
                    "maps_played": 0,
                    "kills": 0,
                    "deaths": 0,
                    "assists": 0,
                    "adr_sum": 0.0,
                    "rating_sum": 0.0,
                    "reached_playoffs": s.team_id in playoff_team_ids,
                    "placement": placements_map.get(s.team_id, "Group Stage"),
                    "is_finalist": s.team_id in finalist_team_ids,
                }
            entry = player_map[pid]
            entry["maps_played"] += 1
            entry["kills"] += s.kills
            entry["deaths"] += s.deaths
            entry["assists"] += s.assists
            entry["adr_sum"] += s.adr
            entry["rating_sum"] += s.rating

        player_stats_list = []
        for p in player_map.values():
            mp = max(1, p["maps_played"])
            k = p["kills"]
            d = p["deaths"]
            kd_diff = k - d
            kd_ratio = round(k / max(1, d), 2)
            avg_adr = round(p["adr_sum"] / mp, 1)
            avg_rating = round(p["rating_sum"] / mp, 2)

            player_stats_list.append({
                "player_id": p["player_id"],
                "player_name": p["player_name"],
                "team_id": p["team_id"],
                "team_name": p["team_name"],
                "role": p["role"],
                "maps_played": p["maps_played"],
                "kills": k,
                "deaths": d,
                "assists": p["assists"],
                "kd_diff": kd_diff,
                "kd_ratio": kd_ratio,
                "adr": avg_adr,
                "rating": avg_rating,
                "reached_playoffs": p["reached_playoffs"],
                "placement": p["placement"],
                "is_finalist": p["is_finalist"],
                "award": None,
            })

        # Sort all players by average rating desc, then kd_diff desc
        player_stats_list.sort(key=lambda x: (x["rating"], x["kd_diff"]), reverse=True)

        # Determine MVP:
        # Best player out of the 2 Grand Finalist teams left!
        mvp = None
        finalist_players = [p for p in player_stats_list if p["is_finalist"]]
        if finalist_players:
            if tournament.champion_id:
                champ_players = [p for p in finalist_players if p["team_id"] == tournament.champion_id]
                runner_players = [p for p in finalist_players if p["team_id"] != tournament.champion_id]
                best_champ = max(champ_players, key=lambda x: (x["rating"], x["kd_diff"])) if champ_players else None
                best_runner = max(runner_players, key=lambda x: (x["rating"], x["kd_diff"])) if runner_players else None
                if best_champ and best_runner:
                    # Runner-up only takes MVP if visibly superior (+0.08 rating)
                    if best_runner["rating"] > best_champ["rating"] + 0.08:
                        mvp = best_runner
                    else:
                        mvp = best_champ
                else:
                    mvp = best_champ or best_runner
            else:
                mvp = max(finalist_players, key=lambda x: (x["rating"], x["kd_diff"]))
        elif any(p["reached_playoffs"] for p in player_stats_list):
            mvp = max([p for p in player_stats_list if p["reached_playoffs"]], key=lambda x: (x["rating"], x["kd_diff"]))
        elif player_stats_list:
            mvp = player_stats_list[0]

        if mvp:
            mvp["award"] = "MVP"

        # Determine EVPs:
        # Constrained to players who made it to playoffs (quarters, semis, finals) and could have been in contention for MVP
        evp_candidates = [
            p for p in player_stats_list
            if p["reached_playoffs"] and (mvp is None or p["player_id"] != mvp["player_id"])
        ]
        evp_candidates.sort(key=lambda x: (x["rating"], x["kd_diff"]), reverse=True)

        evps = evp_candidates[:10]
        for idx, evp in enumerate(evps, 1):
            evp["award"] = f"EVP #{idx}"

        is_completed = (tournament.status == TournamentStatus.COMPLETED.value)

        return {
            "tournament_id": tournament.id,
            "tournament_name": tournament.name,
            "is_completed": is_completed,
            "mvp": mvp,
            "evps": evps,
            "player_stats": player_stats_list,
        }

    def advance_calendar(self) -> models.CalendarState:
        """Advance calendar to the next month/tournament in the competitive year."""
        state = self.get_or_create_calendar_state()

        # Mark current active tournament as completed if not already
        if state.active_tournament and state.active_tournament.status != TournamentStatus.COMPLETED.value:
            # Fast-forward remaining matches if user chooses to advance calendar
            pending = (
                self.db.query(models.Match)
                .filter(
                    models.Match.tournament_id == state.active_tournament.id,
                    models.Match.status == MatchStatus.SCHEDULED.value,
                )
                .all()
            )
            for m in pending:
                self.play_match(m.id)

        # Advance month
        next_month = state.current_month + 1
        next_year = state.current_year
        if next_month > 12:
            next_month = 1
            next_year += 1

        state.current_month = next_month
        state.current_year = next_year

        # Ensure tournaments for next year if rolled over
        self.ensure_circuit_tournaments(next_year)

        # Activate next tournament
        next_t = self.get_tournament_for_month(next_year, next_month)
        if next_t:
            state.active_tournament_id = next_t.id
            if next_t.status == TournamentStatus.UPCOMING.value:
                next_t.status = TournamentStatus.ACTIVE.value
                self.initialize_tournament(next_t.id)

        self.db.commit()
        self.db.refresh(state)
        return state
