# =============================================================================
# EX-DIGITAL — Flask Integration Gateway (app.py)
# =============================================================================
# Entry point for the Flask gateway service. Registers all blueprints,
# configures logging, and provides health/status endpoints.
#
# Run:  python -m integration_gateway.app
#   or: flask --app integration_gateway.app run --port 5001
# =============================================================================

import logging
from datetime import datetime, timezone

from flask import Flask, jsonify

from database.config import Base, engine
from database.models import User, Course, Session, AttendanceLog, SyncLog  # noqa: F401

from .config import GatewayConfig
from .export import export_bp
from .sync import sync_bp


def create_app() -> Flask:
    """Flask application factory."""

    app = Flask(__name__)
    app.config.from_object(GatewayConfig)

    # ── Logging ────────────────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # ── Ensure tables exist (graceful if DB not yet available) ───────────
    with app.app_context():
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as exc:
            logging.warning("Could not connect to database on startup: %s", exc)
            logging.warning("Tables will be created when the database becomes available.")

    # ── Register blueprints ────────────────────────────────────────────────
    app.register_blueprint(export_bp)
    app.register_blueprint(sync_bp)

    # ── Health endpoints ───────────────────────────────────────────────────

    @app.route("/", methods=["GET"])
    def root():
        return jsonify({
            "service": "EX-DIGITAL Integration Gateway",
            "status": "operational",
            "version": "1.0.0",
            "endpoints": {
                "export": "/gateway/v1/export/...",
                "sync": "/gateway/v1/sync/...",
            },
        })

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return app


# ── Direct execution ───────────────────────────────────────────────────────

if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=GatewayConfig.PORT,
        debug=GatewayConfig.DEBUG,
    )
