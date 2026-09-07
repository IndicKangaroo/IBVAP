"""Database engine/session setup — Phase 4.

Defaults to a local SQLite file so the backend runs with zero extra
setup — no Postgres server needed to develop or demo against on a
single laptop. Point DATABASE_URL at a real Postgres instance
(`postgresql://user:pass@host/dbname`) for anything beyond that;
nothing else in this module or in models.py needs to change —
SQLAlchemy's ORM layer covers both the same way.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./ibvap.db")

# SQLite needs this flag for use across FastAPI's request-per-thread
# handling; Postgres doesn't need or want it.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they don't exist. Fine for SQLite/dev and for
    getting a hackathon demo running; a longer-lived Postgres
    deployment would normally use Alembic migrations instead of
    create_all — out of scope for the MVP."""
    from . import models  # noqa: F401 — registers models on Base before create_all
    Base.metadata.create_all(bind=engine)
