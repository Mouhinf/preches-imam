"""Database configuration with SQLAlchemy.

Uses PostgreSQL (via DATABASE_URL env var) on Vercel,
falls back to SQLite in a writable directory for local development.
"""
import os
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    try:
        BASE_DIR = Path(__file__).resolve().parent.parent
        DB_PATH = BASE_DIR / "storage" / "preches.db"
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        DB_PATH = Path(tempfile.gettempdir()) / "preches-imam" / "preches.db"
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models
    Base.metadata.create_all(bind=engine)
