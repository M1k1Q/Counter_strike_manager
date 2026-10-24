import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
default_db_path = APP_DIR / "cs_manager.db"


def _resolve_database_url() -> str:
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        return f"sqlite:///{default_db_path}"

    if raw_url.startswith("sqlite"):
        if raw_url.startswith("sqlite:///:memory:"):
            return raw_url

        if raw_url.startswith("sqlite:///"):
            sqlite_path = raw_url[len("sqlite:///") :]
            if sqlite_path == ":memory:":
                return raw_url
            sqlite_path = sqlite_path.replace("\\", "/")
            if not os.path.isabs(sqlite_path):
                sqlite_path = str((PROJECT_ROOT / sqlite_path).resolve())
            sqlite_dir = os.path.dirname(sqlite_path)
            if sqlite_dir and not os.path.exists(sqlite_dir):
                os.makedirs(sqlite_dir, exist_ok=True)
            return f"sqlite:///{sqlite_path}"

    return raw_url


DATABASE_URL = _resolve_database_url()

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "SessionLocal", "engine", "get_db"]
