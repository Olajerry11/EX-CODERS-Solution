# =============================================================================
# EX-DIGITAL — Gateway Configuration
# =============================================================================
# Centralized config for the Flask integration gateway, loaded from .env.
# =============================================================================

import os
from dotenv import load_dotenv

load_dotenv()


class GatewayConfig:
    """Flask configuration class."""

    # ── Flask ───────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "CHANGE_ME_FLASK_SECRET")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    PORT: int = int(os.getenv("FLASK_PORT", "5001"))

    # ── Database (shared with core_api) ─────────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://exdigital:exdigital_secret@localhost:5432/exdigital_db",
    )

    # ── External Portal / ERP ───────────────────────────────────────────────
    EXTERNAL_PORTAL_BASE_URL: str = os.getenv(
        "EXTERNAL_PORTAL_BASE_URL",
        "https://portal.university.edu/api/v1",
    )
    EXTERNAL_PORTAL_API_KEY: str = os.getenv(
        "EXTERNAL_PORTAL_API_KEY",
        "your_external_api_key_here",
    )

    # ── Gateway API Key (for inbound webhook auth) ──────────────────────────
    GATEWAY_API_KEY: str = os.getenv(
        "GATEWAY_API_KEY",
        "exdigital_gateway_secret_key",
    )

    # ── Sync Settings ───────────────────────────────────────────────────────
    SYNC_BATCH_SIZE: int = int(os.getenv("SYNC_BATCH_SIZE", "100"))
    SYNC_MAX_RETRIES: int = int(os.getenv("SYNC_MAX_RETRIES", "5"))
