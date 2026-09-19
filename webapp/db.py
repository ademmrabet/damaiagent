"""
Database connection and session management for the users table.

Deliberately separate from the DAM knowledge base: nodes/graph are
immutable, in-memory, and loaded once from data/processed/nodes.json
(see dashboard_data.py and backend.py's load_dam()). Accounts,
passwords, and OAuth links are a different kind of data - mutable,
per-user, and needing to survive process restarts - so they get a
real database instead.

DATABASE_URL controls where that database lives:
  - Locally, with no DATABASE_URL set, this falls back to a SQLite
    file (local_dev.db) so auth can be built and tested without
    signing up for a hosted database first.
  - In production, DATABASE_URL should point at a Postgres instance
    with a persistent disk (Neon, Supabase, or similar) - Render's
    own free tier has no persistent disk, so a SQLite file there
    would be wiped on every redeploy, silently deleting every
    registered user. This mirrors the exact class of problem that
    forced the nodes-cache change described in Chapter 3/5 (Render
    OOM-killing a process that assumed local state would persist).
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local_dev.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session, always closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables that don't exist yet. Safe to call on every startup."""
    from webapp import models

    Base.metadata.create_all(bind=engine)
