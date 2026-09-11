# PROGRESS — Transaction Risk Assessment Engine

Author: Mourad.Soltani
Version: 1.0.0
Last updated: 2026-09

## Category rotation

Previous run built Tier A · Vendor Master Data Cleanup.
This run rotates to Tier B · Financial Crime Transaction Monitoring
(highest-ACV RegTech category in the approved set).

## Completed

- [x] Deterministic 7-rule AML engine (`backend/aml_engine.py`)
- [x] Every rule is a pure function; evidence block emitted per rule
- [x] Tier mapping with four bands (LOW / MEDIUM / HIGH / CRITICAL)
- [x] Flask HTTP surface with signature envelope on every response
- [x] Two POST endpoints: `/api/assess`, `/api/screen`
- [x] Static front-end at `/ui` (no framework, textContent only)
- [x] Field-level type validation at the boundary → 400 on bad input
- [x] Request body cap 512 KB, history cap 2,000 records
- [x] JSON error handlers for 400 / 404 / 413 / 500
- [x] 38 tests written and hand-verified
- [x] Dockerfile with HEALTHCHECK on `/health`
- [x] GitHub Actions workflow on push / PR to main
- [x] Signature in README, LICENSE, all source headers, all JSON responses
- [x] requirements.txt / requirements-dev.txt / pyproject.toml consistent

## Pending (next run)

- [ ] Local `pytest -v` execution
- [ ] `curl /health` against a live process
- [ ] Docker build + run verification
- [ ] GitHub push (no credentials supplied this session)
- [ ] Zip to `/home/workdir/artifacts/transaction-risk-engine-1.0.0.zip`

## Blockers

- No shell access in this session.
- No GitHub credentials; push skipped per brief §8.

## Next run

1. Save tree, run `pytest -v`, confirm 38 pass.
2. `docker build` + `docker run`, confirm HEALTHCHECK goes healthy.
3. Zip to `/home/workdir/artifacts/`.
4. Push with provided credentials.
5. On 403 or missing scope: stop and report.
