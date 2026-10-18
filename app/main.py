from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Boolean, false, inspect, text

from app.api.routes.players import router as players_router
from app.api.routes.teams import router as teams_router
from app.api.routes.games import router as games_router
from app.api.routes.negotiations import router as negotiations_router
from app.api.routes.roster import router as roster_router
from app.api.routes.ai_buyouts import router as ai_buyouts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.tournaments import router as tournaments_router
from app.infrastructure.database import SessionLocal, engine, Base
from app.services.player_rating_service import migrate_player_ratings
from app import models
from contextlib import asynccontextmanager

Base.metadata.create_all(bind=engine)


def _ensure_calendar_tournament_start_column():
    columns = {
        column["name"]
        for column in inspect(engine).get_columns("calendar_states")
    }
    if "tournament_start_pending" in columns:
        return

    boolean_type = str(Boolean().compile(dialect=engine.dialect))
    false_value = str(false().compile(dialect=engine.dialect))
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE calendar_states "
            f"ADD COLUMN tournament_start_pending {boolean_type} "
            f"NOT NULL DEFAULT {false_value}"
        ))


_ensure_calendar_tournament_start_column()


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as db:
        migrate_player_ratings(db)
    yield


app = FastAPI(lifespan=lifespan)

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