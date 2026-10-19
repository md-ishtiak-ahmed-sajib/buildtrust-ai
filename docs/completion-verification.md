# Completion verification — October 19, 2026

The locally tested application is available at http://127.0.0.1:8000/. Settlement remains simulated. [Remaining work](../prompt/Not%20implemented.md) separates missing external prerequisites and human handoff.

## Executed release checks

| Check | Result | Evidence |
|---|---|---|
| Full backend suite | 191 passed; one existing Starlette/httpx deprecation warning | submission/execution-evidence/backend-tests.log |
| Frontend tests | 8 passed | submission/execution-evidence/frontend-tests.log |
| Production build | Passed | submission/execution-evidence/frontend-build.log |
| Isolated browser workflows | 16 passed | submission/execution-evidence/browser-tests.log; submission/screenshots/ |
| Original HTTP scenarios | A–H passed | submission/execution-evidence/manifest.json; scenario-a through scenario-h.json |
| Audit chain | Valid | HTTP manifest and local upgrade evidence |
| Populated migration/recovery | Head 0017; 54 legacy table/column fingerprints unchanged; integrity and recovery passed | migration-recovery.log; local-upgrade-preservation.json |
| Private state preservation | Credentials, signing secret, legacy balances, approvals, settlements and receipts unchanged during migration | local-upgrade-preservation.json |
| Source archive installation | Passed: unpacked archive checksums, locked setup, build, independent payment/estimating/audit smoke checks | archive-install.json; archive-install.log |
| Fresh Windows setup | Passed on a new source copy, including payment, estimate and audit smoke tests | clean-install.json; clean-install logs |
| Contract drift | OpenAPI, document schema and generated frontend contracts agree | contract-drift.json |
| Advisory scans | npm: 0 known vulnerabilities; Python: no known vulnerabilities found | npm-audit.log; python-audit.log |
| Initial JavaScript | 116708 bytes gzip; 49.8% below the 232480-byte baseline | asset-budget.json |
| Live free FX persistence | USD/BDT 123.27, observation date 2026-10-19; dated provider attribution stored; audit valid | live-fx-acceptance.json |

Advisory scans describe known published issues at execution time. Functional checks and automated accessibility scans do not establish production suitability or complete accessibility/security assurance.

## Financial and commercial acceptance

- Procurement authorization separately controls quantity and value. Amendment events retire eligible unreceived quantities and publish linked successor POs, preserving original documents and rates. Received, allocated, certified and settled scope stays protected.
- Whole-item and component forecast allocations bind supported quantities, disjoint intervals, conversions, source versions and explicit schedules. A genuine same-component overlap is rejected. Two disjoint contract sources retain their separate prices. Stale sources preserve the estimate requirement and demand review.
- Estimate and extended previews use the same service. A 20-tonne material contract at 74,000 plus untouched labour at 5,000 per tonne gives cost 1,580,000. Recoverable tax 148,000 and held retention 74,000 stay separate. Scheduled cash requirements total 1,654,000; unscheduled retention adds 74,000 to eventual cash. No release date is invented.
- Supplier certificate reversal of 10,000 restores accrual or supplier credit while original accepted base cost remains 70,000. A separately approved linked cost correction reduces that base cost to 60,000. Original quantities and settled cash stay unchanged.
- Supplier/customer tax, retention and advance reversals reconcile through compensating entries. Customer reversals never create negative receivables or automatic refunds; excess becomes customer credit.
- Invoice and certificate installment tests cover expiry, lost preparing/approving authority, competing credits, rollback, retention, retries and concurrent settlement. Permission changes through administration invalidate live affected proposals and release reservations.
- Original examples remain valid: 30,000 + 40,000 installments close at 930,000 from 1,000,000; retention 66,500 + 3,500 totals 70,000; EVM CV −50,000 / SV −100,000 / EAC 1,050,000; the 20-tonne estimating change adds 80,000 and changes the scheduled forecast from 600,000 to 520,000 without cash movement.
- New browser evidence covers composite forecasts, PO amendments, certificate reversals, sensitivity/maturity/history comparisons and read-error retry. Existing keyboard/mobile, draft guards, print content, independent approval and audit workflows still pass.

## Local workload measurement

Synthetic isolated SQLite dataset: 2,000 invoices, 500 estimates, 10,000 quotations and 50,000 valid chained audit events. Ten concurrent clients perform 250 reads and 50 draft writes in each run. All 900 requests succeeded.

| Run | Read median / p95 ms | Write median / p95 ms | Errors |
|---|---|---|---|
| 1 | 38.371 / 615.408 | 17.606 / 68.414 | 0 |
| 2 | 38.113 / 648.298 | 13.468 / 30.15 | 0 |
| 3 | 43.828 / 658.054 | 13.434 / 30.58 | 0 |

SQL measurements: median 0.285 ms, p95 5.909 ms, maximum 793.832 ms. 3 write-lock waits reached the 50 ms logging threshold; maximum 156 ms.

Investigation identifies broad audit searches as the slow group (audit SQL p95 635.627 ms). Contains-search counts scan matching project records; project/id indexes support paging but do not make leading-wildcard searches selective. No earlier comparable load baseline exists, so this is an initial measurement, not a regression or production-capacity claim. Indexes and the measured query shapes are recorded in the source and load evidence. Full-text indexing or a dedicated reporting store would need separate design if production search latency becomes a requirement.

## Artifact evidence

Presentation, video and archive checks have individual validation receipts. The video uses a newly seeded dedicated database and supplied local address; its recorder refuses the working app port and never calls reset. Video provenance includes actual decode/duration results and application source hashes. The release manifest binds packaged files, while the source checksum file identifies the final archive. The nine-slide presentation has speaker notes and inspected renders. The 272-second recording passed full playback decoding. The source archive passed checksum verification and an actual fresh Windows installation. Team identity, registration, rehearsal and competition upload await the user. The user has supplied and authorized the GitHub destination: https://github.com/md-ishtiak-ahmed-sajib/buildtrust-ai. The initial source publication is verified at commit `e3871e0383cfbb5f44e852e4631753a9441fe5d0` on the default branch `codex/verified-release`. Publication and hosted CI have separate receipts; Git history records subsequent documentation/package updates.
