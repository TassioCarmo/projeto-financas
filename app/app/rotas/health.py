from flask import Blueprint, jsonify

from app.servicos.db import check_db

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    try:
        check_db()
        return jsonify({"status": "ok", "database": "connected"}), 200
    except Exception as exc:
        return (
            jsonify(
                {
                    "status": "degraded",
                    "database": "unreachable",
                    "error": str(exc),
                }
            ),
            503,
        )
