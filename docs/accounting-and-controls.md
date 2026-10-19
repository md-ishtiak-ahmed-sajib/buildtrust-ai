# Accounting, review controls and release boundaries

The application adds Cost Control & Accounting, Commercial Management, Team & Access, Review Inbox, and Performance & Scenarios. These modules extend the local sandbox. They do not connect a bank or establish production accounting compliance. Local behavior and separate external prerequisites are recorded in [all-suggestions-implementation.md](all-suggestions-implementation.md).

## Records and authority

`control_records` retain typed payloads, calculation results, every contributor, versions and submission snapshots. An Operator prepares and submits; an independent Finance Manager checks; a separate Admin approves. Current account status, role, membership, source versions and the complete bound content are checked again before publication. Submitted controls are locked. Revisions retain contributors; approved postings require supported correcting events rather than edits.

Policy, acceptance, invoice reconciliation, customer certificate/receipt, opening journal, credit, retention release, supplier change, measurement profile, performance baseline/progress, sensitivity, maturity and explicit obligations have separate typed payloads. New routes are in `control_api.py`, `operations_api.py`, `reporting_api.py` and `administration_api.py`. They share the original SQLAlchemy Base and financial transaction context.

## Cost, liability, revenue and cash

- A confirmed receipt cost is measured at its contractual PO rate, assigned a cost code and explicitly dated. Independent approval debits project cost and credits accrued liability once. A unique recognition prevents repeating the accepted cost.
- Reconciliation of an exact supported invoice debits the corresponding accrual, records applicable tax separately, and credits accounts payable/retention. It does not recognize the original cost again. Recognition allocations support splitting an accepted quantity across invoices. Each invoice must be fully supported, cumulative quantities cannot exceed acceptance, and allocation amounts reconcile to the accepted cost. Rounding residue belongs to the final allocation. Supplier certificates claim accepted cost separately; the same source cannot also support an invoice.
- Customer certificates credit revenue and debit receivables/held retention, with separately identified output tax. Cash stays unchanged. An independently approved simulated customer receipt debits cash and reduces its receivable.
- Existing historical settlements are preserved. They are not automatically assigned invented cost-recognition dates. Opening journals require explicit evidence, dates, balance and independent approval. They document opening accounting values without changing existing recorded sandbox cash.

Every journal must balance in integer minor units before it can be stored. Source keys prevent duplicate posting. Journal publication and its approval audit occur in one SQLite write transaction. Settlement additionally commits cash, payable changes, cash reservations, ledger entries, receipt evidence and success audit atomically.

## Installments, credits and retention

After invoice reconciliation, `invoice_entitlements` claim accepted quantities once for the invoice. A cash installment never claims those quantities again. One pending/approved/executing proposal may exist per invoice. `POST /payables/{id}/installments` requires an expected payable version and an exact amount; the existing approval/execution routes, amount limits, 30-minute expiry and idempotency still apply.

The legacy invoice proposal operation pays the full remaining recognized balance; legacy invoices without a payable retain their previous full-payment behavior. Unique settlement per proposal remains enforced. Invoice-wide payment uniqueness was deliberately replaced by aggregate payable controls in migration 0008. Original payment IDs and receipt bodies remain unchanged.

Reservations cover only the installment amount. A dated unpaid remainder stays in the forecast; undated obligations stay visibly unscheduled. Failed execution rolls back financial mutations. Credits against unpaid balances reduce AP; excess credits become supplier credit, without an automatic cash refund. Credits do not release the physical invoice entitlement. Retention release needs separate approval and creates an unpaid amount requiring a separately approved settlement.

## Estimating and performance

The legacy estimate `total` remains the selling/tender total. New calculations expose separate `cost_total` and `tender_total`. Cost excludes profit, recoverable tax and output tax; explicit nonrecoverable tax may enter cost. Unknown nonzero tax treatment prevents a cost baseline. Previously approved snapshots are not recalculated or reinterpreted.

An independently approved performance baseline records BAC and dated cumulative planned values. Independently checked progress records evidenced EV at baseline cost. AC comes from dated recognized project-cost journal entries, not payments. Missing progress/costs and zero denominators remain unavailable.

`CV = EV − AC`; `SV = EV − PV`; `CPI = EV / AC`; `SPI = EV / PV`. EAC methods are `AC + BAC − EV`, `BAC / CPI`, `AC + (BAC − EV)/(CPI × SPI)`, and `AC + sourced bottom-up remaining cost`. Scenario snapshots preserve their inputs and source estimate versions. Reporting FX uses recorded dated evidence and does not change project-currency transactions. A non-BDT payment authority check needs a sourced BDT conversion.

## OCR and measurement

OCR is optional. Run `uv run --project backend python scripts/setup_ocr.py`, then configure `BUILDTRUST_OCR_ENABLED=true`, `BUILDTRUST_OCR_TESSDATA_DIR` and `BUILDTRUST_OCR_LANGUAGES=eng+ben`. The installer verifies the pinned model sizes/hashes in `ocr-models.lock.json`; runtime performs no downloads. PyMuPDF runs in a timed child process with bounded pages, raster dimensions and extracted output. At most five scanned pages are OCR processed per upload; further/ambiguous pages require manual review. Page method and unavailable confidence are retained. Missing or changed models retain manual review instead of preventing offline startup. English recognition through an actual image-only PDF has been exercised; Bengali recognition accuracy needs a representative acceptance corpus.

Trade templates include earthworks, backfill/disposal, masonry/openings, finishes, doors/windows, roofing, pavement, prism/frustum/annular concrete and supplied reinforcement schedules. Factors, deductions, nominal masses and drawing evidence are supplied explicitly. No structural adequacy, laps or automatic standard thresholds are inferred. Independently approved project profiles whitelist deterministic templates and explicit measurement rules, with edition/source/reviewer evidence. No arbitrary rule code executes. Full NRM/CESMM/PWD/LGED compliance and professional acceptance are not claimed.

## Migration and operational limits

Migrations 0005–0014 add authorship, coverage, worker attempts, evidence, accounting, entitlements, obligations and user versions. SQLite's online backup API includes committed WAL data. The controlled payment-table rebuild disables FK enforcement only around migration, checks all foreign keys before commit, and reenables enforcement afterward. A populated-copy migration/recovery check and local before/after legacy-table fingerprints are recorded under ignored `data/`.

Workers retain durable intent, attempts, leases, heartbeats, exponential backoff and a five-attempt ceiling. The local scheduler automatically resumes eligible interrupted work and known remote task IDs, respects live leases, and fences stale publishers. Uncertain paid submissions are held for manual provider reconciliation. Disable automatic dispatch with BUILDTRUST_BACKGROUND_JOBS=false; the supported deployment remains a single local application process. Logs contain request IDs, method/path/status/duration and lock waits, not request bodies, authorization headers or passwords. An upload envelope is bounded before multipart processing. This is still a single-process local application; there has been no full load test or penetration test.

Outstanding scope and acceptance checks remain listed in the implementation ledger, including complete cost-code propagation, commercial schedule/forecast mapping, representative OCR/rule acceptance and broader operational/security assessment. CI configuration has been added, but a hosted run awaits the user's GitHub commit/push. Submission artifacts remain the earlier release and are intentionally untouched.


## Commercial records and certificate settlement

Commercial Management prepares contracts with explicit parties, currency, rates, cost codes, payment conditions, tax, retention and advance recovery. Local RFQs do not send external messages. Bids require independently verified supplier quotations, compatible specifications/units, known landed costs, current validity, matching supplier identity and suitable delivery. Listings and synthetic offers cannot be awarded. Recommendations preserve compared bids and the human selection reason; single-source comparisons remain labeled.

An independently approved purchase award creates a new confirmed PO linked to its source control and cost code. It cannot exceed separately approved procurement BOQ quantity or contractual value, and cannot replace existing procurement or settled rates. Contract scope changes require distinct variation controls. Budget and existing PO amendments remain separately authorized processes.

Checked measurements support work acceptance, which posts project cost/accrual once. Supplier interim certificates reconcile current gross value to approved work/delivery acceptances and clear accrual into payable/retention/tax/advance accounts. Customer interim certificates recognize revenue/receivables separately. Calculations retain cumulative/previous/current work, approved prospective rates, materials-on-site evidence, sourced advance recovery, retention, tax, adjustments and net due. A unique certificate allocation prevents the same accepted cost funding another certificate or an invoice.

Certified supplier payables use the same proposal, approval, reservation, liquidity, idempotency and atomic settlement service as invoice payables. A proposal/payment identifies exactly one invoice or certified payable. The original invoice IDs and stored receipt bodies remain intact. Credits and retention releases require separate approval; tax-bearing credits require explicit tax allocation and source evidence. Recoverable tax reverses the tax asset; nonrecoverable tax reverses project cost. A specified retention-credit portion reduces held retention. Cumulative base/tax credits are bounded against their original source and stale payable versions cannot approve.

Prospective rate changes and quantity reductions cannot rewrite accepted, certified or committed quantities. Time impacts and claimed/reviewed/approved values are retained. Contract variations do not directly alter procurement BOQs, issued POs or approved estimate budgets. CONTRACT_ESTIMATE_LINK now provides independently reviewed, exact direct-cost mapping into a selected forecast. Changed source snapshots retain the estimate amount until fresh review. Composite/allowance-bearing lines and nonzero contract tax, retention or advance terms require an explicit rate-analysis revision; broader combined mapping remains open. No payment date is inferred from delivery.

## Forecast evidence and exports

PROJECT_SCHEDULE records independently reviewed calendar start/completion dates for project-duration forecasts. FINANCIAL_FORECAST binds complete approved customer-contract scope to an approved cost estimate or an available sourced EAC method, with forecast revenue/profit/margin separate from recognized revenue and cash. EVM additionally exposes ETC, VAC and TCPI with unavailable denominators preserved.

Version-2 CSV/XLSX exports include project, revision, state, currency, totals, basis, component JSON and explicit allowance settings. Reimport preserves arithmetic without applying overhead/profit twice. Imported component material/price-selection authority is cleared and must be reviewed again; the original immutable evidence remains in its source revision. Flat external unit rates are treated as final manual/composite rates with zero inherited allowances. Import replaces the draft BOQ; it does not preserve an external approval, procurement authority or source identity.

## Module boundaries

The main application composes document_api, invoice_api, payment_api and workflow_api. Upgrade routing composes price_api, measurement_api, estimate_api and copilot_api. api_support/upgrade_access share resource access rules; accounting, commercial, governance, performance, payments and finance retain distinct business services. SQLite write-transaction ownership remains in the API context and existing settlement service.


## Contract advances, history and bounded processing

ADVANCE_ASSIGNMENT independently binds a reviewed opening ADVANCE or CUSTOMER_ADVANCE journal allocation to one contract/counterparty. Allocations cannot exceed the source balance; certificate recovery cannot exceed the assigned unrecovered amount or contract percentage. Legacy recovery is included when bounding new assignments. No assignment creates a cash movement.

ESTIMATE_MATURITY can bind approved historical project estimates, show exact-description/unit cost-rate comparisons and flag changed specifications. It never infers an AACE class. Internal price history refresh appends fingerprints of approved purchase-order evidence and later settlement context. Whole-invoice payment amounts are labeled as context, never assigned to a line rate, and missing specification/landed charges remain missing.

Request bodies are bounded before multipart/JSON parsing and must arrive within 15 seconds. Untrusted JSON has a 64-level/100000-structure bound. Dedicated PDF children establish a 512 MiB process-memory quota and 45 CPU-second quota (Windows Job Object, POSIX resource limits), in addition to parent wall-clock, page, pixel and output limits. A real child-allocation test verifies the local Windows quota; this is not a full malware sandbox.

Per-request correlation IDs travel in response headers. Persisted idempotent settlement results and terminal failure bodies remain unchanged across retries. OpenAPI includes typed error envelopes, operational pages/attempts and commercial source options. The review inbox derives expiry state from current approval records, with a five-minute warning window.

The six original frontend screens and material quotation/comparison/history workflows are separate modules. Control evidence displays business values and nested readable records, with storage values/fingerprints retained in a separate audit disclosure.


## Completion release: explicit scopes, amendments and corrections

Migrations 0015–0017 add immutable procurement authorization/amendment relations, receivable correction balances and project-scoped query indexes. A populated-copy rehearsal and live upgrade preserve 54 legacy table/column fingerprints, credentials, original receipts and audit history. Original audit payloads and stored receipt bodies retain their exact historical schema; current authoritative calculation/source views have explicit response contracts and generated frontend types.

`forecasting.py` is the shared estimate/extended cash-overlay service. Whole-item or specific-component allocations retain quantity/unit conversions, disjoint intervals, source hashes, calculation policy, dated segments, tax treatment, retention and sourced advance recovery. Whole-item contracts include their complete scope; component mappings apply estimate overhead/contingency once and contract tax once. Unmapped components retain estimate assumptions; profit and output tax do not become project cost. Missing cash or retention-release dates remain unscheduled. Changed sources retain estimated requirements until fresh review. Existing invoice/certificate obligations and exact installments remain canonical; unrecognized PO exposure and held retention appear separately without fabricated dates.

Procurement value/quantity authorization is separate from estimate budgeting. An independently checked and Admin-approved PO amendment appends retirement events for eligible unreceived scope, then publishes a successor PO. It cannot rewrite original lines/rates or retire received, allocated, certified or settled scope. Entitlement, coverage, cost control and forecasts use effective quantities. Material procurement/supplier/authority changes invalidate affected pending approvals and release live reservations.

Source-linked certificate reversals post compensating financial journals and adjust payable/receivable or supplier/customer credit balances. They never refund cash. A separate linked accepted-cost correction reverses supported cost/accrual without releasing physical quantity. Cumulative source, cost-code, tax, retention, advance and previous-correction limits are checked under the same serialized approval boundary.

The estimate page now delegates BOQ display, measurement/rate editing, basis/allowances and forecast presentation to focused components. Read failures retain request/field/retry details; loading retries preserve the workspace, and failed edits stay available for correction. Paginated registers cover growing accounting and commercial records alongside the original lists.

See [completion-verification.md](completion-verification.md) for actual test results, local workload limitations and separately outstanding external verification.
