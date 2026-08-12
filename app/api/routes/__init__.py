from .players import router as players_router
from .teams import router as teams_router
from .games import router as games_router
from .negotiations import router as negotiations_router
from .roster import router as roster_router
from .ai_buyouts import router as ai_buyouts_router

players = players_router
teams = teams_router
games = games_router
negotiations = negotiations_router
roster = roster_router
ai_buyouts = ai_buyouts_router
