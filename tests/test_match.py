from sqlalchemy.org import joinedload
from app.database import SessionLocal
from app.models import Team, Player, Match, Round, PlayerStats
from ortools.sat.python import cp_model


MAX_KILLS = 109 #best case scenario for a player in a whole match ie scoreline is 13-11, 
#5 kills in every round won ie 13 and 
# 4 kills for every round lost ie 11 in a best case win scenario
MIN_KILLS = 0

model = cp_model.CpModel()

#we have to essentially skew this to a more realistic distribution of kills per round, as the average player will not get 5 kills in every round won and 4 kills in every round lost.
#so team wise we kinda do this
#divide max kills by 5, skew according to player ratings of a team
#so lets say donk rated 94 gets more kills skewed to him ,
#cause he's a better player than the other 4 players on his team,
#so he gets more kills than the other 4 players on his team, 
#and the other 4 players get less kills than him, but still some kills, 
#so we can skew the distribution of kills per round according to player ratings of a team.

#one more thing is that we need to make sure,
#one teams max kills equal the other teams max deaths and vice versa


def simulate_match(Team1: Team, Team2: Team) -> Round:
    """
    Simulates a match between two teams and returns end match scoreline and stats
    """
    db = SessionLocal()
    try:
        
        # Create a new round
        new_round = Round(team1_id=Team1.id, team2_id=Team2.id)
        
        # Simulate player stats for each player in both teams
        # for player in Team1.players + Team2.players:
        #     player_stats = PlayerStats(
        #         round_id=new_round.id,
        #         player_id=player.id,
        #         kills=simulate_kills(player),
        #         deaths=simulate_deaths(),
        #         assists=simulate_assists(),
        #     )
        team1_avg_rating = sum(player.rating for player in Team1.players) / len(Team1.players)
        team2_avg_rating = sum(player.rating for player in Team2.players) / len(Team2.players)

        ratio = team1_avg_rating / team2_avg_rating
        team1_odds = ratio / (ratio + 1)
        team2_odds = 1 - team1_odds

        print(f"Team 1 Odds: {team1_odds:.2f}, Team 2 Odds: {team2_odds:.2f}")
            

    except Exception as e:
        db.rollback()
        print(f"Error simulating round: {e}")
        return None
    finally:
        db.close()

Team1 = db.query(Team).options(joinedload(Team.players)).filter(Team.name == "Spirit").first()
Team2 = db.query(Team).options(joinedload(Team.players)).filter(Team.name == "Vitality").first()

simulate_match(Team1, Team2)