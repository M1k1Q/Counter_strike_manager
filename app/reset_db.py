import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database import engine, Base
from app import models

def reset_database():
    print("Cleaning database...")
    
    # Drop all existing tables (wipes data and schema)
    Base.metadata.drop_all(bind=engine)
    
    # Recreate tables from scratch (fresh start)
    Base.metadata.create_all(bind=engine)
    
    print("Database cleared")

if __name__ == "__main__":
    reset_database()
