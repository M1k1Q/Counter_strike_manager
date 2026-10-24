from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import csv
from pathlib import Path
from sqlalchemy import Boolean, Float, Integer, false, inspect, text

from app.api.routes.players import router as players_router
from app.api.routes.teams import router as teams_router
from app.api.routes.games import router as games_router
from app.api.routes.negotiations import router as negotiations_router
from app.api.routes.roster import router as roster_router
from app.api.routes.ai_buyouts import router as ai_buyouts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.tournaments import router as tournaments_router
from app.database import SessionLocal, engine, Base
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


def _ensure_player_development_columns():
    columns = {column["name"] for column in inspect(engine).get_columns("players")}
    age_column_missing = "Age" not in columns
    column_definitions = {
        "Age": f"{Integer().compile(dialect=engine.dialect)} NOT NULL DEFAULT 20",
        "Potential": f"{Integer().compile(dialect=engine.dialect)}",
        "form": f"{Float().compile(dialect=engine.dialect)} NOT NULL DEFAULT 1.0",
        "training_form_bonus": f"{Float().compile(dialect=engine.dialect)} NOT NULL DEFAULT 0.0",
        "last_trained_year": f"{Integer().compile(dialect=engine.dialect)}",
        "last_trained_month": f"{Integer().compile(dialect=engine.dialect)}",
        "training_points_used": f"{Float().compile(dialect=engine.dialect)} NOT NULL DEFAULT 0.0",
    }
    missing_columns = {
        name: definition
        for name, definition in column_definitions.items()
        if name not in columns
    }
    if missing_columns:
        with engine.begin() as connection:
            for name, definition in missing_columns.items():
                connection.execute(text(
                    f'ALTER TABLE players ADD COLUMN "{name}" {definition}'
                ))

    if age_column_missing:
        csv_path = Path(__file__).with_name("hltv_team_player_stats_2026.csv")
        if csv_path.is_file():
            with csv_path.open(encoding="utf-8", newline="") as source:
                age_updates = []
                for row in csv.DictReader(source):
                    try:
                        age = int(row["Age"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    age_updates.append({"age": age, "player": row.get("Player", "")})
            if age_updates:
                with engine.begin() as connection:
                    connection.execute(
                        text('UPDATE players SET "Age" = :age WHERE player = :player AND "Age" = 20'),
                        age_updates,
                    )

    with engine.begin() as connection:
        connection.execute(text(
            'UPDATE players SET "Age" = 20 WHERE "Age" IS NULL'
        ))
        connection.execute(text(
            'UPDATE players SET "Potential" = COALESCE("Potential", "Rating")'
        ))
        connection.execute(text(
            'UPDATE players SET "form" = 1.0 WHERE "form" IS NULL'
        ))
        connection.execute(text(
            "UPDATE players SET training_form_bonus = 0.0 WHERE training_form_bonus IS NULL"
        ))
        connection.execute(text(
            "UPDATE players SET training_points_used = 0.0 WHERE training_points_used IS NULL"
        ))


_ensure_player_development_columns()


def _ensure_player_transfer_list_column():
    columns = {column["name"] for column in inspect(engine).get_columns("players")}
    if "is_transfer_listed" in columns:
        return

    boolean_type = str(Boolean().compile(dialect=engine.dialect))
    false_value = str(false().compile(dialect=engine.dialect))
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE players "
            f'ADD COLUMN "is_transfer_listed" {boolean_type} '
            f"NOT NULL DEFAULT {false_value}"
        ))


_ensure_player_transfer_list_column()


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