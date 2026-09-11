"""Deterministic AML/CFT transaction risk scoring engine.

Every rule is a pure function. Every score is reproducible byte-for-byte
across runs. No external API calls. No randomness. No state. This is a
deliberate design choice: an AML alert must survive an audit, and a raw
model call cannot guarantee that.

Author: Mourad.Soltani
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


# --- Rule configuration ------------------------------------------------------

REPORTING_THRESHOLD = 10_000.0

STRUCTURING_MARGIN = 0.9
STRUCTURING_MIN_COUNT = 3
STRUCTURING_WINDOW_SECONDS = 24 * 3600

VELOCITY_WINDOW_SECONDS = 24 * 3600
VELOCITY_MIN_COUNT = 10

HIGH_VALUE_MULTIPLIER = 3.0

ROUND_AMOUNT_MIN = 5_000.0
ROUND_AMOUNT_STEP = 1_000.0
ROUND_AMOUNT_MIN_COUNT = 3
ROUND_AMOUNT_WINDOW_SECONDS = 7 * 24 * 3600

PASSTHROUGH_WINDOW_SECONDS = 48 * 3600
PASSTHROUGH_TOLERANCE = 0.05

HIGH_RISK_JURISDICTIONS = frozenset({
    "IR", "KP", "SY", "CU", "MM", "AF", "YE", "LY", "SO", "SS", "SD",
})

RULE_SCORES: dict[str, int] = {
    "WATCHLIST_MATCH": 80,
    "STRUCTURING": 40,
    "PASSTHROUGH": 35,
    "HIGH_RISK_GEO": 25,
    "HIGH_VALUE": 20,
    "VELOCITY": 15,
    "ROUND_AMOUNT": 10,
}

# Ordered highest threshold first; tier_for_score scans top down.
TIER_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (80, "CRITICAL"),
    (50, "HIGH"),
    (20, "MEDIUM"),
    (0, "LOW"),
)

LEGAL_SUFFIXES: frozenset[str] = frozenset({
    "inc", "incorporated", "llc", "llp", "lp", "ltd", "limited",
    "corp", "corporation", "co", "company",
    "gmbh", "ag", "kg", "ohg", "ug",
    "sa", "sas", "sarl", "bv", "nv", "plc", "pty", "pvt",
    "srl", "spa", "sprl", "kk", "oy", "ab", "as", "aps",
})


# --- Helpers -----------------------------------------------------------------

def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalize_name(name: Any) -> str:
    """Canonical entity name for watchlist comparison.

    Lowercase, accents stripped, non-alphanumerics collapsed, legal
    suffixes removed. If stripping suffixes would empty the name,
    fall back to the raw token list so the record keeps a signal.
    """
    if not isinstance(name, str):
        return ""
    lowered = _strip_accents(name).lower()
    toks = [t for t in re.sub(r"[^a-z0-9]+", " ", lowered).split() if t]
    stripped = [t for t in toks if t not in LEGAL_SUFFIXES]
    final = stripped if stripped else toks
    return " ".join(final)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _window(txn: dict, history: list, seconds: int) -> list:
    """All records (current + history) with ts in [t - seconds, t], inclusive."""
    t = txn.get("timestamp")
    if not _is_number(t):
        return []
    start = t - seconds
    out: list = []
    for x in [txn] + list(history):
        if not isinstance(x, dict):
            continue
        ts = x.get("timestamp")
        if _is_number(ts) and start <= ts <= t:
            out.append(x)
    return out


def tier_for_score(score: int) -> str:
    for threshold, tier in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "LOW"


# --- Rules -------------------------------------------------------------------

def rule_structuring(txn: dict, history: list) -> dict:
    """Multiple transactions just below the reporting threshold.

    Band is [REPORTING_THRESHOLD * MARGIN, REPORTING_THRESHOLD). An
    amount at or above the threshold is a reportable transaction, not
    structuring.
    """
    window = _window(txn, history, STRUCTURING_WINDOW_SECONDS)
    lo = REPORTING_THRESHOLD * STRUCTURING_MARGIN
    hi = REPORTING_THRESHOLD
    near = [
        x for x in window
        if _is_number(x.get("amount")) and lo <= x["amount"] < hi
    ]
    fired = len(near) >= STRUCTURING_MIN_COUNT
    return {
        "rule_id": "STRUCTURING",
        "fired": fired,
        "score": RULE_SCORES["STRUCTURING"] if fired else 0,
        "detail": (
            f"{len(near)} near-threshold transaction(s) in "
            f"{STRUCTURING_WINDOW_SECONDS // 3600}h window"
        ),
        "evidence": {
            "count": len(near),
            "window_hours": STRUCTURING_WINDOW_SECONDS // 3600,
            "band_low": lo,
            "band_high_exclusive": hi,
        },
    }


def rule_velocity(txn: dict, history: list) -> dict:
    window = _window(txn, history, VELOCITY_WINDOW_SECONDS)
    fired = len(window) >= VELOCITY_MIN_COUNT
    return {
        "rule_id": "VELOCITY",
        "fired": fired,
        "score": RULE_SCORES["VELOCITY"] if fired else 0,
        "detail": (
            f"{len(window)} transaction(s) in "
            f"{VELOCITY_WINDOW_SECONDS // 3600}h window"
        ),
        "evidence": {
            "count": len(window),
            "window_hours": VELOCITY_WINDOW_SECONDS // 3600,
        },
    }


def rule_high_value(txn: dict) -> dict:
    amount = txn.get("amount")
    threshold = REPORTING_THRESHOLD * HIGH_VALUE_MULTIPLIER
    fired = _is_number(amount) and amount >= threshold
    return {
        "rule_id": "HIGH_VALUE",
        "fired": fired,
        "score": RULE_SCORES["HIGH_VALUE"] if fired else 0,
        "detail": f"single transaction >= {threshold}",
        "evidence": {
            "amount": amount if _is_number(amount) else None,
            "threshold": threshold,
        },
    }


def rule_round_amount(txn: dict, history: list) -> dict:
    window = _window(txn, history, ROUND_AMOUNT_WINDOW_SECONDS)
    rounds = [
        x["amount"] for x in window
        if _is_number(x.get("amount"))
        and x["amount"] >= ROUND_AMOUNT_MIN
        and x["amount"] % ROUND_AMOUNT_STEP == 0
    ]
    fired = len(rounds) >= ROUND_AMOUNT_MIN_COUNT
    return {
        "rule_id": "ROUND_AMOUNT",
        "fired": fired,
        "score": RULE_SCORES["ROUND_AMOUNT"] if fired else 0,
        "detail": (
            f"{len(rounds)} round-amount transaction(s) in "
            f"{ROUND_AMOUNT_WINDOW_SECONDS // 86400}d window"
        ),
        "evidence": {
            "count": len(rounds),
            "step": ROUND_AMOUNT_STEP,
            "min": ROUND_AMOUNT_MIN,
        },
    }


def rule_high_risk_geo(txn: dict) -> dict:
    raw = txn.get("country")
    cc = raw.upper() if isinstance(raw, str) else ""
    fired = cc in HIGH_RISK_JURISDICTIONS
    return {
        "rule_id": "HIGH_RISK_GEO",
        "fired": fired,
        "score": RULE_SCORES["HIGH_RISK_GEO"] if fired else 0,
        "detail": f"counterparty jurisdiction {cc or 'unknown'}",
        "evidence": {"country": cc, "list_size": len(HIGH_RISK_JURISDICTIONS)},
    }


def rule_passthrough(txn: dict, history: list) -> dict:
    """Incoming credit followed by a near-identical outgoing debit.

    Only evaluated on outgoing transactions. Tolerance is computed
    against the *inflow* amount so the denominator is stable.
    """
    if txn.get("direction") != "debit":
        return {
            "rule_id": "PASSTHROUGH",
            "fired": False,
            "score": 0,
            "detail": "not an outgoing transaction",
            "evidence": {"direction": txn.get("direction")},
        }

    out_amt = txn.get("amount")
    t = txn.get("timestamp")
    if not _is_number(out_amt) or out_amt <= 0 or not _is_number(t):
        return {
            "rule_id": "PASSTHROUGH",
            "fired": False,
            "score": 0,
            "detail": "missing or invalid amount/timestamp",
            "evidence": {"amount": out_amt, "timestamp": t},
        }

    matched: dict | None = None
    for x in history:
        if not isinstance(x, dict) or x.get("direction") != "credit":
            continue
        ts = x.get("timestamp")
        in_amt = x.get("amount")
        if not _is_number(ts) or not _is_number(in_amt) or in_amt <= 0:
            continue
        if ts > t or (t - ts) > PASSTHROUGH_WINDOW_SECONDS:
            continue
        if abs(out_amt - in_amt) / in_amt <= PASSTHROUGH_TOLERANCE:
            matched = {
                "inflow_id": x.get("id"),
                "inflow_amount": in_amt,
                "inflow_timestamp": ts,
                "delta_ratio": round(abs(out_amt - in_amt) / in_amt, 6),
            }
            break

    fired = matched is not None
    return {
        "rule_id": "PASSTHROUGH",
        "fired": fired,
        "score": RULE_SCORES["PASSTHROUGH"] if fired else 0,
        "detail": "matched pass-through inflow" if fired else "no matched inflow",
        "evidence": matched or {
            "outflow_amount": out_amt,
            "tolerance": PASSTHROUGH_TOLERANCE,
            "window_hours": PASSTHROUGH_WINDOW_SECONDS // 3600,
        },
    }


def rule_watchlist(txn: dict, watchlist: list) -> dict:
    normalized = normalize_name(txn.get("counterparty"))
    if not normalized:
        return {
            "rule_id": "WATCHLIST_MATCH",
            "fired": False,
            "score": 0,
            "detail": "no counterparty name supplied",
            "evidence": {"normalized": ""},
        }
    hits: list = []
    for entry in watchlist:
        if isinstance(entry, dict):
            candidate = entry.get("name")
        elif isinstance(entry, str):
            candidate = entry
        else:
            continue
        if normalize_name(candidate) == normalized:
            hits.append(candidate)
    fired = len(hits) > 0
    return {
        "rule_id": "WATCHLIST_MATCH",
        "fired": fired,
        "score": RULE_SCORES["WATCHLIST_MATCH"] if fired else 0,
        "detail": f"{len(hits)} watchlist hit(s)" if fired else "no watchlist hit",
        "evidence": {"normalized": normalized, "hits": hits},
    }


# --- Engine ------------------------------------------------------------------

def assess(txn: dict, history: list | None = None, watchlist: list | None = None) -> dict:
    """Assess one transaction against all rules. Returns full explainability."""
    if not isinstance(txn, dict):
        raise TypeError("transaction must be a dict")
    if history is None:
        history = []
    if watchlist is None:
        watchlist = []
    if not isinstance(history, list):
        raise TypeError("history must be a list")
    if not isinstance(watchlist, list):
        raise TypeError("watchlist must be a list")

    signals = [
        rule_structuring(txn, history),
        rule_velocity(txn, history),
        rule_high_value(txn),
        rule_round_amount(txn, history),
        rule_high_risk_geo(txn),
        rule_passthrough(txn, history),
        rule_watchlist(txn, watchlist),
    ]
    total = sum(s["score"] for s in signals)
    tier = tier_for_score(total)
    fired_ids = [s["rule_id"] for s in signals if s["fired"]]
    return {
        "transaction_id": txn.get("id"),
        "score": total,
        "tier": tier,
        "alert": tier in ("HIGH", "CRITICAL"),
        "fired_rules": fired_ids,
        "signals": signals,
    }
