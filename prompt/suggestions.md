> Historical review. The findings below describe the app before the fixes. Read [current features](../features.md), [the 42-item ledger](../docs/all-suggestions-implementation.md) and [actual verification](../docs/completion-verification.md) for today's implementation and external review limits. The original reproductions are preserved as evidence.

# BuildTrust AI — Application Review and Improvement Roadmap

> **Current status:** the local fixes and feature work are recorded per recommendation in the ledger. Real provider, document, professional and independent assessment tasks remain separate. Use [Not implemented.md](Not%20implemented.md) for unfinished work rather than treating the old review below as the current backlog.

**Review date:** October 18, 2026 · **Application:** v0.2.0 · **Direction:** stabilize first, then expand.

This report implements the documentation deliverable from the approved review plan. It records source inspection, actual verification, reproduced problems, and proposed improvements. **The application fixes and new features below have not been implemented by writing this report.** They remain recommendations for subsequent approval. Submission artifacts and GitHub publishing are outside this documentation change.

Read this alongside the [remaining-work checklist](<Not implemented.md>), [advanced upgrade brief](<New prompt for upgrade.md>), [accepted upgrade architecture](../docs/advanced-upgrade-plan.md), and [known limitations](../docs/limitations.md). The checklist describes outstanding scope; this report additionally identifies defects in implemented behavior. Earlier statements that the competition core is complete do not mean the application has no defects or that the entire advanced brief is implemented.

Status labels used throughout:

- **Verified:** exercised successfully within the stated test or workflow scope.
- **Partially implemented:** useful behavior exists, with a specific missing capability or reproduced defect.
- **Not implemented:** the requested capability is absent from the current release.
- **Unverified integration:** implementation exists, but the relevant real service or environment has not been exercised.
- **Potential risk:** source inspection identifies a concern whose full runtime impact has not been demonstrated.

Priority and severity are separate. **P0** addresses financial integrity and authorization first; **P1** addresses major reliability and essential improvements; **P2** covers usability, maintainability, and subsequent capabilities; **P3** covers later commercial and operational extensions. Severity describes the consequence of an individual finding within this local sandbox.

Effort ranges are estimates for one engineer, including focused tests. They are not completion promises, are not automatically additive, and depend on the stated prerequisites. No full-upgrade delivery before the competition deadline is implied.

## 1. Application overview

BuildTrust AI is a construction-finance sandbox with two connected but independently authorized workflows:

1. Upload procurement and invoice documents → review and confirm trusted records → reconcile BOQ, PO, accepted receipt, and invoice → assess liquidity → prepare a proposal → obtain independent human approval → execute a simulated settlement → inspect receipt, ledger, and audit evidence.
2. Open an estimate BOQ component → search or import price evidence → compare technical compatibility and landed cost → select a supported rate → recalculate a versioned estimate → preview budget and scheduled cash effects → submit, independently check, and approve a separate estimate baseline.

The interface contains Overview, Documents, BOQ & Estimates, Quantity Takeoff, Materials & Prices, Invoice Intelligence, Cash-Flow Forecast, Payment Center, and Audit & Security. Operators prepare work; Finance Managers check evidence and have limited payment authority; Admins manage authorized controls and approve estimate baselines; Auditors read evidence.

The application uses React/TypeScript/Vite, TanStack Query, React Router, and Recharts with FastAPI, Pydantic, synchronous SQLAlchemy, Alembic, and SQLite. Authoritative financial calculations run on the backend with Decimal; monetary totals persist as integer minor units. Uploaded material remains untrusted until the required review or confirmation.

The intended near-term audience is a local demonstration team and competition judges. The existing Windows/offline path is valuable and should remain usable. There is no real bank connection, card charging, or transfer of real funds.

## 2. Existing feature inventory

| Area | Status | What exists and what the status means |
|---|---|---|
| Authentication and project access | **Verified**, with a reproduced throttling defect | Argon2, signed short-lived tokens, current database authority checks, memberships, and role enforcement exist. B04 concerns failure throttling rather than a demonstrated password-authentication bypass. |
| Document intake and provenance | **Verified** for documented layouts | Actual PDF/CSV/JSON content, private uploads, extraction revisions, reviewed corrections, authorized procurement publication, and protected previews exist. Arbitrary/scanned layouts still need manual review. |
| Invoice entitlement and deterministic findings | **Verified** within current scenarios | Four-way comparison, exact amounts, duplicate and beneficiary checks, accepted-quantity allocation, and blocking explanations are exercised. |
| Payment authorization and sandbox settlement | **Verified** within current scenarios | Independent proposal approval, role ceilings, exact snapshots, reservations, idempotency, atomic cash/ledger/receipt updates, and rollback checks exist. No real payment connectivity is claimed. |
| Payment cash-flow gate | **Verified** within current scenarios | The 30-day base and delayed-receivable gate remains authoritative; a cost-pressure scenario provides additional context. |
| Estimate forecast commitment coverage | **Partially implemented** | Scheduled uncommitted estimate overlays exist, but B02 demonstrates incorrect coverage when item codes match incompatible specifications. |
| Materials, price comparison, and supplier quotations | **Partially implemented** | Technical matching, conversions, unknown-cost handling, quotation verification, recommendation explanations, immutable selections, and imports exist. B03 affects normalization rounding; richer quotation extraction provenance is recommended in F01. |
| SerpApi and DataForSEO | **Unverified integration** for live use | Adapter protocol fixtures, truthful unavailable states, persisted remote task IDs, and recovery controls are exercised. No actual paid-provider search is claimed without configured credentials and a recorded live check. |
| FX | **Unverified integration** for the live provider | Estimate-only sourced conversion and the Frankfurter adapter exist. Live supported-pair retrieval has not been verified. |
| Takeoff | **Partially implemented** | Concrete geometry, rebar mass, selected formwork, and generic area/length/count calculations and checking exist. B06 affects displayed result freshness; remaining trade templates are absent. |
| Measurement standards | **Partially implemented** | Profiles retain edition context, assumptions, and review warnings. Full professional NRM/CESMM/PWD/LGED rules and clause compliance are not established. |
| Versioned estimates and rate analysis | **Partially implemented** | BOQ editing, build-ups, imports/exports, immutable evidence, checking, approval, and revision creation exist. B01, B05, B07, and B08 expose additional defects. |
| Audit and workflow history | **Verified**, within documented limits | Persisted stages, denied/successful actions, retained demo runs, and hash-chain verification exist. A privileged administrator can rewrite a local chain; it is not independently anchored immutability. |
| Deterministic copilot | **Verified** for implemented tools | Stored-evidence explanations, basic sensitivity, geometry, and forecast tools exist. Future-module answers require future tools; the copilot has no approval authority. |
| Actual-cost/accrual, EVM, certificates, RFQs, complete commercial variations | **Not implemented** | These require additional records and workflows; current estimates and cash payments do not substitute for incurred costs. |
| OCR, full supplier-master maintenance, partial payments | **Not implemented** | Existing manual review and complete-invoice sandbox settlement remain the supported paths. |
| Delivery environments and submission | Mixed | Windows setup/migration/recovery was verified earlier. Docker, Linux, and live Ollama remain unverified. Existing submission artifacts describe the earlier release and were intentionally preserved. |

### Actual verification and evidence

The following checks ran during the application review preceding this report. They were not rerun merely to write a Markdown file.

| Check | Actual review result | Evidence and qualification |
|---|---|---|
| Complete backend suite | **95 passed**, one Starlette test-client deprecation warning, **63.04 seconds** | Actual command output in the review conversation. The earlier upgrade report records a separate 60.72-second run; these are different executions. |
| Frontend unit tests | **8 passed**, across two files | Actual Vitest output. These tests primarily cover helpers and request behavior; they are not eight comprehensive screen tests. |
| Production build | **Passed** | Actual TypeScript/Vite output; JavaScript **796.61 kB raw / 232.48 kB gzip**, CSS **42.54 kB raw / 10.38 kB gzip**. These are asset sizes, not a page-load benchmark. |
| Isolated browser flows | **4 passed**, **11.6 seconds** | [Browser log](../data/advanced-browser-c4e5807d/browser-tests.log) and screenshots in that isolated runtime. Covers the upgrade journey, mobile takeoff, original payment/receipt/audit, and document upload. |
| Original HTTP scenarios A–H | **All eight passed** | [Review HTTP manifest](../data/review-evidence-20261018/manifest.json), scenario records, and operation log in the same directory. |
| npm dependency audit | **Zero known advisories reported** | Actual audit result: info 0, low 0, moderate 0, high 0, critical 0. |
| Python dependency audit | **No known vulnerabilities reported** | Actual pip-audit output for the installed backend environment. |
| Additional API/math probes | Reproduced B01–B05 and B09 | Executed against temporary seeded databases; concise results are included in Section 4. The final probe run exited successfully. |
| Additional Chromium probes | Reproduced B06–B08 | Isolated runtime [review-ui-fO7erS](../data/review-ui-fO7erS/); includes an actual stale-takeoff screenshot. No user workspace database was used. |

The review commands were:

```powershell
uv run --project backend pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run build
uv run --project backend python scripts/verify_upgrade_browser.py
uv run --project backend python scripts/collect_evidence.py --port 8013 --output data/review-evidence-20261018
npm --prefix frontend audit --json
uvx pip-audit --path backend/.venv/Lib/site-packages --format json
```

The additional reproductions were inline Python and Node/Playwright probes, not committed regression tests. Their observed outputs are preserved below; reusable regression tests still need to be added when implementing fixes. Local `data/` evidence is intentionally ignored by Git and contains private runtime state. Do not publish a whole runtime directory or its credentials/signing secret. Include reviewed, redacted results when a distributable evidence package is separately requested.

Prior populated-database migration/recovery and clean Windows installation results are documented in [advanced-feature-tests.md](../docs/advanced-feature-tests.md). They were inspected, not newly repeated in this documentation step.

## 3. Overall technical assessment

| Dimension | Assessment | Recommended direction |
|---|---|---|
| Architecture | Appropriate stack for a local sandbox; payment and estimating authority are meaningfully separated. Some API/page modules now concentrate many responsibilities. | Keep the stack and incrementally separate feature boundaries. Do not introduce microservices or replace SQLite without demonstrated operational requirements. |
| Financial correctness | Exact arithmetic, integer money, approval snapshots, atomic settlement, and original scenarios are strengths. Forecast coverage and rate-rounding defects need correction. | Address B02/B03 before adding more financial indicators. Preserve approved historical evidence. |
| Authorization | Backend role and project controls are established. The estimate independence model loses contributor history. | Address B01 and investigate analogous multi-editor approvals. |
| Reliability | Core tests and browser journeys pass. Malformed import handling, unsaved changes, result freshness, and print behavior have gaps. | Convert each reproduction into a regression test, then fix the behavior. |
| Frontend/data integration | Main areas call real endpoints. Some manually maintained response types, broad dictionaries, and inconsistent error helpers make integration harder to maintain. | Strengthen typed contracts and shared client behavior without breaking existing consumers. |
| UX/accessibility | Visual identity is consistent, responsive layouts exist, and dialogs include keyboard handling. Long forms, small secondary text, and incomplete workflow guidance need further review. | Preserve the identity; improve task clarity, mobile usability, result freshness, and accessible data access. |
| Security | Password hashing, memory-only browser tokens, private files, current authority checks, and source URL restrictions are useful controls. Limits at request ingestion and numeric canonicalization warrant attention. | Fix demonstrated weaknesses and test remaining risks. No penetration-test or security-certification claim is justified. |
| Performance/scalability | The bundle size was measured; load latency, lock contention, parser resource use, and large datasets were not benchmarked. | Establish measurements, shorten write locks, lazy-load, and paginate before assuming a database replacement is necessary. |
| Delivery/maintenance | Locks, migrations, Windows scripts, and isolation helpers exist. There is no established CI workflow in the inspected repository, and release tooling retains earlier-release assumptions. | Add reproducible CI, safer default test outputs, and explicit release validation when submission updates are requested. |

Inspected module sizes illustrate concentration rather than proving defects: backend `main.py` is approximately 987 lines, `advanced_api.py` 1,523; frontend `pages.tsx` 1,730, `Prices.tsx` 1,363, and `Estimates.tsx` 1,091. Refactor around coherent workflows and transaction boundaries, not arbitrary line-count targets.

## 4. Confirmed bugs and issues

### B01 — Earlier estimate contributors can approve their work

**Status:** confirmed · **Priority:** P0 · **Severity:** High · **Effort:** 2–3 days · **Implementation risk:** High, because approval history and migrations are involved.

**Reproduction:** In an isolated fictional upgrade project, an Admin changed the steel component rate to BDT 76,000. An Operator then changed the Basis of Estimate narrative and saved. Operator submission, Finance Manager checking, and approval by that same Admin all returned HTTP 200. The final status was `APPROVED`, total `1520000.00`.

**Root cause:** Content mutations replace `prepared_by` with the latest editor. Independence checks compare the checker/approver against that single account, so earlier contributors disappear from the authority decision.

**Sources:** [estimate mutation](../backend/app/advanced_api.py#L833), [price-selection mutation](../backend/app/advanced_api.py#L983), [BOQ import mutation](../backend/app/advanced_api.py#L1231), and [estimate transition checks](../backend/app/estimating.py#L230).

**Impact:** A person who helped prepare the retained estimate contents can be presented as an independent approving authority. This reproduction concerns estimate/budget approval; it does not demonstrate bypass of payment settlement controls.

**Proposed solution:** Persist contributor identities for each estimate revision and its retained content. Record preparation, import, price selection, and other content-changing actions. Prevent contributors from checking or approving that revision; require a different checker and approver. Include contributor evidence in the submitted snapshot. Creating a revision or handing the file to another editor must not simply erase authorship of retained work. Explain blocked authority in the UI.

Backfill contributor information from relevant audit events where reconstruction is reliable. Require fresh review for unresolved pending submissions. Preserve approved historical snapshots and baseline amounts; do not silently rewrite prior approvals to make a migration pass.

**Acceptance:** Reproduce the exact multi-editor sequence and deny the earlier contributor; verify no baseline is created by the denied approval. Test ordinary Operator → Manager → Admin approval, revision inheritance, changed account authority, and migration of populated records. Retain an audit record of denied actions.

### B02 — Incompatible PO items suppress estimated forecast costs

**Status:** confirmed · **Priority:** P0 · **Severity:** High · **Effort:** 2–3 days · **Implementation risk:** High, because coverage changes affect forecasts and need migration/reconciliation.

**Reproduction:** Import an existing approved BOQ into an estimate. In the isolated fixture, change a confirmed cement PO line description to an incompatible specification while retaining its item code and quantity. The forecast endpoint still returned HTTP 200 with `unscheduled_estimated_cost: "0.00"` and no warnings. At least BDT 70,000 should have remained uncovered by that incompatible commitment.

This probe used a direct fixture mutation to represent inconsistent confirmed evidence; it did not demonstrate an unauthorized production edit through the UI.

**Root cause:** Commitment coverage sums approved PO quantities using item code alone, without sufficient specification/currency identity or an explicit coverage relationship.

**Source:** [committed_quantity](../backend/app/estimating.py#L381).

**Impact:** The estimate can understate additional uncommitted costs and overstate projected liquidity. Payment entitlement remains a separate control and must stay separate.

**Proposed solution:** Persist explicit BOQ-to-PO-line coverage links. Auto-link only unambiguous project, specification, compatible-unit, and currency matches; expose unresolved mappings for authorized review. Bound coverage quantities and prevent a commitment from offsetting the same requirement twice. Keep existing contractual rates and settled cash unchanged. Display unresolved coverage and its conservative financial effect rather than treating a matching code as sufficient.

**Acceptance:** The incompatible-specification reproduction leaves at least BDT 70,000 visible. Test compatible kg/tonne coverage, wrong currency, duplicate links, partial coverage, multiple POs, and changed source versions. Recheck the original BDT 80,000 upgrade example and ensure covered commitments are not repriced.

### B03 — Inconsistent rounding in normalized and landed rates

**Status:** confirmed · **Priority:** P0 · **Severity:** Medium · **Effort:** 0.5–1 day · **Implementation risk:** Medium, because corrected rounding can change new calculations.

**Reproduction:** A human-verified fixture quotation with rate `1.2345665` produced eligible landed cost `1.234566`. Explicit `ROUND_HALF_UP` to six decimals produces `1.234567`.

**Root cause:** Fixed-point formatting uses the active Decimal context's rounding rather than the explicitly required policy. Rate analysis already explicitly quantizes some values, so policies differ across stages.

**Sources:** [normalized price](../backend/app/pricing.py#L281), [landed rate](../backend/app/pricing.py#L332), and [rate analysis](../backend/app/advanced_math.py#L160).

**Impact:** A selected rate can differ from the documented financial policy and propagate into estimate amounts. The fixture is not a claimed live market price.

**Proposed solution:** Centralize explicit rate, money, and published-quantity rounding. Keep intermediate calculations exact; quantize authoritative published rates to six decimals and monetary totals to two using `ROUND_HALF_UP`. Define the calculation-policy version and preserve historical approved snapshots instead of recalculating them in place.

**Acceptance:** Test ties and nearby non-ties in normalization, landed cost, FX, takeoff output, selection snapshots, and estimate totals. Verify the selected persisted rate, displayed preview, approved evidence, and export agree.

### B04 — Whitespace bypasses the login failure throttle

**Status:** confirmed · **Priority:** P1 · **Severity:** Medium · **Effort:** 1 day · **Implementation risk:** Low–Medium, because shared-IP users can be affected by poorly chosen limits.

**Reproduction:** Eleven failed sign-ins for the same fixture email reached HTTP 429. A request for that same email with trailing whitespace returned HTTP 401 rather than sharing the existing throttle.

**Root cause:** The failure-counter key lowercases the raw email, while account lookup strips whitespace and lowercases it. Different strings identify the same account but different counters.

**Source:** [login counter and lookup](../backend/app/main.py#L354).

**Impact:** Attackers can bypass the intended failure limit through equivalent account spellings. No successful password bypass was demonstrated.

**Proposed solution:** Normalize once and reuse the canonical identifier for lookup, throttling, and relevant audit metadata. Use expiring, bounded account and IP failure buckets; retain generic errors and return `Retry-After` for throttled requests. Keep account-based protection effective across source addresses. Reference: [OWASP login throttling](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#login-throttling).

**Acceptance:** Case and whitespace variants share an account bucket; expired buckets recover; many account names cannot grow storage without bounds; legitimate successful sign-ins work; error responses do not reveal account existence.

### B05 — Missing BOQ CSV headers return an unhandled 500

**Status:** confirmed · **Priority:** P1 · **Severity:** Medium · **Effort:** 0.5–1 day · **Implementation risk:** Low.

**Reproduction:** Import this CSV into a draft estimate with its current expected version:

```csv
description,unit,quantity,unit_rate
A,tonne,20,70000
```

Observed response: HTTP `500`, body `Internal Server Error`.

**Root cause:** The importer accesses required dictionary keys such as `row["code"]` without first validating the complete header schema. The surrounding table-reader exception handling does not cover this later access.

**Source:** [BOQ import](../backend/app/advanced_imports.py#L159).

**Impact:** Ordinary user mistakes become server errors, provide no actionable correction, and make the feature appear unreliable.

**Proposed solution:** Validate required and duplicate headers before row processing; bound iteration to the supported row count before materializing a large table. Return a structured 422 identifying columns and cells. Reject the complete import without changing the draft, version, selections, or approval evidence. Share schema errors with the frontend's field-error presentation.

**Acceptance:** Missing/duplicate headers, invalid rows, unsupported units, malformed files, formula cells, and excess rows return actionable failures with no partial import. Valid CSV/XLSX exports still import under the documented round-trip limitations.

### B06 — Displayed takeoff results become stale after input changes

**Status:** confirmed · **Priority:** P1 · **Severity:** Medium · **Effort:** 0.5–1 day · **Implementation risk:** Low.

**Reproduction:** Calculate rectangular volume using 0.4 × 0.4 × 3 × 20 and observe `9.600000 m3`. Change length to 0.8. The displayed result remains `9.600000 m3`; recalculation should produce `19.200000 m3`. [Actual screenshot](../data/review-ui-fO7erS/stale-takeoff-result.png).

**Root cause:** Result state resets on selected changes such as project/calculation kind, but not on every input that affects the calculation or evidence. The displayed result is not visibly bound to its input snapshot.

**Source:** [takeoff form state and changes](../frontend/src/advanced/Takeoff.tsx#L108).

**Impact:** Users can read a previous result as though it describes the current dimensions. This probe establishes a display problem; the save endpoint independently recalculates and was not shown to persist the stale displayed number.

**Proposed solution:** Bind each displayed result to the full calculation/evidence inputs. Clear it or visibly mark it stale after relevant changes, including dimensions, units, deductions, mass method, profile, drawing, and revision. Do not present a stale result as current or reusable.

**Acceptance:** Each relevant input invalidates the result; recalculation shows 19.200000 m3 for the changed example; saved/retrieved quantities and checking evidence agree with the new inputs. Cover mobile use and calculation failures.

### B07 — Navigation silently discards unsaved estimate changes

**Status:** confirmed · **Priority:** P1 · **Severity:** Medium · **Effort:** 1–2 days · **Implementation risk:** Medium, because guards interact with navigation and asynchronous saves.

**Reproduction:** Change the estimate name to `UNSAVED REVIEW TEXT`, navigate to Quantity Takeoff, then return. The original name reappears and no confirmation was shown.

**Root cause:** Draft state is local to the estimate screen. Route changes unmount it; estimate/version changes replace state without a shared decision about unsaved work.

**Source:** [estimate draft state and selection](../frontend/src/advanced/Estimates.tsx#L79).

**Impact:** Preparers lose work and may assume changes were persisted when they were not.

**Proposed solution:** Add a shared Save / Discard / Stay guard for route, project, and estimate-version changes, with browser-unload protection. Continue only after a successful save; preserve the draft on errors or version conflicts. Use the existing accessible dialog style. Cover browser back/forward as well as sidebar links.

**Acceptance:** Exercise all three choices, failed saves, 409 conflicts, project/version changes, and back/forward navigation. Verify clean or read-only screens do not show unnecessary prompts.

### B08 — Estimate print styles hide the BOQ

**Status:** confirmed · **Priority:** P1 · **Severity:** Medium · **Effort:** 0.5–1 day · **Implementation risk:** Low–Medium, because receipt printing shares styles.

**Reproduction:** Open an estimate and emulate Chromium print media. Observed `main_display: "none"` and `estimate_table_visible: false`.

**Root cause:** A later receipt-oriented print rule hides `main`, overriding the earlier estimate print styling. The Print estimate button invokes printing without a separate content scope.

**Sources:** [earlier estimate rules](../frontend/src/index.css#L539), [later print rules](../frontend/src/index.css#L2706), and [print action](../frontend/src/advanced/Estimates.tsx#L392).

**Impact:** A visible export action cannot produce the intended estimate content.

**Proposed solution:** Separate estimate and receipt print scopes. Include project, revision, status, BOQ lines, totals, and assumptions; hide navigation/actions; support sensible page breaks and readable headers. Preserve the existing receipt output.

**Acceptance:** Generate an actual browser print/PDF test artifact and verify its text includes the project, BOQ code, revision, and expected total. Repeat for a receipt and a multi-page estimate. Do not rely solely on a CSS-selector assertion.

### B09 — Small decimal inputs can expand into large canonical strings

**Status:** confirmed expansion; **potential risk** of resource exhaustion · **Priority:** P1 · **Severity:** Medium risk · **Effort:** 1 day · **Implementation risk:** Medium, because limits must preserve legitimate financial precision.

**Reproduction:** Formatting the accepted decimal input `1e-20000` into fixed-point form produced **20,002 characters**. No large exhaustion attempt was performed.

**Root cause:** Validation bounds numeric magnitude but does not sufficiently bound raw length, coefficient digits, exponent, or expanded representation before fixed-point canonicalization.

**Sources:** [decimal parser](../backend/app/money.py#L9) and [Exact input conversion](../backend/app/advanced_schemas.py#L15).

**Impact:** Request validation can amplify compact untrusted input into substantially larger allocations. The full service-level impact is unmeasured.

**Proposed solution:** Document and enforce bounded raw numeric representations before fixed-point expansion; reject pathological inputs with 422. Keep ingress validation separate from valid intermediate Decimal calculations and retain the existing magnitude, finite-number, and no-binary-float policies. Check related table, query, and document input paths.

**Acceptance:** Reject excessive exponents/digits quickly without expanding them; accept documented boundary values; preserve high-precision calculations and explicit rounding; return structured errors rather than 500 responses. Use bounded tests, not a destructive exhaustion exercise.

### Follow-up investigations — not yet confirmed as equivalent defects

- **Contributor history in quotations and technical equivalence:** inspect multi-editor sequences and retained source authorship. The estimate reproduction does not establish identical behavior for these paths. Add explicit probes and regressions before labeling them confirmed.
- **Request ingestion and parser limits:** check whether large multipart bodies are bounded before spooling/parsing and whether CSV limits apply before allocation. Existing content limits do not prove full ingestion bounds.
- **Write-lock contention and event-loop responsiveness:** hashing/parsing inside write contexts and synchronous work in async endpoints warrant measurement. No latency or throughput regression was measured in this review.
- **Background permission changes and retry races:** test role changes, duplicate workers, restart leases, and repeated retrieval against persisted task states. Preserve the prohibition on blindly repeating an uncertain paid submission.

## 5. Major feature recommendations

These extend existing workflows rather than replacing features that already work. Each feature needs its own bounded implementation and acceptance gate.

### F01 — Quotation evidence and a role-aware review inbox

**Priority:** P1 · **Complexity:** Medium · **Effort:** 4–7 days · **Dependencies:** B01, reliable typed errors/contracts.

- **Problem and benefit:** Preparers need a traceable path from an indicative listing or extracted quotation to independently reviewed evidence, while reviewers need a clear queue of work they can act on.
- **Frontend:** show retained page/row evidence, correction history, missing fields, source observation, and verification state; add a listing-to-quotation draft action and an inbox linking to existing approval screens.
- **Backend/data/API:** persist quotation extraction revisions and field provenance linked to original attachment hashes and source observations. Add quotation-evidence reads and project/role-scoped work-item queries over authoritative quotation, measurement, estimate, and payment states. Avoid a second competing workflow state machine.
- **Integration:** continue to treat listing costs and delivery as unknown until evidenced; independent verification creates immutable observations consumed by the existing comparison and selection flow.
- **Risk:** Medium; provenance loss or duplicate authority must be avoided. Notifications stay in-app unless external messaging is separately authorized.
- **Acceptance:** original source and extraction history remain retrievable after correction, verification, and refresh; inbox actions respect role, project, self-approval, and expiry rules.

### F02 — Actual-cost, accrual, and integrated cost-coding foundation

**Priority:** P1 · **Complexity:** High · **Effort:** 10–15 days · **Dependencies:** B02, agreed accounting definitions and source records.

- **Problem and benefit:** Estimate values and cash paid cannot answer what work has been incurred, remains payable, or is still committed. A cost-control foundation makes forecasts and later profitability meaningful.
- **Frontend:** add cost-code drilldowns, incurred/committed/paid views, unreconciled items, evidence links, and dated reconciliation reports.
- **Backend/data/API:** add relational cost codes, cost/accrual entries, commitment coverage, and receipt/invoice/payment associations. Extend finance summaries with defined bases and source references; reconcile rather than add the same obligation at every stage.
- **Integration:** reuse existing procurement, receipts, invoices, payments, and approved budget baselines. Do not infer incurred costs from a payment alone or rewrite settled entries.
- **Risk:** High; recognition rules, tax/retention treatment, and duplicate recognition require explicit policy and review.
- **Acceptance:** independently specified examples distinguish estimate, commitment, incurred cost, liability, and cash; receipts/invoices/payments reconcile without double counting; unknown measures stay unavailable.

### F03 — Extended forecasting and earned value management

**Priority:** P2 · **Complexity:** High · **Effort:** 10–15 days · **Dependencies:** F02, approved time-phased baselines and measured progress.

- **Problem and benefit:** Thirty-day cash alone does not explain project-duration cost performance or future funding needs.
- **Frontend:** add 7/30/90-day and project-duration views, progress evidence, EVM indicators, forecast-method explanations, and scenario comparisons.
- **Backend/data/API:** introduce dated baseline/progress observations, EVM calculations and snapshots, additional schedule categories, and extended forecast interfaces. Calculate PV/EV/AC, BAC/CV/SV/CPI/SPI/EAC/ETC/VAC from the recorded basis and handle unavailable data/zero denominators.
- **Integration:** preserve the existing 30-day payment gate. Estimate and forecasting scenarios remain advisory and cannot authorize settlement.
- **Risk:** High; unsupported progress assumptions or mixing cash with actual cost would produce misleading indicators.
- **Acceptance:** independent numerical fixtures cover documented EAC methods, delays, supplier acceleration, payroll/equipment/loan/tax/retention schedules, combined stress, and missing-data cases.

### F04 — Additional trade takeoff and professionally reviewed measurement rules

**Priority:** P2 · **Complexity:** High · **Effort:** 8–15 days, plus external review time · **Dependencies:** B06, authorized standards/reference material.

- **Problem and benefit:** Current geometry is useful but cannot support complete trade measurement or establish standards compliance.
- **Frontend:** add earthworks, masonry/openings, finishes, complex geometry, and supplied reinforcement-schedule templates; show drawings, editions, deductions, assumptions, and checker evidence.
- **Backend/data/API:** add versioned calculation/rule profiles, input/output contracts, drawing references, reviewed rule metadata, and saved calculation revisions. Extend existing measurement endpoints and BOQ links.
- **Integration:** calculations supply independently checked quantities to estimates; they do not infer structural adequacy, laps, anchorage, or unrecorded engineering decisions.
- **Risk:** High; standards interpretation, rights to reference material, and engineering review are dependencies, not assumptions to invent.
- **Acceptance:** independently worked examples cover deductions, units, drawing revisions, profile versions, review state, and the effect of changed measurements on submitted estimates.

### F05 — Full sensitivity analysis and evidence-based estimate maturity

**Priority:** P2 · **Complexity:** Medium · **Effort:** 5–8 days · **Dependencies:** B03, F02/F03 for accounting and cash effects.

- **Problem and benefit:** Preparers need transparent uncertainty comparisons beyond the existing basic material-percentage copilot tool.
- **Frontend:** add controls for material, labour, fuel/transport, FX, waste, and procurement delays; show estimate, contingency, margin, and cash differences and an evidence-based maturity checklist.
- **Backend/data/API:** save immutable scenario inputs/results, calculation-policy versions, comparison interfaces, historical references, and maturity evidence. Extend existing estimate and forecast services.
- **Integration:** scenarios never overwrite an approved baseline. Describe AACE maturity from actual supporting evidence; do not assign a class merely from the estimate label.
- **Risk:** Medium; arbitrary percentages must be labeled assumptions rather than market predictions.
- **Acceptance:** fixed scenario inputs reproduce exact deltas; committed rates stay unchanged; missing margin/cost evidence remains unavailable; scenario changes require new snapshots.

### F06 — RFQs, procurement integration, certificates, and complete variations

**Priority:** P3 · **Complexity:** High · **Effort:** 15–25 days · **Dependencies:** F02, contracts, cost codes, authority and source rules.

- **Problem and benefit:** Existing quote comparison and quantity-only variations do not provide the complete commercial cycle needed for contract administration.
- **Frontend:** add RFQ registers, bid comparison, recommendations, PO linkage, certificate workbooks, and variation value/time review.
- **Backend/data/API:** add RFQ/bid records, contract/certificate versions, cumulative and previous/current certified work, advance recovery, retention/tax, and reviewed/approved variation quantities, rates, values, and time impacts. Add authenticated RFQ, certificate, and variation interfaces with explicit transitions.
- **Integration:** approved commercial records feed commitments and payable/receivable schedules through separately authorized procurement controls. They do not silently amend old POs, supplier beneficiaries, or payment approvals.
- **Risk:** High; cumulative certification, reversals, contract terms, and separation of duties need dedicated reconciliation tests.
- **Acceptance:** certificates reconcile previous/current/cumulative values; variation approval updates only authorized effects; bid selection cannot create an unauthorized order or payment; no emails are sent without authorization.

### F07 — Profitability, aging, ratios, and reporting currencies

**Priority:** P3 · **Complexity:** High · **Effort:** 7–12 days · **Dependencies:** F02/F03 and evidenced receivable/payable data.

- **Problem and benefit:** Managers need project margin and working-capital views derived from accounting data, not estimates disguised as achieved results.
- **Frontend:** add gross/forecast margin, AR/AP aging, retention outstanding, working capital, supported DSO/DPO/cash-cycle indicators, and reporting-currency views.
- **Backend/data/API:** extend receivable/payable schedules, dated reporting conversions, policy/source snapshots, and finance reporting endpoints. Clearly define each numerator, denominator, date, and missing-data state.
- **Integration:** reuse sourced FX and existing budget/payment evidence. Reporting conversion does not enable cross-currency settlement.
- **Risk:** High; wrong cost recognition, dates, or FX bases can misstate results.
- **Acceptance:** known fixtures reconcile ratios and currency presentations; absent data does not become zero; historical reports retain their dated conversion evidence.

### F08 — Reviewed OCR for scanned documents

**Priority:** P3 · **Complexity:** High · **Effort:** 5–15 days · **Dependencies:** bounded parser operation, F01 provenance.

- **Problem and benefit:** Scanned PDFs currently require manual entry; optional OCR can reduce preparation effort without granting document text authority.
- **Frontend:** show page evidence, uncertain fields, explicit correction, and independent confirmation state.
- **Backend/data/API:** add an optional bounded OCR worker and extraction revisions, source hashes, method/model versions, and confidence only where available. Reuse existing upload/review interfaces.
- **Risk:** High; resource use, language/layout accuracy, and dependency packaging need measurement. Offline startup must still work without OCR.
- **Acceptance:** actual scanned fixtures produce reviewable suggestions, low-quality cases remain held, malicious instructions remain untrusted, and timeout/unavailable-engine paths preserve manual entry.

### F09 — Supplier onboarding and controlled master maintenance

**Priority:** P3 · **Complexity:** High · **Effort:** 5–15 days · **Dependencies:** contributor-aware approvals, supplier identity/verification policy.

- **Problem and benefit:** A blocked beneficiary mismatch currently lacks a full authorized master-maintenance workflow.
- **Frontend:** add supplier drafts, evidence, change comparison, independent verification, and effective versions.
- **Backend/data/API:** introduce supplier-change requests, evidence and reviewer records, versioned master updates, and project-scoped supplier administration APIs.
- **Integration:** supplier changes invalidate affected pending payment snapshots and require fresh validation. Invoice text never edits master beneficiary authority.
- **Risk:** High; fraud exposure and mistaken identity make separation of duties essential.
- **Acceptance:** self-verification is denied, invoice instructions cannot change the master, old receipts remain immutable, and affected proposals require fresh approval.

### F10 — Partial payments, credit notes, and retention release

**Priority:** P3 · **Complexity:** High · **Effort:** 5–15 days · **Dependencies:** F02, explicit allocation/reversal policies, payment-security regressions.

- **Problem and benefit:** Complete-invoice settlement cannot represent staged payment and later adjustments.
- **Frontend:** show paid/unpaid/retained amounts, allocation history, credit-note evidence, and separately approved releases.
- **Backend/data/API:** add payment allocations, invoice adjustments, remaining-payable constraints, and authorized credit/release transitions. Evolve payment contracts deliberately; the current one-settlement-per-invoice constraint cannot simply be removed.
- **Integration:** preserve atomic reservation, receipt allocation, ledger, cash, audit, and idempotency semantics for every installment or adjustment.
- **Risk:** High; overpayment, reused entitlement, and incorrect reversals are material risks.
- **Acceptance:** installments and credits reconcile to permitted payable amounts under concurrency; retries never deduct twice; retention cannot be released without authority; historical receipts remain auditable.

### F11 — Extend the copilot with each delivered module

**Priority:** follows the underlying feature · **Complexity/effort:** include in that module's gate · **Dependencies:** verified deterministic services and available evidence.

Expose new accounting, EVM, certificate, procurement, and profitability tools only after their services pass acceptance. Add typed tool inputs/outputs, evidence references, uncertainty explanations, and UI links to source records. The assistant may prepare drafts but cannot check, approve, or execute authorized financial actions. Test unsupported questions, missing evidence, and optional provider failure. No additional LLM is required for these financial capabilities.

## 6. Minor improvements and quick wins

These complement the defect fixes; they do not replace them.

| ID | Suggestion and user benefit | Priority / effort | Dependency and risk | Acceptance |
|---|---|---|---|---|
| Q01 | Show role-specific next steps and why an approval/action is unavailable. Reduces confusion about preparation versus checking and approval. | P2 / 1–2 days | Correct B01 authority; Low risk | UI explains self-approval, wrong role, missing evidence, and expiry without suggesting a bypass. |
| Q02 | Display last-searched material, quantity, unit, destination, mode, and timestamp next to price results. | P2 / 0.5–1 day | Existing persisted searches; Low risk | Changing form inputs cannot make old results appear to describe a new search. |
| Q03 | Add searchable project/material/version selectors and preserve useful filters. | P2 / 1–2 days | Project scope; Low risk | Keyboard selection works and state cannot leak another project's records. |
| Q04 | Improve inline validation, field-error summaries, and empty/loading/retry states. | P2 / 1–2 days | A03 typed errors; Low risk | A malformed import or quote explains exactly what the user can correct. |
| Q05 | Improve secondary text readability, touch targets, form grouping, and mobile review of long sheets. | P2 / 1–2 days | Accessibility review; Low risk | Recheck desktop/mobile screenshots and keyboard access at representative widths. |
| Q06 | Add accessible table alternatives and meaningful summaries for financial charts. | P2 / 1–2 days | Existing backend figures; Low risk | Nonvisual access exposes the same dates, balances, scenario names, and reserve information. |
| Q07 | Add authorized read-only navigation to archived demo runs. | P2 / 1–2 days | Existing retained memberships/history; Low–Medium risk | Archived evidence is discoverable; all attempted writes remain denied. |
| Q08 | Improve export context: project, revision, state, currency, calculation basis, and clear CSV/XLSX round-trip limits. | P2 / 1–2 days | B08 print fix and existing export contracts; Low risk | Exported totals reconcile with the server and evidence; formula-escaping tests stay valid. |
| Q09 | Show actionable in-app review/expiry notifications without duplicating authoritative workflow state. | P2 / 1–2 days after F01 | Work-item reads; Medium risk | Messages disappear or update when the underlying record changes; no unauthorized external messages. |
| Q10 | Add a short first-run guide covering locally generated credentials, demo roles, upgrade-project creation, and source categories. | P2 / 0.5–1 day | Existing setup flow; Low risk | A new user can find the credential file and reach the right role/project without publishing credentials. |
| Q11 | Share form, state, status, evidence, and error components where behavior is genuinely repeated. | P2 / 1–2 days incrementally | A01; Medium regression risk | Existing workflows and focus behavior remain intact; avoid abstraction that hides authority differences. |
| Q12 | Reconcile README command descriptions and stale release-tool assumptions. The current release packager expects older counts/version and omits the prompt directory from its explicit directory list. | P2 / 0.5–1 day for documentation; release work separately gated | [README](../README.md), [packager](../scripts/package_release.py); Medium delivery risk | Documentation matches actual command output locations. Updating/rebuilding submission artifacts still requires separate instruction. |

## 7. Security, performance, and architecture recommendations

### A01 — Incremental feature boundaries

**Priority:** P1 · **Effort:** 3–5 days · **Risk:** Medium · **Benefit:** safer maintenance and smaller review surfaces.

Split the main API and upgrade router into document, payment, pricing, measurement, estimate, and finance boundaries. Separate large frontend pages by workflow and move pure helpers out of components. Preserve `models.py` and the shared Base, existing API URLs, authority checks, and atomic settlement boundaries. Additive refactoring should not reimplement working financial rules.

### A02 — Short SQLite write transactions

**Priority:** P1 · **Effort:** 2–4 days · **Risk:** High if revalidation is omitted · **Benefit:** less interference between uploads, sign-in, and financial writes.

Perform hashing, parsing, and external calls outside write locks. Reauthenticate/recheck current role, project access, relevant source versions, and conflicts immediately before committing. Avoid turning a shorter transaction into a time-of-check/time-of-use authority gap. Keep settlement, cash, ledger, allocations, and success audit events in one write transaction.

SQLite permits only one simultaneous write transaction; quantify lock duration and busy responses before and after changes. [SQLite transaction documentation](https://www.sqlite.org/lang_transaction.html).

### A03 — Typed API errors and complete contracts

**Priority:** P1 · **Effort:** 2–3 days · **Risk:** Medium · **Benefit:** clearer failures and fewer frontend/backend mismatches.

Introduce a shared frontend API error carrying HTTP status, domain code, field errors, and retry information. Route downloads/previews through consistent session-expiry handling. Add explicit Pydantic responses for currently broad material/quotation/finance payloads, generate TypeScript types from OpenAPI, and add contract checks. Preserve existing consumers and the established error envelope when extending fields.

Sources include the separate helpers in [api.ts](../frontend/src/api.ts) and response definitions in [advanced_schemas.py](../backend/app/advanced_schemas.py).

### A04 — Persisted job attempts and recovery

**Priority:** P1 · **Effort:** 3–5 days · **Risk:** High for paid-task duplication · **Benefit:** predictable recovery and supportability.

Extend the current persisted workflow/search state with attempts, leases, bounded retry counts, next-attempt times, and failure details. Recheck current authority when work actually starts and before publishing results. Test duplicate workers and restart recovery. Resume known remote IDs; keep uncertain submissions held for manual provider reconciliation. Use the existing stack for the local release rather than adding a distributed queue without demonstrated need.

### A05 — Operational diagnostics and redaction

**Priority:** P1 · **Effort:** 1–2 days · **Risk:** Medium for accidental data exposure · **Benefit:** faster debugging with trustworthy evidence.

Add request IDs, structured errors, parser/job timings, lock-wait visibility, and correlation between API requests, workflow steps, and audit events. Redact credentials, bearer tokens, provider URL secrets, and document contents. Treat operational logs and financial audit evidence as different records; do not claim a log line substitutes for a committed audit event.

### A06 — Lazy loading and a measured asset budget

**Priority:** P2 · **Effort:** 1–2 days · **Risk:** Low–Medium · **Benefit:** smaller initial download, especially at login/on mobile.

Lazy-load routes and move chart-heavy imports away from the initial shell. Use Suspense and error boundaries for loading/chunk failures. Baseline initial JavaScript is 232.48 kB gzip; target at least a 25% reduction in the actual initially loaded JavaScript, not merely a renamed split bundle or a higher warning threshold. Record the browser network/build evidence; no page-load improvement percentage is currently measured. [React lazy-loading documentation](https://react.dev/reference/react/lazy).

### A07 — Search, pagination, and query efficiency

**Priority:** P2 · **Effort:** 2–4 days · **Risk:** Medium for API compatibility and access filtering · **Benefit:** usable growing registers.

Add server-side search, sorting, filters, and pagination to growing document, quotation, estimate, payment, and audit lists. Apply project/role predicates before pagination. Retain existing contracts through additive interfaces rather than replacing arrays without coordination. Measure representative datasets and query counts; add indexes based on observed query plans. No large-data performance benchmark has been run yet.

### A08 — Accessibility validation

**Priority:** P2 · **Effort:** 2–3 days · **Risk:** Low–Medium · **Benefit:** usable financial decisions by keyboard and assistive technology.

Review text size/contrast, focus visibility, modal trapping/restoration, error announcements, chart alternatives, and mobile navigation expanded state. Add automated checks and manual keyboard journeys. Existing focus handling is a foundation, not proof of a complete accessibility assessment.

### A09 — Safer validation defaults and CI

**Priority:** P1 · **Effort:** 1–2 days · **Risk:** Medium for accidentally targeting user data · **Benefit:** reproducible checks without disturbing the demonstration workspace.

Default HTTP evidence and browser verification to isolated databases and ignored output directories. Keep submission export an explicit action. Add CI using locked dependency installation, backend/frontend tests, production build, isolated browser/API scenarios, dependency audits, and contract drift checks. Keep paid/live checks opt-in and secrets server-side. Validate migration/recovery and clean Windows setup before a material release. Resolve the test-client deprecation warning through a supported dependency combination and regression verification rather than a blind upgrade.

### A10 — Request-ingestion and resource bounds

**Status:** **Potential risk** beyond B09's demonstrated expansion · **Priority:** P1 investigation · **Effort:** 1–2 days to assess and add focused controls · **Risk:** Medium.

Verify request-body bounds before multipart spooling, enforce file/page/decompression/time limits, and stop CSV iteration at its row limit before allocation. Examine parser CPU/memory bounds and cleanup on failure. Preserve manual review and private storage. The existing 10 MB/50-page policy and bounded worker are useful but do not establish complete ingress or OS isolation. [OWASP upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

### Security and validation limits

- Dependency scans reported no known advisories at execution time; this does not establish complete security.
- No full penetration test, destructive exhaustion test, load benchmark, or complete accessibility assessment was performed.
- Live SerpApi, DataForSEO, and Frankfurter behavior needs actual configured checks. Fixture success is not live-market evidence.
- Docker, Linux, and a live Ollama model remain unverified; the tested Windows/offline path remains the delivery baseline.
- Preserve documented local hash-chain limits. Public deployment, managed identities, production monitoring/backups, and stronger audit anchoring need a separate operational design; they are not reasons to rewrite the local prototype now.

## 8. Impact-versus-effort matrix

| Workstream | Priority | Expected benefit / impact | Effort | Prerequisites | Principal risk |
|---|---|---|---|---|---|
| B01 contributor-aware independence | P0 | High: restores estimate approval independence | 2–3 days | Audit reconstruction and additive schema | Misclassifying historical authorship |
| B02 commitment coverage | P0 | High: prevents understated estimated costs | 2–3 days | Specification/unit/currency identity | Wrong coverage or double counting |
| B03 rounding policy | P0 | High correctness benefit for low effort | 0.5–1 day | Explicit calculation policy | Rewriting old approved figures |
| B04/B05/B09 input and authentication reliability | P1 | High: bounded, actionable, consistent requests | 2.5–3 days | Shared errors and input policy | Rejected legitimate inputs or poor rate-limit usability |
| B06/B07/B08 user-workflow defects | P1 | High: prevents misleading results, lost edits, and broken print | 2–4 days | Navigation/print-state handling | Regression in saved data or receipts |
| A01–A05/A09/A10 foundations | P1 | High: safer changes, recovery, diagnostics, and verification | See individual estimates; overlapping work | Existing regression suite | Transaction/authority regression |
| F01 quotation evidence/inbox | P1 | High: clearer evidence and reviewer workload | 4–7 days | Approval and contract fixes | Duplicate state or incomplete provenance |
| F02 actual-cost/accrual foundation | P1 | High: meaningful downstream financial measures | 10–15 days | Correct commitment coverage | Incorrect recognition and reconciliation |
| A06–A08 and Q01–Q11 polish | P2 | Medium–High: usability, accessibility, and measured performance | See individual estimates; deliver incrementally | Stable core workflows | Cosmetic changes hiding behavioral regression |
| F03 extended forecasts/EVM | P2 | High once source data exists | 10–15 days | F02 and recorded progress | Unsupported performance indicators |
| F04/F05 QS and sensitivity/maturity | P2 | High estimating usefulness | 8–15 / 5–8 days | Reviewed rules and reliable calculation inputs | Standards overclaim or fabricated assumptions |
| F06 commercial workflows | P3 | High for contract administration | 15–25 days | Contracts, F02, independent authority | Cumulative value/approval errors |
| F07 profitability/reporting FX | P3 | High once accounting data exists | 7–12 days | Cost and AR/AP data | Misstated metrics or conversion basis |
| F08/F09/F10 extensions | P3 | Useful but substantial separate releases | 5–15 days each | Provenance, authority, allocation controls | OCR trust, beneficiary fraud, or overpayment |
| F11 copilot expansion | Follows module | Better explanations of verified new capability | Included with module | Deterministic tools and evidence | Unsupported facts or accidental authority |
| Q12 release/document consistency | P2 | High delivery clarity for low documentation effort | 0.5–1 day initially | Final chosen release scope | Stale archive, counts, or revision evidence |

Highest-value low-effort work includes explicit rounding, actionable import errors, stale-result handling, and scoped printing. The higher-effort contributor and commitment fixes still come first because they protect decision integrity.

## 9. Development roadmap and acceptance gates

### Gate 1 — Review document only

**Deliverable:** this ten-section report, with source references, reproduced outcomes, priorities, effort/dependencies/risks, and a link to the remaining-work checklist.

**Exit gate:** verify section structure, Markdown links, evidence paths, status labels, all nine findings, all feature/recommendation IDs, and the distinction between observed results and proposed tests. This gate does not implement fixes or regenerate submission material.

### Gate 2 — Stabilize authorization and financial decisions

Implement B01, B02, and B03 with focused regressions first. Use additive migrations, a consistent SQLite backup, and recovery rehearsal on a separate copy. Preserve credentials, memberships, cash, settled transactions, approved evidence, and audit events.

**Exit gate:** multi-editor independence is enforced; incompatible/unresolved commitments cannot silently hide costs; policy rounding is consistent; historical records remain intact; original payment scenarios and the BDT 80,000 upgrade example still pass.

### Gate 3 — Fix reliability and workflow defects

Implement B04–B09. Introduce the supporting structured-error and transaction changes needed for safe validation. Investigate quotation/equivalence contributor history and ingress/job risks, recording whether each is confirmed, fixed, or remains a documented limitation.

**Exit gate:** invalid inputs fail clearly without partial persistence; stale results cannot look current; navigation protects edits; estimate and receipt print artifacts contain the correct content; throttling and numeric bounds pass their focused tests.

### Gate 4 — Improve maintainability and usability

Deliver A01–A10 and the relevant quick wins incrementally. Establish CI and contract checks before large feature additions. Keep API compatibility, role/project scope, private uploads, and atomic settlement intact.

**Exit gate:** all regressions pass; diagnostics are redacted; default verification is isolated; accessibility checks cover main journeys; pagination remains project scoped; initial JavaScript reduction is measured against the recorded baseline.

### Gate 5 — Expand through dependency-ordered releases

Deliver F01 and F02, then F03–F05 as their data and professional-review dependencies become available. Deliver F06–F10 as separately bounded commercial/operational releases. Extend F11 only alongside verified services. Each release needs migrations, permission rules, actual UI/API acceptance, documentation, and updated limitations.

**Exit gate:** each feature has independent expected calculations, backend and browser evidence, migration/recovery checks, and truthful live-integration status. No unavailable accounting measure, standard rule, or market price is fabricated.

### Required regression scenarios

- An earlier contributor cannot check or approve retained work after another user edits or revises it.
- Denied approvals create no baseline, payment, or balance movement and retain appropriate audit evidence.
- Wrong-specification, wrong-currency, ambiguous, and duplicate commitment links cannot hide estimate costs.
- Rate and quantity ties follow documented rounding; selection, preview, persistence, approval evidence, and exports agree.
- Malformed imports return actionable 422 responses and leave the record/version unchanged.
- Case/whitespace login variants share throttles; expiry and bounded storage work.
- Changed takeoff inputs invalidate the displayed result; recalculated and saved evidence agree.
- Save / Discard / Stay works for routes, project/version changes, back/forward, failed saves, and conflicts.
- Actual printed estimates contain BOQ codes and totals; receipts still print correctly.
- Pathological numeric representations are rejected before expansion without blocking valid Decimal calculations.
- Existing A–H scenarios, audit integrity, snapshots, reservations, failure rollback, idempotency, and concurrent settlement controls continue to pass.
- Populated migration/recovery and clean installation preserve old records and work without external AI services.

Live provider checks remain opt-in. Record actual search/task IDs, source links, times, and results using locally configured credentials; never publish secrets or relabel fixtures as live evidence.

## 10. Recommended first actions

1. **Review and retain this report.** Use B/F/A/Q IDs to track work and keep the remaining-work checklist aligned when implementation actually occurs. The current documentation task changes only this file.
2. **Implement B01–B03 before expanding financial functionality.** These protect approval independence, forecast completeness, and deterministic arithmetic.
3. **Resolve B04–B09 next and add the missing regressions.** A passing baseline alone does not cover the newly reproduced behaviors.
4. **Add the essential foundations and workflow guidance incrementally.** Prioritize typed errors, short write locks, isolated CI, diagnostics, and quotation evidence before broader module growth.
5. **Build actual-cost/cost-coding data before EVM, profitability, or advanced forecasts.** These measures must derive from evidence and defined accounting bases.
6. **Verify live integrations separately when credentials and real source data are available.** Keep official/reference, historical, supplier, public-listing, and demonstration categories distinct.
7. **Retain release boundaries.** The user will review, commit, and push the source to the actual GitHub repository when ready. Registration/team details and final upload are human actions. Updating the presentation, recording, reports, archive, or submission evidence requires a separate instruction.

**Current readiness:** the existing competition workflows passed their recorded checks, and this review identified additional defects requiring stabilization. The full advanced brief and broader enhancements remain incomplete. No fix, live integration result, performance gain, or submission update is marked complete merely because it is recommended here. All settlement remains simulated, financial authority stays in deterministic backend controls, and AGPL licensing/offline operation remain requirements.
