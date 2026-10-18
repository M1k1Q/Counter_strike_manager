from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models
from app.domain.enums import MatchStage, MatchStatus, TournamentStatus, TournamentTier, MatchFormats
from app.services.match_engine import MatchEngine
from app.services.transfer_service import reconcile_ai_rosters

CIRCUIT_EVENTS = [
    {"month": 1, "name": "IEM Krakow", "tier": TournamentTier.S_TIER, "prize": 1_000_000, "min_rank": 16, "format": "Bo5"},
    {"month": 2, "name": "BLAST Premier Spring Groups", "tier": TournamentTier.A_TIER, "prize": 400_000, "min_rank": 16, "format": "Bo5"},
    {"month": 3, "name": "ESL Pro League Spring", "tier": TournamentTier.S_TIER, "prize": 750_000, "min_rank": 16, "format": "Bo5"},
    {"month": 5, "name": "PGL CS2 Major", "tier": TournamentTier.MAJOR, "prize": 1_250_000, "min_rank": 16, "format": "Bo5"},
    {"month": 6, "name": "BLAST Premier Spring Final", "tier": TournamentTier.S_TIER, "prize": 500_000, "min_rank": 16, "format": "Bo5"},
    {"month": 7, "name": "IEM Cologne", "tier": TournamentTier.S_TIER, "prize": 1_000_000, "min_rank": 16, "format": "Bo5"},
    {"month": 8, "name": "Roobet Cup Global", "tier": TournamentTier.A_TIER, "prize": 350_000, "min_rank": 16, "format": "Bo5"},
    {"month": 9, "name": "ESL Pro League Autumn", "tier": TournamentTier.S_TIER, "prize": 750_000, "min_rank": 16, "format": "Bo5"},
    {"month": 10, "name": "Thunderpick World Championship", "tier": TournamentTier.A_TIER, "prize": 600_000, "min_rank": 16, "format": "Bo5"},
    {"month": 11, "name": "Perfect World Winter Major", "tier": TournamentTier.MAJOR, "prize": 1_250_000, "min_rank": 16, "format": "Bo5"},
    {"month": 12, "name": "BLAST Premier World Final", "tier": TournamentTier.S_TIER, "prize": 1_000_000, "min_rank": 16, "format": "Bo5"},
]

LOWER_TIER_EVENTS = [
    {"month": 1, "name": "CCT Season 2 Series", "tier": TournamentTier.B_TIER, "prize": 100_000, "min_rank": 40, "format": "Bo3"},
    {"month": 2, "name": "ESL Challenger Katowice", "tier": TournamentTier.B_TIER, "prize": 120_000, "min_rank": 40, "format": "Bo3"},
    {"month": 3, "name": "DraculaN Invitational", "tier": TournamentTier.C_TIER, "prize": 75_000, "min_rank": 50, "format": "Bo3"},
    {"month": 4, "name": "Stake Ranked Open Spring", "tier": TournamentTier.C_TIER, "prize": 60_000, "min_rank": 60, "format": "Bo3"},
    {"month": 5, "name": "CCT Regional Cup", "tier": TournamentTier.B_TIER, "prize": 100_000, "min_rank": 40, "format": "Bo3"},
    {"month": 6, "name": "ESL Challenger Jönköping", "tier": TournamentTier.B_TIER, "prize": 120_000, "min_rank": 40, "format": "Bo3"},
    {"month": 7, "name": "DraculaN Summer Clash", "tier": TournamentTier.C_TIER, "prize": 75_000, "min_rank": 50, "format": "Bo3"},
    {"month": 8, "name": "Stake Ranked Masters", "tier": TournamentTier.C_TIER, "prize": 60_000, "min_rank": 60, "format": "Bo3"},
    {"month": 9, "name": "CCT Global Finals Qualifier", "tier": TournamentTier.B_TIER, "prize": 100_000, "min_rank": 40, "format": "Bo3"},
    {"month": 10, "name": "ESL Challenger Atlanta", "tier": TournamentTier.B_TIER, "prize": 120_000, "min_rank": 40, "format": "Bo3"},
    {"month": 11, "name": "DraculaN Winter Showdown", "tier": TournamentTier.C_TIER, "prize": 75_000, "min_rank": 50, "format": "Bo3"},
    {"month": 12, "name": "Stake Ranked Championship", "tier": TournamentTier.C_TIER, "prize": 80_000, "min_rank": 60, "format": "Bo3"},
]

ALL_SCHEDULED_EVENTS = CIRCUIT_EVENTS + LOWER_TIER_EVENTS


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
                tournament_start_pending=True,
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
                state.tournament_start_pending = True
                self.db.commit()
                self.db.refresh(state)

        return state

    def ensure_circuit_tournaments(self, year: int) -> List[models.Tournament]:
        """Ensure all events for the season year exist in the database."""
        existing = self.db.query(models.Tournament).filter(models.Tournament.year == year).all()
        existing_names = {t.name for t in existing}

        total_teams = self.db.query(models.Team).count()
        events_to_schedule = ALL_SCHEDULED_EVENTS if total_teams >= 32 else CIRCUIT_EVENTS

        created = []
        for event in events_to_schedule:
            if event["name"] not in existing_names:
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

        if created:
            self.db.commit()
        return self.db.query(models.Tournament).filter(models.Tournament.year == year).order_by(models.Tournament.month.asc(), models.Tournament.prize_pool.desc()).all()

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
        Seed 16 teams into four groups of four and generate round-robin matches.
        Each group's top two teams advance to the quarter-finals.
        Teams cannot participate in more than one tournament in the same month!
        """
        tournament = self.db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
        if not tournament:
            raise ValueError(f"Tournament {tournament_id} not found")

        # If already has participants, return
        if tournament.participants:
            return tournament

        # Find all teams already participating in other tournaments in the exact same year and month
        other_concurrent_tournaments = (
            self.db.query(models.Tournament)
            .filter(
                models.Tournament.year == tournament.year,
                models.Tournament.month == tournament.month,
                models.Tournament.id != tournament.id,
            )
            .all()
        )
        busy_team_ids = set()
        for other_t in other_concurrent_tournaments:
            for part in other_t.participants:
                busy_team_ids.add(part.team_id)

        # Teams need a complete roster before they can take an event slot.
        roster_counts = dict(
            self.db.query(models.Player.team_id, func.count(models.Player.id))
            .filter(models.Player.team_id.isnot(None))
            .group_by(models.Player.team_id)
            .all()
        )
        all_teams = self.db.query(models.Team).order_by(models.Team.ranking.asc()).all()
        eligible_teams = [
            team for team in all_teams
            if roster_counts.get(team.id, 0) >= 5
        ]

        manager = self.db.query(models.Manager).first()
        user_team = manager.team if (manager and manager.team) else None
        eligible_team_ids = {team.id for team in eligible_teams}

        cutoff = tournament.min_rank_required or 16
        is_lower_tier = tournament.tier in [TournamentTier.B_TIER.value, TournamentTier.C_TIER.value]

        # Determine 16 invited teams:
        invited_teams = []
        user_included = False

        # Check if user team qualifies and is not already busy in another concurrent event
        if user_team and user_team.id in eligible_team_ids and user_team.id not in busy_team_ids:
            if not is_lower_tier:
                # Top-tier event: user qualifies if rank <= cutoff
                if user_team.ranking and user_team.ranking <= cutoff:
                    invited_teams.append(user_team)
                    user_included = True
            else:
                # Lower-tier event: user qualifies if within ranking range (e.g. > 16 and <= cutoff, or if cutoff allows)
                if user_team.ranking and user_team.ranking <= cutoff:
                    invited_teams.append(user_team)
                    user_included = True

        for t in eligible_teams:
            if len(invited_teams) >= 16:
                break
            if t.id in busy_team_ids:
                continue
            if user_included and t.id == user_team.id:
                continue
            invited_teams.append(t)

        if len(invited_teams) < 16:
            if is_lower_tier:
                # In small database setups (like tests with only 16 teams), skip/mark completed if not enough teams
                tournament.status = TournamentStatus.COMPLETED.value
                self.db.commit()
                return tournament
            raise ValueError(f"Not enough available teams to populate tournament {tournament.name} (requires 16, found {len(invited_teams)})")

        # Sort invited teams by ranking to assign Seeds 1..16
        invited_teams.sort(key=lambda t: t.ranking if t.ranking else 999)

        # Snake seed the four groups so the strongest seeds are distributed evenly.
        group_names = ["A", "B", "C", "D"]
        group_by_seed = ["A", "B", "C", "D", "D", "C", "B", "A"]

        participants = []
        for seed_idx, team in enumerate(invited_teams, 1):
            grp = group_by_seed[(seed_idx - 1) % len(group_by_seed)]

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

        # Berger tables for four teams (3 rounds x 2 matches = 6 matches per group).
        round_pairings = [
            [(0, 3), (1, 2)],  # Round 1
            [(3, 2), (0, 1)],  # Round 2
            [(1, 3), (2, 0)],  # Round 3
        ]

        for grp_name in group_names:
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

        if match.tournament_id:
            tournament = self.db.query(models.Tournament).filter(
                models.Tournament.id == match.tournament_id
            ).first()
            if tournament and tournament.status == TournamentStatus.COMPLETED.value:
                raise ValueError(f"Tournament {tournament.id} is already completed")

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
            raise ValueError(f"Tournament {tournament_id} not found")
        if tournament.status == TournamentStatus.COMPLETED.value:
            raise ValueError(f"Tournament {tournament_id} is already completed")

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
        1. Group Stage (24 matches) -> Create Quarter-Finals (4 matches, Bo3)
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
        """Advance each group's top two and pair adjacent groups in quarter-finals."""
        participants = tournament.participants

        # Sort by: wins DESC, round differential DESC, seed ASC
        def sort_group(p: models.TournamentParticipant):
            round_diff = p.rounds_won - p.rounds_lost
            return (p.wins, round_diff, -p.seed)

        groups = {
            group_name: sorted(
                (p for p in participants if p.group_name == group_name),
                key=sort_group,
                reverse=True,
            )
            for group_name in ["A", "B", "C", "D"]
        }
        if any(len(group) < 4 for group in groups.values()):
            return

        for group in groups.values():
            for participant in group[:2]:
                participant.placement = "Quarterfinalist"
            for participant in group[2:]:
                participant.eliminated = True
                participant.placement = "Group Stage"

        pairings = [
            ("A", 0, "B", 1),
            ("B", 0, "A", 1),
            ("C", 0, "D", 1),
            ("D", 0, "C", 1),
        ]
        quarterfinals = [
            models.Match(
                tournament_id=tournament.id,
                stage=MatchStage.QUARTER_FINAL.value,
                round_name=(
                    f"Quarter-Final {idx} "
                    f"({group1}{place1 + 1} vs {group2}{place2 + 1})"
                ),
                team1_id=groups[group1][place1].team_id,
                team2_id=groups[group2][place2].team_id,
                format="Bo3",
                status=MatchStatus.SCHEDULED.value,
            )
            for idx, (group1, place1, group2, place2) in enumerate(pairings, 1)
        ]
        self.db.add_all(quarterfinals)
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

        # Determine ranking points and career points multiplier based on tournament tier
        tier = tournament.tier
        if tier in [TournamentTier.MAJOR.value, TournamentTier.S_TIER.value]:
            pts_champ, pts_runner, pts_semi, pts_qf, pts_group = 1000, 600, 350, 175, 50
        elif tier == TournamentTier.A_TIER.value:
            pts_champ, pts_runner, pts_semi, pts_qf, pts_group = 600, 360, 200, 100, 30
        elif tier == TournamentTier.B_TIER.value:
            pts_champ, pts_runner, pts_semi, pts_qf, pts_group = 150, 90, 50, 25, 10
        else: # C_TIER or other lower tier
            pts_champ, pts_runner, pts_semi, pts_qf, pts_group = 100, 60, 35, 15, 5

        # Check if manager's team won prize money & career points
        manager = self.db.query(models.Manager).first()
        if manager and manager.team_id:
            m_team_id = manager.team_id
            if m_team_id == champion_id:
                manager.budget += int(prize_total * 0.50)
                manager.career_points += pts_champ
            elif m_team_id == runner_up_id:
                manager.budget += int(prize_total * 0.25)
                manager.career_points += pts_runner
            elif any(p.team_id == m_team_id and p.placement == "Semifinals" for p in tournament.participants):
                manager.budget += int(prize_total * 0.10)
                manager.career_points += pts_semi
            elif any(p.team_id == m_team_id and p.placement == "Quarterfinalist" for p in tournament.participants):
                manager.budget += int(prize_total * 0.025)
                manager.career_points += pts_qf
            elif any(p.team_id == m_team_id for p in tournament.participants):
                manager.budget += int(prize_total * 0.005)
                manager.career_points += pts_group

        # Award ranking points to participating teams
        for p in tournament.participants:
            team = p.team
            if not team:
                continue
            curr_pts = team.ranking_points or 0
            if p.placement == "Champion":
                team.ranking_points = curr_pts + pts_champ
            elif p.placement == "Runner-Up":
                team.ranking_points = curr_pts + pts_runner
            elif p.placement == "Semifinals":
                team.ranking_points = curr_pts + pts_semi
            elif p.placement == "Quarterfinalist":
                team.ranking_points = curr_pts + pts_qf
            else:
                team.ranking_points = curr_pts + pts_group

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

        archived_rows = (
            self.db.query(models.TournamentPlayerStatArchive)
            .filter(models.TournamentPlayerStatArchive.tournament_id == tournament_id)
            .order_by(
                models.TournamentPlayerStatArchive.rating.desc(),
                models.TournamentPlayerStatArchive.kd_diff.desc(),
            )
            .all()
        )
        if archived_rows:
            player_stats = [
                {
                    "player_id": row.player_id,
                    "player_name": row.player_name,
                    "team_id": row.team_id,
                    "team_name": row.team_name,
                    "role": row.role,
                    "maps_played": row.maps_played,
                    "kills": row.kills,
                    "deaths": row.deaths,
                    "assists": row.assists,
                    "kd_diff": row.kd_diff,
                    "kd_ratio": row.kd_ratio,
                    "adr": row.adr,
                    "rating": row.rating,
                    "reached_playoffs": row.reached_playoffs,
                    "placement": row.placement,
                    "is_finalist": row.is_finalist,
                    "award": row.award,
                }
                for row in archived_rows
            ]
            archived_evps = [
                player for player in player_stats
                if player["award"] and player["award"].startswith("EVP #")
            ]
            archived_evps.sort(key=lambda player: int(player["award"].split("#", 1)[1]))
            return {
                "tournament_id": tournament.id,
                "tournament_name": tournament.name,
                "is_completed": tournament.status == TournamentStatus.COMPLETED.value,
                "mvp": next((player for player in player_stats if player["award"] == "MVP"), None),
                "evps": archived_evps,
                "player_stats": player_stats,
            }

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

        # Determine MVP from the finalists, except Majors where only the champion
        # can produce the event MVP.
        mvp = None
        finalist_players = [p for p in player_stats_list if p["is_finalist"]]
        if tournament.tier == TournamentTier.MAJOR.value:
            champion_players = [
                p for p in player_stats_list
                if tournament.champion_id and p["team_id"] == tournament.champion_id
            ]
            if champion_players:
                mvp = max(champion_players, key=lambda x: (x["rating"], x["kd_diff"]))
        elif finalist_players:
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
            if p["reached_playoffs"]
            and p["rating"] >= 1.15
            and (mvp is None or p["player_id"] != mvp["player_id"])
        ]

        if tournament.tier == TournamentTier.MAJOR.value:
            placement_bonus = {
                "champion": 0.36,
                "runner-up": 0.24,
                "semifinalist": 0.12,
                "semifinals": 0.12,
                "quarterfinalist": 0.0,
            }

            def major_evp_score(player: Dict[str, Any]) -> tuple[float, float, int]:
                placement = (player["placement"] or "").lower()
                return (
                    player["rating"] + placement_bonus.get(placement, 0.0),
                    player["rating"],
                    player["kd_diff"],
                )

            evp_candidates.sort(key=major_evp_score, reverse=True)
        else:
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

    def get_year_end_top_20(self) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(models.YearEndPlayerArchive)
            .order_by(models.YearEndPlayerArchive.year.desc(), models.YearEndPlayerArchive.rank.asc())
            .all()
        )
        seasons: Dict[int, List[Dict[str, Any]]] = {}
        player_seasons: Dict[tuple[int, int], Dict[str, Any]] = {}
        for row in rows:
            player = {
                "rank": row.rank,
                "player_id": row.player_id,
                "player_name": row.player_name,
                "team_name": row.team_name,
                "role": row.role,
                "maps_played": row.maps_played,
                "kills": row.kills,
                "deaths": row.deaths,
                "assists": row.assists,
                "kd_diff": row.kd_diff,
                "kd_ratio": row.kd_ratio,
                "adr": row.adr,
                "rating": row.rating,
                "mvp_count": row.mvp_count,
                "evp_count": row.evp_count,
                "honors": [],
            }
            seasons.setdefault(row.year, []).append(player)
            player_seasons[(row.year, row.player_id)] = player

        if player_seasons:
            years = {year for year, _ in player_seasons}
            player_ids = {player_id for _, player_id in player_seasons}
            honor_rows = (
                self.db.query(models.TournamentPlayerStatArchive, models.Tournament)
                .join(
                    models.Tournament,
                    models.Tournament.id == models.TournamentPlayerStatArchive.tournament_id,
                )
                .filter(
                    models.Tournament.year.in_(years),
                    models.TournamentPlayerStatArchive.player_id.in_(player_ids),
                    models.TournamentPlayerStatArchive.award.isnot(None),
                )
                .order_by(models.Tournament.year.desc(), models.Tournament.month.asc())
                .all()
            )
            for stat, tournament in honor_rows:
                player = player_seasons.get((tournament.year, stat.player_id))
                if player:
                    player["honors"].append({
                        "event_name": tournament.name,
                        "month": tournament.month,
                        "award": stat.award,
                        "event_rating": stat.rating,
                        "placement": stat.placement,
                    })
        return [{"year": year, "players": players} for year, players in seasons.items()]

    def archive_year_end_stats(self, year: int) -> None:
        tournaments = (
            self.db.query(models.Tournament)
            .filter(
                models.Tournament.year == year,
                models.Tournament.status == TournamentStatus.COMPLETED.value,
            )
            .order_by(models.Tournament.month.asc())
            .all()
        )
        totals: Dict[int, Dict[str, Any]] = {}
        tournament_ids = [tournament.id for tournament in tournaments]

        for tournament in tournaments:
            event_stats = self.get_tournament_stats(tournament.id)
            archived_rows = (
                self.db.query(models.TournamentPlayerStatArchive)
                .filter(models.TournamentPlayerStatArchive.tournament_id == tournament.id)
                .all()
            )
            if not archived_rows:
                for player in event_stats["player_stats"]:
                    self.db.add(models.TournamentPlayerStatArchive(
                        tournament_id=tournament.id,
                        player_id=player["player_id"],
                        player_name=player["player_name"],
                        team_id=player["team_id"],
                        team_name=player["team_name"],
                        role=player["role"],
                        maps_played=player["maps_played"],
                        kills=player["kills"],
                        deaths=player["deaths"],
                        assists=player["assists"],
                        kd_diff=player["kd_diff"],
                        kd_ratio=player["kd_ratio"],
                        adr=player["adr"],
                        rating=player["rating"],
                        reached_playoffs=player["reached_playoffs"],
                        is_finalist=player["is_finalist"],
                        placement=player["placement"],
                        award=player["award"],
                    ))

            for player in event_stats["player_stats"]:
                total = totals.setdefault(player["player_id"], {
                    "player_id": player["player_id"],
                    "player_name": player["player_name"],
                    "team_name": player["team_name"],
                    "role": player["role"],
                    "maps_played": 0,
                    "kills": 0,
                    "deaths": 0,
                    "assists": 0,
                    "rating_sum": 0.0,
                    "adr_sum": 0.0,
                    "mvp_count": 0,
                    "evp_count": 0,
                })
                maps_played = player["maps_played"]
                total["player_name"] = player["player_name"]
                total["team_name"] = player["team_name"]
                total["role"] = player["role"]
                total["maps_played"] += maps_played
                total["kills"] += player["kills"]
                total["deaths"] += player["deaths"]
                total["assists"] += player["assists"]
                total["rating_sum"] += player["rating"] * maps_played
                total["adr_sum"] += player["adr"] * maps_played
                total["mvp_count"] += player["award"] == "MVP"
                total["evp_count"] += bool(player["award"] and player["award"].startswith("EVP #"))

        ranked_players = []
        for player in totals.values():
            maps_played = player["maps_played"]
            player["rating"] = round(player["rating_sum"] / maps_played, 2)
            player["adr"] = round(player["adr_sum"] / maps_played, 1)
            player["kd_diff"] = player["kills"] - player["deaths"]
            player["kd_ratio"] = round(player["kills"] / max(1, player["deaths"]), 2)
            ranked_players.append(player)
        ranked_players.sort(
            key=lambda player: (
                player["rating"],
                player["mvp_count"],
                player["evp_count"],
                player["maps_played"],
                player["kd_diff"],
            ),
            reverse=True,
        )

        self.db.query(models.YearEndPlayerArchive).filter(
            models.YearEndPlayerArchive.year == year
        ).delete(synchronize_session=False)
        for rank, player in enumerate(ranked_players[:20], 1):
            self.db.add(models.YearEndPlayerArchive(
                year=year,
                rank=rank,
                player_id=player["player_id"],
                player_name=player["player_name"],
                team_name=player["team_name"],
                role=player["role"],
                maps_played=player["maps_played"],
                kills=player["kills"],
                deaths=player["deaths"],
                assists=player["assists"],
                kd_diff=player["kd_diff"],
                kd_ratio=player["kd_ratio"],
                adr=player["adr"],
                rating=player["rating"],
                mvp_count=player["mvp_count"],
                evp_count=player["evp_count"],
            ))

        if tournament_ids:
            match_ids = self.db.query(models.Match.id).filter(
                models.Match.tournament_id.in_(tournament_ids)
            )
            self.db.query(models.PlayerMatchStat).filter(
                models.PlayerMatchStat.match_id.in_(match_ids)
            ).delete(synchronize_session=False)

    def start_current_month_tournaments(self) -> models.CalendarState:
        state = self.get_or_create_calendar_state()
        if not state.tournament_start_pending:
            raise ValueError("The current month's tournament has already started")

        # Use the open inter-event window to repair AI rosters before qualifying teams.
        reconcile_ai_rosters(self.db)

        scheduled_event_count = (
            self.db.query(models.Tournament.id)
            .filter(
                models.Tournament.year == state.current_year,
                models.Tournament.month == state.current_month,
                models.Tournament.status != TournamentStatus.COMPLETED.value,
            )
            .count()
        )
        if not scheduled_event_count and state.active_tournament:
            state.current_year = state.active_tournament.year
            state.current_month = state.active_tournament.month

        tournaments = (
            self.db.query(models.Tournament)
            .filter(
                models.Tournament.year == state.current_year,
                models.Tournament.month == state.current_month,
                models.Tournament.status != TournamentStatus.COMPLETED.value,
            )
            .order_by(models.Tournament.prize_pool.desc())
            .all()
        )
        if not tournaments:
            raise ValueError("There is no tournament scheduled for the current month")

        total_teams = self.db.query(models.Team).count()
        for tournament in tournaments:
            if (
                tournament.tier in [TournamentTier.B_TIER.value, TournamentTier.C_TIER.value]
                and total_teams < 32
            ):
                continue
            if not tournament.participants:
                try:
                    self.initialize_tournament(tournament.id)
                except ValueError:
                    continue

        manager = self.db.query(models.Manager).first()
        manager_team_id = manager.team_id if manager else None
        chosen = next(
            (
                tournament for tournament in tournaments
                if manager_team_id
                and any(participant.team_id == manager_team_id for participant in tournament.participants)
            ),
            None,
        )
        if not chosen:
            chosen = next((tournament for tournament in tournaments if tournament.participants), None)
        if not chosen:
            raise ValueError("No tournament could be started with the available teams")

        state.active_tournament_id = chosen.id
        state.tournament_start_pending = False
        self.db.commit()
        self.db.refresh(state)
        return state

    def advance_calendar(self) -> models.CalendarState:
        """Advance calendar to the next month in the competitive year, simulating all concurrent tournaments."""
        state = self.get_or_create_calendar_state()
        if state.tournament_start_pending:
            raise ValueError("Start the current month's tournament before advancing to the next month")

        # Find ALL tournaments for the current month and year that are not yet completed
        curr_tournaments = (
            self.db.query(models.Tournament)
            .filter(
                models.Tournament.year == state.current_year,
                models.Tournament.month == state.current_month,
                models.Tournament.status != TournamentStatus.COMPLETED.value,
            )
            .order_by(models.Tournament.prize_pool.desc())
            .all()
        )

        # If state.active_tournament is among them, ensure it runs first
        if state.active_tournament and state.active_tournament in curr_tournaments:
            curr_tournaments.remove(state.active_tournament)
            curr_tournaments.insert(0, state.active_tournament)

        for tourney in curr_tournaments:
            if not tourney.participants:
                try:
                    self.initialize_tournament(tourney.id)
                except ValueError:
                    continue

            while tourney.status != TournamentStatus.COMPLETED.value:
                pending = (
                    self.db.query(models.Match)
                    .filter(
                        models.Match.tournament_id == tourney.id,
                        models.Match.status == MatchStatus.SCHEDULED.value,
                    )
                    .all()
                )
                if not pending:
                    break
                for match in pending:
                    self.play_match(match.id)

        # Advance month
        next_month = state.current_month + 1
        next_year = state.current_year
        if next_month > 12:
            next_month = 1
            next_year += 1

        if next_year > state.current_year:
            self.archive_year_end_stats(state.current_year)

        while True:
            self.ensure_circuit_tournaments(next_year)
            next_month_tournaments = (
                self.db.query(models.Tournament)
                .filter(
                    models.Tournament.year == next_year,
                    models.Tournament.month == next_month,
                )
                .order_by(models.Tournament.prize_pool.desc())
                .all()
            )
            if any(
                tournament.status != TournamentStatus.COMPLETED.value
                for tournament in next_month_tournaments
            ):
                break

            next_month += 1
            if next_month > 12:
                self.archive_year_end_stats(next_year)
                next_month = 1
                next_year += 1

        # Select the next event now, but defer initialization until the manager starts it.
        next_tournament = next(
            (
                tournament for tournament in next_month_tournaments
                if tournament.status != TournamentStatus.COMPLETED.value
            ),
            None,
        )

        state.current_month = next_month
        state.current_year = next_year
        if next_tournament:
            state.active_tournament_id = next_tournament.id
        else:
            state.active_tournament_id = None
        state.tournament_start_pending = True

        self.db.commit()
        self.db.refresh(state)
        return state
