# =============================================================================
# EX-DIGITAL — Programmatic Migration Runner
# =============================================================================
# Creates all tables from the ORM models.
# Run:  python -m database.migrations
# =============================================================================

from .config import engine, Base
from .models import (  # noqa: F401 — ensure all models are imported
    User, Course, Enrollment, Session, AttendanceLog, SyncLog,
)


def run_migrations():
    """Create all tables that don't already exist."""
    print("⏳  Running migrations (create_all) …")
    Base.metadata.create_all(bind=engine)
    print("✅  All tables are up to date.")


if __name__ == "__main__":
    run_migrations()
