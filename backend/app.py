"""Flask HTTP surface for the Transaction Risk Assessment Engine.

Author: Mourad.Soltani
"""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, request, send_from_directory

from backend import aml_engine
from backend.config import (
    AUTHOR,
    MAX_CONTENT_LENGTH,
    MAX_HISTORY_RECORDS,
    PROJECT_NAME,
    SIGNATURE,
    VERSION,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)
_INDEX_PATH = os.path.join(FRONTEND_DIR, "index.html")

if not os.path.isfile(_INDEX_PATH):
    logger.warning(
        "frontend/index.html not found at %s — /ui will return 404", _INDEX_PATH
    )


# --- Envelope ----------------------------------------------------------------

def _envelope(payload: dict, status: int = 200):
    body = {"signature": SIGNATURE, "author": AUTHOR, "version": VERSION}
    body.update(payload)
    return jsonify(body), status


# --- Error handlers ----------------------------------------------------------

@app.errorhandler(400)
def _err_400(e):
    return _envelope(
        {"error": "bad_request", "message": str(getattr(e, "description", e))}, 400
    )


@app.errorhandler(404)
def _err_404(e):
    return _envelope({"error": "not_found", "message": "Endpoint not found"}, 404)


@app.errorhandler(413)
def _err_413(e):
    return _envelope(
        {"error": "payload_too_large", "message": "Request body exceeds limit"}, 413
    )


@app.errorhandler(500)
def _err_500(e):
    return _envelope({"error": "internal_error", "message": "Server error"}, 500)


# --- Validation helpers ------------------------------------------------------

def _validate_txn_fields(txn: dict) -> str | None:
    """Return an error message for an invalid field, or None if OK.

    The engine tolerates missing fields. It does not tolerate a field
    that is present with a nonsense type — that is a client bug, not a
    partial record.
    """
    if "amount" in txn and not isinstance(txn["amount"], (int, float)):
        return "'amount' must be numeric"
    if isinstance(txn.get("amount"), bool):
        return "'amount' must be numeric"
    if "timestamp" in txn and not isinstance(txn["timestamp"], (int, float)):
        return "'timestamp' must be numeric"
    if isinstance(txn.get("timestamp"), bool):
        return "'timestamp' must be numeric"
    if "direction" in txn and txn["direction"] not in ("debit", "credit"):
        return "'direction' must be 'debit' or 'credit'"
    if "country" in txn and not isinstance(txn["country"], str):
        return "'country' must be a string"
    if "counterparty" in txn and not isinstance(txn["counterparty"], str):
        return "'counterparty' must be a string"
    return None


# --- Routes ------------------------------------------------------------------

@app.get("/health")
def health():
    return _envelope({"status": "ok", "project": PROJECT_NAME})


@app.get("/")
def index():
    return _envelope({
        "project": PROJECT_NAME,
        "endpoints": ["/health", "/api/assess", "/api/screen", "/ui"],
    })


@app.post("/api/assess")
def assess_endpoint():
    data = request.get_json(silent=True)
    if data is None:
        return _envelope(
            {"error": "invalid_json", "message": "Body must be valid JSON"}, 400
        )
    if not isinstance(data, dict):
        return _envelope(
            {"error": "invalid_payload", "message": "Body must be a JSON object"}, 400
        )

    txn = data.get("transaction")
    if not isinstance(txn, dict):
        return _envelope(
            {"error": "invalid_payload", "message": "'transaction' must be an object"},
            400,
        )

    field_error = _validate_txn_fields(txn)
    if field_error is not None:
        return _envelope({"error": "invalid_payload", "message": field_error}, 400)

    history = data.get("history", [])
    if not isinstance(history, list):
        return _envelope(
            {"error": "invalid_payload", "message": "'history' must be an array"}, 400
        )
    if len(history) > MAX_HISTORY_RECORDS:
        return _envelope(
            {
                "error": "payload_too_large",
                "message": f"Maximum {MAX_HISTORY_RECORDS} history records",
            },
            400,
        )

    watchlist = data.get("watchlist", [])
    if not isinstance(watchlist, list):
        return _envelope(
            {"error": "invalid_payload", "message": "'watchlist' must be an array"}, 400
        )

    result = aml_engine.assess(txn, history, watchlist)
    return _envelope({"result": result})


@app.post("/api/screen")
def screen_endpoint():
    data = request.get_json(silent=True)
    if data is None:
        return _envelope(
            {"error": "invalid_json", "message": "Body must be valid JSON"}, 400
        )
    if not isinstance(data, dict):
        return _envelope(
            {"error": "invalid_payload", "message": "Body must be a JSON object"}, 400
        )

    name = data.get("name")
    if not isinstance(name, str):
        return _envelope(
            {"error": "invalid_payload", "message": "'name' must be a string"}, 400
        )

    watchlist = data.get("watchlist", [])
    if not isinstance(watchlist, list):
        return _envelope(
            {"error": "invalid_payload", "message": "'watchlist' must be an array"}, 400
        )

    normalized = aml_engine.normalize_name(name)
    matches: list = []
    for entry in watchlist:
        if isinstance(entry, dict):
            candidate = entry.get("name")
        elif isinstance(entry, str):
            candidate = entry
        else:
            continue
        if aml_engine.normalize_name(candidate) == normalized:
            matches.append(candidate)

    return _envelope({
        "result": {
            "name": name,
            "normalized_name": normalized,
            "matches": matches,
        }
    })


# --- UI (static) -------------------------------------------------------------

@app.get("/ui")
def ui_index():
    if not os.path.isfile(_INDEX_PATH):
        return _envelope({"error": "not_found", "message": "UI not available"}, 404)
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/ui/<path:filename>")
def ui_static(filename: str):
    return send_from_directory(FRONTEND_DIR, filename)
