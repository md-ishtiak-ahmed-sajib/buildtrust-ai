# Tests and evidence

The latest local run passed **203 backend tests**, **8 frontend tests** and **16 browser workflows**. Four additional browser logins verified the README's public accounts. One existing Starlette/httpx dependency deprecation warning remains.

Read [completion verification](completion-verification.md) for exact evidence, artifact checks and platform status. The evidence folder contains actual output, not invented results.

## Run checks safely

```powershell
uv run --project backend pytest backend/tests
npm --prefix frontend test
npm --prefix frontend run build
uv run --project backend python scripts/verify_upgrade_browser.py
uv run --project backend python scripts/collect_evidence.py --output data/my-api-evidence
```

The browser wrapper starts a private test server on port 8010. The HTTP collector starts its own server on port 8001. Both use separate databases. Install Chromium before the first browser run. Do not point direct browser tests at the working app because demo-reset actions can change fictional data.

The fresh Windows installer checks the ordinary private setup, then launches the public profile in the same isolated source copy. It verifies four public logins, denied writes/self-approval, the BDT 70,000 payment, audit integrity, repeat preparation, occupied-port handling and unchanged private records.

Contract generation must leave OpenAPI/document/frontend contracts unchanged. Advisory scans report known issues at execution time; they are not a security certificate. The hosted workflow runs Windows/Ubuntu checks and records its source revision. A queued job is not a pass.
