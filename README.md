# Transaction Risk Assessment Engine

**Author: Mourad.Soltani** · Version 1.0.0 · MIT

Deterministic AML/CFT transaction risk scoring with fully explainable alerts.
Built for banks, fintechs, and money services businesses that need every
alert to survive an audit.

## Why this exists

AML alerting has an explainability problem. When a regulator asks why a
transaction was escalated, a model-score answer is not sufficient — the
institution needs the exact rule, the exact window, and the exact numeric
evidence that drove the decision, reproducible byte-for-byte on demand.

This engine delivers that. Seven rule families, each a pure function,
each emitting a structured evidence block alongside its verdict. The
human reviewer approves, rejects, or escalates with the reasoning in hand.

## What it is not

- Not an LLM wrapper. No model calls. No external APIs. No randomness.
- Not a SaaS. No auth, no billing, no persistence.
- Not a replacement for a case-management system. It is the scoring
  core that feeds one.

## Rules

| Rule | Score | Fires when |
|---|---|---|
| `WATCHLIST_MATCH` | 80 | Counterparty name matches a supplied watchlist entry after normalization (accents stripped, legal suffixes removed, lowercase) |
| `STRUCTURING` | 40 | ≥ 3 transactions in a 24h window with amount in `[0.9 × threshold, threshold)` |
| `PASSTHROUGH` | 35 | Outgoing debit within 48h of an incoming credit of near-identical amount (≤ 5% delta on the inflow) |
| `HIGH_RISK_GEO` | 25 | Counterparty jurisdiction is on the internal high-risk list |
| `HIGH_VALUE` | 20 | Single transaction ≥ 3 × the reporting threshold |
| `VELOCITY` | 15 | ≥ 10 transactions in a 24h window |
| `ROUND_AMOUNT` | 10 | ≥ 3 transactions ≥ 5,000 in a 7-day window with amount divisible by 1,000 |

Default reporting threshold: **10,000** (currency-agnostic; buyer configures).

## Risk tiers

| Score | Tier | Alert? |
|---|---|---|
| 0–19 | LOW | no |
| 20–49 | MEDIUM | no |
| 50–79 | HIGH | yes |
| 80+ | CRITICAL | yes |

A single watchlist hit is CRITICAL on its own. Structuring alone is MEDIUM.
Structuring + velocity is HIGH.

## Install

Requires Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Run locally

```bash
python run.py
```

Then open `http://localhost:5000/ui`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Liveness + version + signature |
| GET  | `/` | Project metadata + endpoint index |
| POST | `/api/assess` | Score one transaction against all rules |
| POST | `/api/screen` | Screen a name against a supplied watchlist |
| GET  | `/ui` | Static HTML front-end |

Every JSON response carries `signature: "Mourad.Soltani"`.

### Example — assess

```bash
curl -s -X POST http://localhost:5000/api/assess \
  -H 'Content-Type: application/json' \
  -d '{
    "transaction": {
      "id": "T1", "amount": 9500, "timestamp": 1000000,
      "direction": "debit", "country": "US", "counterparty": "Acme Corp"
    },
    "history": [
      {"amount": 9200, "timestamp": 999000, "direction": "credit"},
      {"amount": 9300, "timestamp": 998000, "direction": "credit"}
    ],
    "watchlist": ["Sanctioned Entity"]
  }' | python -m json.tool
```

The response includes `result.signals` — one entry per rule, each with
`fired`, `score`, `detail`, and an `evidence` block. This is the audit
trail.

### Example — screen

```bash
curl -s -X POST http://localhost:5000/api/screen \
  -H 'Content-Type: application/json' \
  -d '{"name":"Acme Corporation","watchlist":["Acme Corp","Globex"]}'
```

## Tests

38 tests across health, pure logic, and HTTP endpoints.

```bash
pytest -v
```

## Docker

```bash
docker build -t tre .
docker run --rm -p 5000:5000 tre
```

The image ships a `HEALTHCHECK` that polls `/health`.

## Limits

- Name matching is exact-after-normalization. No fuzzy / phonetic matching
  in v1 — that would break the reproducibility guarantee. A fuzzy layer
  belongs in v2 as a separate, clearly-labeled signal.
- High-risk jurisdiction list is a small internal constant, not a live
  feed. Production use requires wiring to the institution's own list.
- Rule thresholds are compile-time constants. Production deployment
  should promote them to configuration; the engine is designed so that
  is a mechanical change.

## License

MIT — see LICENSE. Author: Mourad.Soltani.
