# =============================================================================
# EX-DIGITAL — Database Configuration & Session Management
# =============================================================================
# Provides a centralized SQLAlchemy engine, session factory, and declarative
# base for all ORM models. Reads the DATABASE_URL from environment variables.
# =============================================================================

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://exdigital:exdigital_secret@localhost:5432/exdigital_db",
)

# ---------------------------------------------------------------------------
# Engine — connection‑pool defaults tuned for a microservice workload
# ---------------------------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,        # auto‑reconnect on stale connections
    echo=False,                # set True for SQL debug logging
)

# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ---------------------------------------------------------------------------
# Declarative Base — all models inherit from this
# ---------------------------------------------------------------------------
Base = declarative_base()


def get_db():
    """
    FastAPI / Flask dependency that yields a scoped database session.
    Automatically closes the session when the request lifecycle ends.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
