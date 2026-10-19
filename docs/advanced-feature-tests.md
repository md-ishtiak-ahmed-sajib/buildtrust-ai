> Historical test report from October 18, 2026. Counts and deferred features below describe that earlier checkpoint. Read [current verification](completion-verification.md) for the latest results. The original report is preserved; it is not the current backlog.

# Upgrade validation — actual results

Executed locally on October 18, 2026, using Windows, Python 3.12 and Node 24.

| Check | Actual result | Evidence |
|---|---|---|
| Complete backend suite | 95 passed, one existing Starlette deprecation warning; 60.72 seconds | `data/advanced-verification/backend-tests.log` |
| Upgrade backend subset | 34 passed | Includes API, provider protocol, math, import, concurrency, snapshot and permission checks |
| Frontend unit tests | 8 passed across 2 files | Actual Vitest execution |
| Production build | TypeScript and Vite passed | Actual build; version 0.2.0 |
| Browser flows | 4 passed, 10.9 seconds | `data/advanced-browser-7b763a93/browser-tests.log` and actual screenshots |
| Original A–H scenarios | All 8 passed over real local HTTP | `data/advanced-api-evidence/` |
| Migration/recovery from original pre-upgrade database | 26 legacy tables unchanged; SQLite integrity passed | `data/migration-check-eb81e95e/result.json` |
| Fresh Windows source-copy installation | Passed locked setup, build, migrations, old payment and new estimate smoke checks | `data/advanced-clean-install/clean-install.json` and redacted log |
| Undefined names/import checks | Ruff F checks passed | Actual command execution |

## Exercised behavior

The browser journey opens an existing estimate material, observes an honest missing
provider state, explicitly searches the synthetic catalogue, blocks the cheaper
wrong-grade entry, previews and confirms a selected rate, verifies the 80,000 BDT
estimate/forecast difference, asks the persisted copilot, and completes Operator →
Finance Manager → Admin checking and approval. It creates an editable revision of
the locked approved version. The mobile journey calculates/saves 9.6 m3 for 20 columns.
The original browser journeys still verify payment/receipt/audit and PDF upload.

Backend checks cover both provider response parsers, missing credentials, empty results,
source URL preservation/rejection, known-unit/packaging/density conversions, sourced
FX, wrong grades, expiry/staleness, unknown costs, selection eligibility, immutable
snapshots after new searches, rate/estimate propagation, locked historical versions,
geometry, profile snapshots, rate build-up/rounding, budget warnings, forecast arithmetic,
project access and unauthorized approval, provider timeout isolation, paid-task resume
without resubmission, ambiguous-submission blocking, provenance/audit, actual CSV/XLSX/
PDF contents, formula rejection, parallel price selection, complete approval evidence,
revoked checker authority, changed material requirements, and preserved archived runs.

The original 61 backend tests continue to verify payment security and all original
financial/document requirements. A–H real HTTP evidence uses its own database and port.
Browser tests use a separate database/server, preserving the user's workspace.

## Commands

```powershell
uv run --project backend pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run build
uv run --project backend python scripts/verify_upgrade_browser.py
uv run --project backend python scripts/verify_upgrade_migration.py
uv run --project backend python scripts/verify_clean_install.py --output data/advanced-clean-install
uv run --project backend python scripts/collect_evidence.py --port 8011 --output data/advanced-api-evidence
```

## Qualifications

Provider fixtures are synthetic, shaped from official documentation, not captured
live market offers. No live SerpApi/DataForSEO credentials were supplied or tested.
The live FX adapter exists; no live rate is claimed as validated by the offline tests.
Docker/Linux and an optional live Ollama model were not newly validated.

The broader brief's EVM test belongs to the explicitly deferred EVM release; it is not
claimed as implemented or passed. The core release exercises the applicable price/QS/
estimate/forecast/security categories. Passing 34 new tests does not imply every
future module in the longer brief exists.

Transient test and UI failures discovered during development were fixed before the
passing runs above. Existing submission artifacts were left untouched; this report
describes the working repository, not a regenerated competition archive.
