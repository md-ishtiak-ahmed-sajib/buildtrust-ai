# Verification and release evidence

The app is a local sandbox. The public demo uses **http://127.0.0.1:8003** and the four README passwords. The private working profile uses port 8000 and its own generated credentials.

All links below refer to actual logs or receipts in [execution evidence](../submission/execution-evidence/README.md). [Remaining work](../prompt/Not%20implemented.md) lists unresolved prerequisites and human actions.

## Current local checks

| Check | Actual result | Evidence file |
|---|---|---|
| Backend suite | 203 passed; one existing Starlette/httpx deprecation warning | backend-tests.log |
| Frontend tests | 8 passed | frontend-tests.log |
| Production build | Passed | frontend-build.log |
| Browser workflows | 16 passed | browser-tests.log; screenshots |
| Public browser logins | Four README accounts passed real browser login/navigation | public-demo-browser.json |
| Public launcher | Fresh Windows setup, four logins, permissions, payment, repeat preparation and occupied-port checks passed | public-demo-install.json |
| Working profile preservation | 57 tables and 155 private files unchanged; credentials, secret and uploads preserved | public-demo-private-preservation.json |
| Private setup | Fresh setup, migrations, generated credentials, payment/estimate and audit checks passed | clean-install.json; clean-install.log |
| Original HTTP examples | A–H results and source fingerprint are recorded by the isolated collector | manifest.json; scenario-a through scenario-h.json |
| Contracts | Repeat generation agrees with OpenAPI/document/frontend types | contract-drift.json |
| Documentation | Render, links, images, mobile layouts, Mermaid diagrams and five SVG checks | documentation-check.json |
| Initial JavaScript | 116708 gzip bytes; 49.8% below the 232480-byte baseline | asset-budget.json |

Public tests cover published passwords, actual role denial, independent payment and clear refusal of unrelated/changed data. Private setup still generates random passwords. No new database migration is needed for this update.

The historical migration to head **0017** preserved 54 legacy table/column fingerprints, original credentials, receipts and audit history. The documentation/public-demo change checks working-profile preservation separately; it does not claim to rerun that earlier migration on the user's database.

## Financial examples

| Example | Verified expected behavior |
|---|---|
| Steel invoice | 95 tonnes claimed, 80 supported; BDT 1,050,000 excess and 18.75%; blocked |
| Valid payment | BDT 70,000; cash 1,000,000 to 930,000 once |
| Low cash | BDT 150,000 less 70,000 would breach the 100,000 reserve; blocked |
| Installments | 30,000 then 40,000; cash 970,000 then 930,000; one delivery claim |
| Retention | Net 66,500 plus separately approved 3,500 release totals 70,000 |
| Certificate reversal | A 10,000 financial reversal leaves accepted cost 70,000 until a separate supported cost correction reduces it to 60,000; no cash refund |
| EVM | BAC 1,000,000; PV 500,000; EV 400,000; AC 450,000; CV −50,000; SV −100,000; remaining-at-budget EAC 1,050,000 |
| Estimate change | 20 tonnes at 70,000 to 74,000 adds 80,000; forecast 600,000 to 520,000; recorded cash remains 2,000,000 |

Composite forecast tests keep unrelated components and apply allowances/tax once. Two disjoint supported scopes retain their rates; overlaps fail. One accepted example has cost 1,580,000, recoverable tax 148,000 and held retention 74,000. Scheduled cash is 1,654,000 plus unscheduled retention 74,000, for eventual cash requirements of 1,728,000. No release date is invented.

Amendments preserve original PO rates and cannot retire protected quantities. Supplier/customer corrections preserve source history, bound allocations and never create automatic refunds. Installment tests cover expiry, changed authority, concurrent credits, retries, rollback and settlement races.

## Earlier workload and live-service evidence

The earlier isolated workload used 2,000 invoices, 500 estimates, 10,000 quotations and 50,000 audit events. Ten concurrent clients made 250 reads and 50 writes in each of three runs. All 900 requests succeeded.

| Run | Read median / p95, ms | Write median / p95, ms | Errors |
|---|---|---|---|
| 1 | 38.371 / 615.408 | 17.606 / 68.414 | 0 |
| 2 | 38.113 / 648.298 | 13.468 / 30.150 | 0 |
| 3 | 43.828 / 658.054 | 13.434 / 30.580 | 0 |

SQL median was 0.285 ms, p95 5.909 ms and maximum 793.832 ms. Three writer waits reached the 50 ms logging threshold; maximum 156 ms. Broad audit text search was the slow group. There is no earlier comparable baseline, so these are not regression or production-capacity claims. See load-measurements.json.

A live free Frankfurter USD/BDT observation of **123.27**, dated **2026-10-19**, was stored with provider attribution and a valid audit result. That dated check is not a current bank quote. Paid providers and a real optional model still need their own acceptance. Known-advisory scans are dated checks, not complete security assurance.

## Artifacts, platforms and publication

The presentation has nine visually inspected slides, nine speaker-note parts and two editable tables, with structural validation. The final recording is **4 minutes 18 seconds**. It uses actual app interactions, a dedicated database and a disclosed local synthetic voice. Full decoding and application-source agreement passed. Archive manifests identify packaged files; archive-install receipts identify the exact tested archive. Read their individual current receipts instead of inferring acceptance from file existence.

The authorized repository is [md-ishtiak-ahmed-sajib/buildtrust-ai](https://github.com/md-ishtiak-ahmed-sajib/buildtrust-ai), default branch `codex/verified-release`. Remote/checkout and hosted-run receipts are revision-specific. Earlier revision `869c4e470d61430e46885d150e24dd6a127c9e92` passed the Windows and Ubuntu application workflow. The refreshed source must record its own run; the new workflow also checks native Linux shell startup and fresh Windows public/private setup.

Docker's engine is unavailable. Professional rule acceptance, representative Bengali documents, assistive-technology review, independent deployment security review and final team actions remain separate. No real payment, external audit immutability or professional certification is claimed.
