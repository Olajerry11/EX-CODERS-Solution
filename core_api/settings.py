# =============================================================================
# EX-DIGITAL — Application Settings (Pydantic Settings)
# =============================================================================
# Centralized, type-safe configuration loaded from environment variables.
# =============================================================================

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    All configuration is read from environment variables (or .env file).
    Pydantic validates types and provides sensible defaults.
    """

    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://exdigital:exdigital_secret@localhost:5432/exdigital_db"

    # ── JWT ─────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE_ME_TO_A_LONG_RANDOM_STRING"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Server ──────────────────────────────────────────────────────────────
    FASTAPI_PORT: int = 8000

    # ── Session Defaults ────────────────────────────────────────────────────
    DEFAULT_SESSION_DURATION_HOURS: int = 2

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
