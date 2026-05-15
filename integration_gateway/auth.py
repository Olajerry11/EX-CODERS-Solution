# =============================================================================
# EX-DIGITAL — Gateway Authentication Middleware
# =============================================================================
# Provides API-key-based authentication for inbound webhook/export requests
# from external systems. This is separate from the JWT auth used internally.
# =============================================================================

from functools import wraps

from flask import request, jsonify

from .config import GatewayConfig


def require_api_key(f):
    """
    Decorator that enforces API key authentication on Flask routes.

    External systems must include the key in one of:
      • Header: X-API-Key: <key>
      • Query param: ?api_key=<key>
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = (
            request.headers.get("X-API-Key")
            or request.args.get("api_key")
        )

        if not api_key:
            return jsonify({
                "error": "Authentication required",
                "detail": "Provide API key via X-API-Key header or api_key query parameter",
            }), 401

        if api_key != GatewayConfig.GATEWAY_API_KEY:
            return jsonify({
                "error": "Invalid API key",
                "detail": "The provided API key is not authorized",
            }), 403

        return f(*args, **kwargs)

    return decorated
