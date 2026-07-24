from sqlalchemy import create_engine
from pathlib import Path

from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import get_settings

settings = get_settings()

database_url = settings.DATABASE_URL
if database_url.startswith("sqlite:///./"):
    relative_path = database_url.removeprefix("sqlite:///./")
    database_path = Path(__file__).resolve().parents[2] / relative_path
    database_url = f"sqlite:///{database_path}"

engine_kwargs = {"connect_args": {"check_same_thread": False}} if database_url.startswith("sqlite:") else {}
engine = create_engine(database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
