import random
import math
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app import models
from app.domain.enums import MatchFormats, MatchStatus

CS_MAP_POOL = ["Mirage", "Inferno", "Nuke", "Dust II", "Anubis", "Ancient", "Train"]


class MatchEngine:
    """
    Simulates CS2 matches (Bo1, Bo3, Bo5) with realistic MR12 scorelines,
    overtime handling, and stat-driven player frag distributions.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_active_roster(self, team: models.Team) -> List[models.Player]:
        """Return the 5 active players of a team, falling back to top rated players."""
        players = list(team.players) if team.players else []
        active = [p for p in players if p.is_active_roster]
        if len(active) == 5:
            return active

        # If not exactly 5 active, pick top 5 by overall_rating / Rating
        def sort_key(p):
            r = p.overall_rating or (p.Rating / 70.0 if p.Rating else 1.0)
            return r

        sorted_players = sorted(players, key=sort_key, reverse=True)
        return sorted_players[:5]

    def compute_team_power(self, team: models.Team, roster: List[models.Player]) -> float:
        """
        Compute an aggregate team power score from player ratings, firepower,
        impact, role synergies, and team ranking.
        """
        if not roster:
            return 50.0

        ratings = []
        firepowers = []
        impacts = []
        has_igl = False
        has_awper = False

        for p in roster:
            r = p.overall_rating or (p.Rating / 70.0 if p.Rating else 1.0)
            ratings.append(r)
            firepowers.append(p.firepower if p.firepower is not None else 50.0)
            imp = p.impact if p.impact is not None else 1.0
            if imp > 10.0:
                imp = imp / 50.0
            impacts.append(imp)

            role = (p.selected_role or p.role or "").lower()
            if p.is_igl or "igl" in role:
                has_igl = True
            if "awp" in role:
                has_awper = True

        avg_rating = sum(ratings) / len(ratings)
        avg_fp = sum(firepowers) / len(firepowers)
        avg_imp = sum(impacts) / len(impacts)

        # Baseline power centered around 100
        power = (avg_rating * 70.0) + (avg_fp * 0.2) + (avg_imp * 15.0)

        # Synergy bonuses
        if has_igl:
            power += 3.5  # Tactical cohesion
        if has_awper:
            power += 2.5  # Dedicated AWP presence

        # Team rank bonus (Rank 1 gets ~5 pts bonus, rank 20 gets ~0)
        rank = team.ranking if team.ranking else 25
        rank_bonus = max(0.0, (25 - min(rank, 25)) * 0.25)
        power += rank_bonus

        return power

    def simulate_map_score(self, power1: float, power2: float) -> Tuple[int, int, bool]:
        """
        Simulate a CS2 map score (MR12: first to 13 regulation, OT if 12-12).
        Returns (rounds_team1, rounds_team2, overtime_occurred).
        """
        # Probability for Team 1 to win an individual round
        power_diff = power1 - power2
        # Logistic sigmoid with moderate variance
        prob_team1 = 1.0 / (1.0 + math.exp(-power_diff / 18.0))
        # Keep probability in reasonable competitive range (0.32 - 0.68)
        prob_team1 = max(0.32, min(0.68, prob_team1))

        t1_rounds = 0
        t2_rounds = 0

        # Regulation (up to 24 rounds, first to 13)
        while t1_rounds < 13 and t2_rounds < 13:
            if t1_rounds == 12 and t2_rounds == 12:
                break
            if random.random() < prob_team1:
                t1_rounds += 1
            else:
                t2_rounds += 1

        # Check for overtime
        if t1_rounds == 12 and t2_rounds == 12:
            overtime = True
            # Overtime: MR3 per half (sets of 6 rounds). First to lead by 2 after reaching 16+
            ot_target = 16
            while True:
                # Play OT rounds
                while (t1_rounds < ot_target and t2_rounds < ot_target) or abs(t1_rounds - t2_rounds) < 2:
                    if random.random() < prob_team1:
                        t1_rounds += 1
                    else:
                        t2_rounds += 1

                    # If both reached target - 1, increase target by 3 (next OT)
                    if t1_rounds == ot_target - 1 and t2_rounds == ot_target - 1:
                        ot_target += 3

                    # Cap extreme overtimes at 25-23
                    if t1_rounds >= 25 or t2_rounds >= 25:
                        if t1_rounds > t2_rounds:
                            t1_rounds = max(t1_rounds, t2_rounds + 2)
                        else:
                            t2_rounds = max(t2_rounds, t1_rounds + 2)
                        break

                if abs(t1_rounds - t2_rounds) >= 2 and (t1_rounds >= 16 or t2_rounds >= 16):
                    break
        else:
            overtime = False

        return t1_rounds, t2_rounds, overtime

    def distribute_frags(
        self,
        roster: List[models.Player],
        enemy_roster: List[models.Player],
        rounds_won: int,
        rounds_lost: int,
        target_kills: int | None = None,
        target_deaths: int | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Distribute kills, deaths, assists, ADR, and authentic HLTV 2.0 ratings across the 5 players.
        Higher rated players reliably top frag while maintaining realistic frag caps.
        Evenly distributes deaths across the lineup without extreme polarization,
        and accurately evaluates solid performances on both winning and losing teams.
        """
        total_rounds = rounds_won + rounds_lost

        # 1. Total team kills & deaths
        if target_kills is None:
            base_kills = rounds_won * 4.25 + rounds_lost * 1.85
            target_kills = max(5, int(round(base_kills + random.uniform(-1.5, 1.5))))

        if target_deaths is None:
            enemy_kills = rounds_lost * 4.25 + rounds_won * 1.85
            target_deaths = max(5, int(round(enemy_kills + random.uniform(-1.5, 1.5))))

        # 2. Compute frag weight for each player
        weights = []
        for p in roster:
            r = p.overall_rating or (p.Rating / 70.0 if p.Rating else 1.0)
            base_r = max(0.65, r) ** 1.25

            fp = p.firepower if p.firepower is not None else 50.0
            fp_mult = 0.85 + (fp / 100.0) * 0.28

            imp = p.impact if p.impact is not None else 1.0
            if imp > 10.0:
                imp = imp / 50.0
            imp_mult = 0.85 + max(-0.25, min(0.35, (imp - 1.0) * 0.26))

            role = (p.selected_role or p.role or "").lower()
            role_mult = 1.0
            if "awp" in role:
                role_mult = 1.10
            elif "entry" in role:
                role_mult = 1.08
            elif "lurker" in role:
                role_mult = 1.02
            elif "support" in role:
                role_mult = 0.92
            elif "igl" in role:
                role_mult = 0.90

            form = random.lognormvariate(0, 0.12)
            w = base_r * fp_mult * imp_mult * role_mult * form
            weights.append(max(0.1, w))

        total_weight = sum(weights)
        probs = [w / total_weight for w in weights]

        # 3. Sample kills using multinomial-like cumulative probabilities
        kills = [0] * len(roster)
        for _ in range(target_kills):
            rand_val = random.random()
            cum = 0.0
            for idx, p_val in enumerate(probs):
                cum += p_val
                if rand_val <= cum:
                    kills[idx] += 1
                    break
            else:
                kills[-1] += 1

        # 4. Realistic maximum & minimum frags per map constraint
        max_frags = min(target_kills - 8, int(1.15 * total_rounds + 2))
        min_frags = max(3, int(0.25 * total_rounds - 2))

        for i in range(len(kills)):
            if kills[i] > max_frags:
                excess = kills[i] - max_frags
                kills[i] = max_frags
                other_indices = [j for j in range(len(kills)) if j != i]
                while excess > 0 and other_indices:
                    chosen = random.choice(other_indices)
                    if kills[chosen] < max_frags:
                        kills[chosen] += 1
                        excess -= 1
                    else:
                        other_indices.remove(chosen)

            if kills[i] < min_frags:
                deficit = min_frags - kills[i]
                kills[i] = min_frags
                for _ in range(deficit):
                    max_idx = max(range(len(kills)), key=lambda idx: kills[idx] if idx != i else -1)
                    if kills[max_idx] > min_frags + 1:
                        kills[max_idx] -= 1

        # 5. Distribute Deaths evenly across the team
        # In CS, even entry fraggers survive 25-35%+ of rounds, and safe AWPers die in 40-50%+ of rounds.
        base_deaths = target_deaths / float(len(roster))
        min_d = max(4, int(rounds_lost * 0.50) + int(rounds_won * 0.15))
        max_d = min(total_rounds - 2, rounds_lost + int(rounds_won * 0.60) + 1)
        min_d = min(min_d, max_d - 1)

        raw_deaths = []
        for i, p in enumerate(roster):
            role = (p.selected_role or p.role or "").lower()
            role_mod = 0.0
            if "entry" in role:
                role_mod = 1.5
            elif "support" in role:
                role_mod = 0.5
            elif "lurker" in role:
                role_mod = -1.0
            elif "awp" in role:
                role_mod = -1.6

            r_val = p.overall_rating or (p.Rating / 70.0 if p.Rating else 1.0)
            rating_mod = -(r_val - 1.0) * 1.4
            noise = random.gauss(0, 0.45)

            d_val = base_deaths + role_mod + rating_mod + noise
            d_val = max(float(min_d), min(float(max_d), d_val))
            raw_deaths.append(d_val)

        # Rebalance integer deaths so sum strictly equals target_deaths
        deaths = [int(math.floor(d)) for d in raw_deaths]
        diff = target_deaths - sum(deaths)
        remainders = [(raw_deaths[i] - deaths[i], i) for i in range(len(roster))]
        remainders.sort(key=lambda x: x[0], reverse=True)

        if diff > 0:
            for _, idx in remainders:
                if diff <= 0:
                    break
                if deaths[idx] < max_d:
                    deaths[idx] += 1
                    diff -= 1
            idx = 0
            while diff > 0:
                if deaths[idx % len(roster)] < total_rounds - 1:
                    deaths[idx % len(roster)] += 1
                    diff -= 1
                idx += 1
        elif diff < 0:
            remainders.sort(key=lambda x: x[0])
            for _, idx in remainders:
                if diff >= 0:
                    break
                if deaths[idx] > min_d:
                    deaths[idx] -= 1
                    diff += 1
            idx = 0
            while diff < 0:
                if deaths[idx % len(roster)] > 1:
                    deaths[idx % len(roster)] -= 1
                    diff += 1
                idx += 1

        # 6. Compute Assists, ADR, KAST, and HLTV 2.0 Rating
        stats = []
        for i, p in enumerate(roster):
            k = kills[i]
            d = deaths[i]
            role = (p.selected_role or p.role or "").lower()

            # Assists: 2-8 typically, boosted by utility / support
            util = p.utility if p.utility is not None else 50.0
            base_a = int(round(total_rounds * 0.18 * (0.8 + (util / 100.0) * 0.4) + random.uniform(-1.0, 1.5)))
            a = max(0, min(12, base_a))

            # Realistic ADR: base chip & utility damage of ~12-16.5 dmg/round + kill & assist damage
            estimated_dmg = k * 80.0 + a * 40.0 + (total_rounds * random.uniform(12.0, 16.5))
            adr = round(max(35.0, min(140.0, estimated_dmg / max(1, total_rounds))), 1)

            # Rates
            kpr = k / max(1, total_rounds)
            dpr = d / max(1, total_rounds)
            apr = a / max(1, total_rounds)

            # KAST (% of rounds with Kill, Assist, Survived, or Traded)
            surv_rate = (total_rounds - d) / max(1, total_rounds)
            trade_bonus = 0.04 if "entry" in role else 0.02
            kast = min(98.0, max(45.0, (0.40 + 0.35 * surv_rate + 0.22 * kpr + 0.15 * apr + trade_bonus) * 100.0))

            # Impact Rating: Opening, multi-kills, clutches
            base_impact = 2.13 * kpr + 0.42 * apr - 0.41
            if "entry" in role:
                base_impact += 0.05
            elif "awp" in role:
                base_impact += 0.04
            elif "lurker" in role:
                base_impact += 0.03
            impact = max(0.30, base_impact)

            # Authentic HLTV Rating 2.0 formula
            raw_rating = (
                0.3591 * kpr -
                0.5329 * dpr +
                0.0073 * kast +
                0.0032 * adr +
                0.2372 * impact +
                0.1587
            )
            rating_2 = round(max(0.35, min(2.50, raw_rating)), 2)

            stats.append({
                "player": p,
                "kills": k,
                "deaths": d,
                "assists": a,
                "adr": adr,
                "rating": rating_2,
            })

        return stats

    def simulate_map(
        self,
        team1: models.Team,
        team2: models.Team,
        map_name: str,
        map_number: int,
    ) -> Dict[str, Any]:
        """Simulate a single map and return round scores and detailed player stats."""
        roster1 = self.get_active_roster(team1)
        roster2 = self.get_active_roster(team2)

        power1 = self.compute_team_power(team1, roster1)
        power2 = self.compute_team_power(team2, roster2)

        t1_score, t2_score, overtime = self.simulate_map_score(power1, power2)

        winner = team1 if t1_score > t2_score else team2

        # Synchronize kills and deaths between teams for total scoreboard consistency
        t1_kills = max(5, int(round(t1_score * 4.25 + t2_score * 1.85 + random.uniform(-1.5, 1.5))))
        t2_kills = max(5, int(round(t2_score * 4.25 + t1_score * 1.85 + random.uniform(-1.5, 1.5))))

        stats1 = self.distribute_frags(roster1, roster2, t1_score, t2_score, target_kills=t1_kills, target_deaths=t2_kills)
        stats2 = self.distribute_frags(roster2, roster1, t2_score, t1_score, target_kills=t2_kills, target_deaths=t1_kills)

        # Determine MVP of the map: highest rating on the winning team
        winning_stats = stats1 if winner.id == team1.id else stats2
        mvp_stat = max(winning_stats, key=lambda s: (s["rating"], s["kills"]))
        for s in winning_stats:
            s["is_mvp"] = (s == mvp_stat)
        losing_stats = stats2 if winner.id == team1.id else stats1
        for s in losing_stats:
            s["is_mvp"] = False

        return {
            "map_number": map_number,
            "map_name": map_name,
            "team1_score": t1_score,
            "team2_score": t2_score,
            "overtime": overtime,
            "winner_id": winner.id,
            "stats1": stats1,
            "stats2": stats2,
        }

    def simulate_series(self, match: models.Match) -> models.Match:
        """
        Simulate an entire best-of-X series (Bo1, Bo3, Bo5) until a team wins
        the required number of maps. Saves map results and player stats to DB.
        """
        if match.status == MatchStatus.COMPLETED:
            return match

        team1 = self.db.query(models.Team).filter(models.Team.id == match.team1_id).first()
        team2 = self.db.query(models.Team).filter(models.Team.id == match.team2_id).first()
        if not team1 or not team2:
            raise ValueError(f"Match {match.id} has invalid teams: {match.team1_id}, {match.team2_id}")

        maps_needed = MatchFormats.get_maps_to_win(match.format)

        # Pick random available maps without duplicates
        available_maps = list(CS_MAP_POOL)
        random.shuffle(available_maps)

        t1_maps = 0
        t2_maps = 0
        map_num = 1

        # Clear any existing partial maps/stats for this match
        self.db.query(models.PlayerMatchStat).filter(models.PlayerMatchStat.match_id == match.id).delete()
        self.db.query(models.MapResult).filter(models.MapResult.match_id == match.id).delete()

        while t1_maps < maps_needed and t2_maps < maps_needed:
            map_name = available_maps.pop(0) if available_maps else "Mirage"
            map_data = self.simulate_map(team1, team2, map_name, map_num)

            # Persist MapResult
            db_map = models.MapResult(
                match_id=match.id,
                map_number=map_num,
                map_name=map_data["map_name"],
                team1_score=map_data["team1_score"],
                team2_score=map_data["team2_score"],
                overtime=map_data["overtime"],
                winner_id=map_data["winner_id"],
            )
            self.db.add(db_map)
            self.db.flush()

            if map_data["winner_id"] == team1.id:
                t1_maps += 1
            else:
                t2_maps += 1

            # Persist PlayerMatchStat for team 1
            for s in map_data["stats1"]:
                db_stat = models.PlayerMatchStat(
                    match_id=match.id,
                    map_result_id=db_map.id,
                    player_id=s["player"].id,
                    team_id=team1.id,
                    kills=s["kills"],
                    deaths=s["deaths"],
                    assists=s["assists"],
                    adr=s["adr"],
                    rating=s["rating"],
                    is_mvp=s.get("is_mvp", False),
                )
                self.db.add(db_stat)

            # Persist PlayerMatchStat for team 2
            for s in map_data["stats2"]:
                db_stat = models.PlayerMatchStat(
                    match_id=match.id,
                    map_result_id=db_map.id,
                    player_id=s["player"].id,
                    team_id=team2.id,
                    kills=s["kills"],
                    deaths=s["deaths"],
                    assists=s["assists"],
                    adr=s["adr"],
                    rating=s["rating"],
                    is_mvp=s.get("is_mvp", False),
                )
                self.db.add(db_stat)

            map_num += 1

        # Conclude Match
        match.team1_score = t1_maps
        match.team2_score = t2_maps
        match.winner_id = team1.id if t1_maps > t2_maps else team2.id
        match.status = MatchStatus.COMPLETED

        self.db.commit()
        self.db.refresh(match)
        return match
