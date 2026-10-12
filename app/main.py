from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.players import router as players_router
from app.api.routes.teams import router as teams_router
from app.api.routes.games import router as games_router
from app.api.routes.negotiations import router as negotiations_router
from app.api.routes.roster import router as roster_router
from app.api.routes.ai_buyouts import router as ai_buyouts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.tournaments import router as tournaments_router
from app.infrastructure.database import engine, Base
from app import models

Base.metadata.create_all(bind=engine)

app = FastAPI()

# Allow React dev server (Vite on port 5173) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(players_router)
app.include_router(teams_router)
app.include_router(games_router)
app.include_router(negotiations_router)
app.include_router(roster_router)
app.include_router(ai_buyouts_router)
app.include_router(tournaments_router)



@app.get("/")
def root():
    return {"message": "CS Manager API — visit /docs for Swagger UI"}