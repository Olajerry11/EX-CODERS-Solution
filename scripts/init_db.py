# =============================================================================
# EX-DIGITAL — Database Initialization Script
# =============================================================================
# Waits for PostgreSQL to be ready, runs migrations, then seeds the database.
# Used as a one-time setup step after `docker compose up`.
#
# Usage (from host, after containers are running):
#   docker exec exdigital-fastapi python -m database.migrations
#   docker exec exdigital-fastapi python -m database.seed
#
# Or run this script directly in a local venv:
#   python scripts/init_db.py
# =============================================================================

import sys
import time
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def wait_for_db(max_retries: int = 30, delay: float = 2.0):
    """Wait for PostgreSQL to accept connections."""
    from database.config import engine

    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(conn.connection.cursor().execute("SELECT 1") if False else __import__("sqlalchemy").text("SELECT 1"))
                print(f"✅  Database is ready (attempt {attempt})")
                return
        except Exception:
            print(f"⏳  Waiting for database... (attempt {attempt}/{max_retries})")
            time.sleep(delay)

    print("❌  Could not connect to database after max retries")
    sys.exit(1)


def main():
    print("=" * 60)
    print("  EX-DIGITAL — Database Initialization")
    print("=" * 60)

    # Step 1: Wait for DB
    wait_for_db()

    # Step 2: Run migrations
    from database.migrations import run_migrations
    run_migrations()

    # Step 3: Seed
    response = input("\n🌱  Seed the database with sample data? [y/N]: ").strip().lower()
    if response in ("y", "yes"):
        from database.seed import seed
        seed()
    else:
        print("⏭️   Skipping seed.")

    print("\n🎉  Database initialization complete!")


if __name__ == "__main__":
    main()
