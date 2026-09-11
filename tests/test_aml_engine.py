"""Pure-logic tests for the AML engine.

Author: Mourad.Soltani
"""

import pytest

from backend.aml_engine import (
    HIGH_VALUE_MULTIPLIER,
    REPORTING_THRESHOLD,
    assess,
    normalize_name,
    rule_high_risk_geo,
    rule_high_value,
    rule_passthrough,
    rule_round_amount,
    rule_structuring,
    rule_velocity,
    rule_watchlist,
    tier_for_score,
)


# --- Normalization -----------------------------------------------------------

def test_normalize_name_basic():
    assert normalize_name("Acme Corp") == "acme"


def test_normalize_name_strips_accents():
    # NFKD decomposes é -> e + combining accent; combining marks dropped.
    assert normalize_name("José García") == "jose garcia"


def test_normalize_name_empty():
    assert normalize_name("") == ""


def test_normalize_name_non_string():
    assert normalize_name(None) == ""


# --- Tier mapping (boundaries) -----------------------------------------------

def test_tier_boundary_low():
    assert tier_for_score(0) == "LOW"
    assert tier_for_score(19) == "LOW"


def test_tier_boundary_medium():
    assert tier_for_score(20) == "MEDIUM"
    assert tier_for_score(49) == "MEDIUM"


def test_tier_boundary_high():
    assert tier_for_score(50) == "HIGH"
    assert tier_for_score(79) == "HIGH"


def test_tier_boundary_critical():
    assert tier_for_score(80) == "CRITICAL"
    assert tier_for_score(225) == "CRITICAL"


# --- Structuring -------------------------------------------------------------

def test_structuring_fires_at_three():
    txn = {"amount": 9500, "timestamp": 1_000_000}
    history = [
        {"amount": 9200, "timestamp": 999_000},
        {"amount": 9800, "timestamp": 998_000},
    ]
    r = rule_structuring(txn, history)
    assert r["fired"] is True
    assert r["score"] == 40
    assert r["evidence"]["count"] == 3


def test_structuring_not_fires_at_two():
    txn = {"amount": 9500, "timestamp": 1_000_000}
    history = [{"amount": 9200, "timestamp": 999_000}]
    r = rule_structuring(txn, history)
    assert r["fired"] is False
    assert r["score"] == 0
    assert r["evidence"]["count"] == 2


def test_structuring_ignores_at_threshold():
    # 10_000 is at the reporting threshold -> reportable, not structuring.
    txn = {"amount": 9500, "timestamp": 1_000_000}
    history = [
        {"amount": REPORTING_THRESHOLD, "timestamp": 999_000},
        {"amount": REPORTING_THRESHOLD + 500, "timestamp": 998_000},
        {"amount": 15_000, "timestamp": 997_000},
    ]
    r = rule_structuring(txn, history)
    assert r["fired"] is False
    assert r["evidence"]["count"] == 1


def test_structuring_window_boundary_inclusive():
    txn = {"amount": 9500, "timestamp": 1_000_000}
    # 913600 == 1_000_000 - 86400 exactly -> included
    history = [
        {"amount": 9200, "timestamp": 913_600},
        {"amount": 9300, "timestamp": 950_000},
    ]
    assert rule_structuring(txn, history)["fired"] is True

    # 1 second earlier -> excluded -> count falls to 2
    history2 = [
        {"amount": 9200, "timestamp": 913_599},
        {"amount": 9300, "timestamp": 950_000},
    ]
    assert rule_structuring(txn, history2)["fired"] is False


# --- Velocity ----------------------------------------------------------------

def test_velocity_fires_at_ten():
    txn = {"amount": 100, "timestamp": 1_000_000}
    history = [{"amount": 100, "timestamp": 999_000 - i} for i in range(9)]
    r = rule_velocity(txn, history)
    assert r["fired"] is True
    assert r["score"] == 15
    assert r["evidence"]["count"] == 10


def test_velocity_window_boundary():
    txn = {"amount": 100, "timestamp": 1_000_000}
    # One record exactly on the boundary (included) + 8 well inside -> 10 total
    history = [{"amount": 100, "timestamp": 913_600}]
    history += [{"amount": 100, "timestamp": 950_000 + i} for i in range(8)]
    assert rule_velocity(txn, history)["fired"] is True

    # Same, but boundary record 1 second earlier -> 9 total -> not fired
    history2 = [{"amount": 100, "timestamp": 913_599}]
    history2 += [{"amount": 100, "timestamp": 950_000 + i} for i in range(8)]
    assert rule_velocity(txn, history2)["fired"] is False


# --- High value --------------------------------------------------------------

def test_high_value_fires_at_exact_threshold():
    threshold = REPORTING_THRESHOLD * HIGH_VALUE_MULTIPLIER
    r = rule_high_value({"amount": threshold})
    assert r["fired"] is True
    assert r["score"] == 20
    assert r["evidence"]["threshold"] == threshold


def test_high_value_not_fires_below():
    r = rule_high_value({"amount": 29_999.99})
    assert r["fired"] is False
    assert r["score"] == 0


# --- Round amount ------------------------------------------------------------

def test_round_amount_fires():
    txn = {"amount": 7000, "timestamp": 1_000_000}
    history = [
        {"amount": 6000, "timestamp": 999_000},
        {"amount": 8000, "timestamp": 998_000},
    ]
    r = rule_round_amount(txn, history)
    assert r["fired"] is True
    assert r["score"] == 10
    assert r["evidence"]["count"] == 3


def test_round_amount_ignores_below_min():
    txn = {"amount": 4000, "timestamp": 1_000_000}
    history = [
        {"amount": 4000, "timestamp": 999_000},
        {"amount": 3000, "timestamp": 998_000},
    ]
    r = rule_round_amount(txn, history)
    assert r["fired"] is False
    assert r["evidence"]["count"] == 0


# --- High risk geo -----------------------------------------------------------

def test_high_risk_geo_fires():
    r = rule_high_risk_geo({"country": "IR"})
    assert r["fired"] is True
    assert r["score"] == 25
    assert r["evidence"]["country"] == "IR"


def test_high_risk_geo_not_fires():
    r = rule_high_risk_geo({"country": "us"})
    assert r["fired"] is False
    assert r["score"] == 0
    assert r["evidence"]["country"] == "US"


# --- Pass-through ------------------------------------------------------------

def test_passthrough_fires_exact_match():
    txn = {"amount": 10_000, "timestamp": 1_000_000, "direction": "debit"}
    history = [{"id": "H1", "amount": 10_000, "timestamp": 999_000, "direction": "credit"}]
    r = rule_passthrough(txn, history)
    assert r["fired"] is True
    assert r["score"] == 35
    assert r["evidence"]["inflow_id"] == "H1"
    assert r["evidence"]["delta_ratio"] == 0.0


def test_passthrough_tolerance_boundary_inclusive():
    # |10500 - 10000| / 10000 == 0.05 exactly -> within tolerance
    txn = {"amount": 10_500, "timestamp": 1_000_000, "direction": "debit"}
    history = [{"amount": 10_000, "timestamp": 999_000, "direction": "credit"}]
    assert rule_passthrough(txn, history)["fired"] is True

    # 1 unit larger -> ratio 0.0501 -> outside tolerance
    txn2 = {"amount": 10_501, "timestamp": 1_000_000, "direction": "debit"}
    assert rule_passthrough(txn2, history)["fired"] is False


def test_passthrough_not_fires_on_credit():
    txn = {"amount": 10_000, "timestamp": 1_000_000, "direction": "credit"}
    history = [{"amount": 10_000, "timestamp": 999_000, "direction": "credit"}]
    r = rule_passthrough(txn, history)
    assert r["fired"] is False
    assert r["evidence"]["direction"] == "credit"


# --- Watchlist ---------------------------------------------------------------

def test_watchlist_match_via_normalization():
    txn = {"counterparty": "Acme Corporation"}
    r = rule_watchlist(txn, ["Acme Corp"])
    assert r["fired"] is True
    assert r["score"] == 80
    assert r["evidence"]["normalized"] == "acme"
    assert r["evidence"]["hits"] == ["Acme Corp"]


def test_watchlist_no_match():
    txn = {"counterparty": "Globex"}
    r = rule_watchlist(txn, ["Acme", "Initech"])
    assert r["fired"] is False
    assert r["score"] == 0
    assert r["evidence"]["normalized"] == "globex"


# --- Assess (integration) ----------------------------------------------------

def test_assess_clean_transaction_is_low():
    txn = {
        "id": "T1", "amount": 100, "timestamp": 1_000_000,
        "direction": "debit", "country": "US", "counterparty": "Nobody",
    }
    result = assess(txn, history=[], watchlist=[])
    assert result["score"] == 0
    assert result["tier"] == "LOW"
    assert result["alert"] is False
    assert result["fired_rules"] == []


def test_assess_structuring_is_high():
    # Structuring (40) + Velocity (15) = 55 -> HIGH.
    # History uses debit so PASSTHROUGH cannot match a credit inflow.
    txn = {
        "id": "T1", "amount": 9500, "timestamp": 1_000_000,
        "direction": "debit", "country": "US", "counterparty": "Nobody",
    }
    history = [
        {"amount": amt, "timestamp": 999_000 + i, "direction": "debit"}
        for i, amt in enumerate([9100, 9200, 9300, 9400, 9500, 9600, 9700, 9800, 9900])
    ]
    result = assess(txn, history=history, watchlist=[])
    assert result["score"] == 55
    assert result["tier"] == "HIGH"
    assert result["alert"] is True
    assert result["fired_rules"] == ["STRUCTURING", "VELOCITY"]


def test_assess_sanctions_is_critical():
    txn = {
        "id": "T1", "amount": 100, "timestamp": 1_000_000,
        "direction": "debit", "country": "US", "counterparty": "Sanctioned Entity",
    }
    result = assess(txn, history=[], watchlist=["Sanctioned Entity"])
    assert result["score"] == 80
    assert result["tier"] == "CRITICAL"
    assert result["alert"] is True
    assert result["fired_rules"] == ["WATCHLIST_MATCH"]


def test_assess_returns_all_seven_signals():
    txn = {"id": "T1", "amount": 100, "timestamp": 1_000_000}
    result = assess(txn, history=[], watchlist=[])
    assert len(result["signals"]) == 7
    ids = {s["rule_id"] for s in result["signals"]}
    assert ids == {
        "STRUCTURING", "VELOCITY", "HIGH_VALUE", "ROUND_AMOUNT",
        "HIGH_RISK_GEO", "PASSTHROUGH", "WATCHLIST_MATCH",
    }
