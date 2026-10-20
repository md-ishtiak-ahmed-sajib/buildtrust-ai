# Tests and evidence

The latest local run passed **251 backend tests**, **10 frontend tests** and **20 browser workflows**. Four additional browser logins verified the README's public accounts. One existing Starlette/httpx dependency deprecation warning remains.

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

Contract generation agrees with OpenAPI, document schemas and frontend types. Both platforms passed [the October 20 hosted security run](https://github.com/md-ishtiak-ahmed-sajib/buildtrust-ai/actions/runs/39419213954), including browser workflows, A–H and their platform startup checks. Each hosted runner passed 250 backend tests and skipped one optional OCR test without its language files. The local suite passed 251. Advisory scans describe known issues at execution time and are not a security certificate.

Public-demo tests use unassisted sign-in: a restricted MFA challenge fails the check. A module-launch regression covers the same entry point as the Windows launcher. All four README accounts also pass real browser login without MFA. Private verification clients complete actual MFA endpoints and never bypass server controls.
