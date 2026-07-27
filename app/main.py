from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import players, teams, games, negotiations, roster
from app.database import engine, Base
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

app.include_router(players.router)
app.include_router(teams.router)
app.include_router(games.router)
app.include_router(negotiations.router)
app.include_router(roster.router)

@app.get("/")
def root():
    return {"message": "CS Manager API — visit /docs for Swagger UI"}