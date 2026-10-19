# BuildTrust AI technical documentation

## Version 0.2 estimating upgrade

The original finance workflow below is preserved. The upgrade adds project-scoped
materials, provider search jobs/states, immutable observations/selections, reviewed
quotations, exchange-rate observations, contextual measurement profiles and sheets,
versioned estimate BOQs/rate components, full approval snapshots and budget baselines.
These share the original database, auth, project membership, transactions and audit.

Additive migrations 0003/0004 preserve legacy records. Startup uses SQLite online
backup before a populated database changes revision. Provider work runs outside write
transactions; task IDs persist before retrieval. Financial writes retain short
serialized transactions and explicit optimistic versions. New frontend areas are
BOQ & Estimates, Quantity Takeoff, and Materials & Prices.

See advanced-upgrade-plan.md, price-source-integrations.md,
quantity-surveying-standards.md, measurement-rule-register.md,
estimating-methodology.md, financial-controls.md, and advanced-feature-tests.md.
The refreshed package uses the verified release; individual artifact and source-agreement checks are recorded in submission/execution-evidence.

## Executive summary

BuildTrust AI is a local construction-finance prototype for Topic E: SME Finance Copilot. It demonstrates document intake, four-way reconciliation, explainable risk decisions, liquidity assessment, independent human approval, simulated settlement, and traceable execution evidence. Its key distinction is using accepted delivery as a payment-entitlement boundary rather than treating an estimated BOQ as proof of supply.

## Problem, users, and scope

Construction SMEs reconcile records held by project staff, procurement, suppliers, and finance. Invoice quantity, contracted price, accepted delivery, beneficiary identity, and available cash must agree before a payment is authorized. The intended users are project Operators, Finance Managers, administrators responsible for approved scope, and read-only Auditors.

The prototype supports fictional projects and suppliers, imported source documents, one currency and cash account per project, and independently approved installments against supported payable balances. It does not offer bank connectivity, cross-currency settlement, financing offers or automatic tax determination. Explicit dated payroll and other obligations can be recorded; this is not payroll processing or a complete statutory accounting suite.

## Architecture

The React workspace calls the same-origin `/api/v1` API. FastAPI authenticates a short-lived signed token, reloads the user and project membership, then invokes domain services. SQLAlchemy uses explicit SQLite transactions, foreign keys, WAL, and bounded lock waits. Alembic creates the frozen initial schema and the active-proposal uniqueness guard. The built frontend is served by the same application in judge mode; Vite proxies requests in development.

Domain modules separate document processing, finance, payment lifecycle, audit, workflow orchestration, and security. Optional Ollama explanations have no database-write or payment interface. See `architecture.mmd` and the README diagram.

## Data model

The relational schema contains users, project membership, projects, approved supplier masters, documents and extraction revisions, BOQ items and approved variations, POs and lines, accepted receipts and lines, invoices and lines, verification results, cash movements, payment proposals, cash reservations, receipt allocations, approvals, payments, execution attempts, ledger entries, audit events, workflows, and workflow steps.

Unique constraints cover supplier codes per project, procurement identities, invoice identity `(project, supplier code, invoice number)`, one active proposal per invoice or certified payable, one settlement per proposal, and aggregate payable-balance controls, idempotency keys, and mock references. Financial balances are SQLite integers in minor units. Quantity and rate strings preserve exact Decimal values. UTC timestamps use explicit `Z` strings rather than relying on SQLite timezone coercion. Scheduled business dates are date-only values interpreted in Asia/Dhaka.

## Document processing

The upload service validates size and type, checks PDF signatures, writes a server-generated storage name, hashes the original bytes, and parses actual contents. Structured CSV/JSON imports are schema-validated. A bounded PyMuPDF child process extracts PDF text and detected tables. Only documented labeled PDF layouts receive automatic field suggestions. Scanned and ambiguous documents remain reviewable rather than receiving invented values.

Every extraction revision records field paths, values, source document IDs, page/row when supported, extraction method, and review metadata. Deterministic parsers do not invent confidence scores. PDF page references are populated only when a value can be located on exactly one extracted page. Human corrections preserve prior revisions and expire active invoice proposals. Confirmed procurement evidence cannot be edited through ordinary document correction.

An invoice is a supplier claim. BOQ/variation publication requires Admin confirmation; PO/receipt publication requires Finance Manager or Admin. Supplier-master records are seeded administrative data and cannot be overwritten by uploaded beneficiary instructions.

## Four-way reconciliation and financial methodology

The engine matches exact item codes and specifications, normalizes compatible quantities and rates, and compares cumulative approved scope, ordered quantity, accepted delivery, and current claims. It subtracts active and consumed receipt allocations, excludes the same invoice's own reservation during reanalysis, and also enforces the remaining BOQ value budget. Quantities for blocked invoices are never consumed.

The claimed subtotal, line arithmetic, PO tax/retention terms, per-invoice discount, and total must agree. Unsupported amounts, uncertain units, unauthorized changes, missing delivery, wrong currency, beneficiary changes, and duplicate settlements block payment. Findings contain a stable code, severity, explanation, and source references. There is no trained fraud-probability claim. See `financial-rules.md` for exact formulas and boundaries.

## Cash-flow methodology

Each project has recorded cash, a required reserve, scheduled receivables, and committed outflows. Pending/approved proposals reserve cash without posting a ledger debit. Forecasts start from recorded cash less other reservations and the proposed payment. Linked obligations are excluded when their invoice is already included as a reservation/proposal; settled obligations are not projected again.

Daily projections cover 30 days: opening plus scheduled inflows minus scheduled outflows. Three scenarios show base records, configurable delayed receivables, and increased eligible future costs. A payment must preserve the reserve immediately and throughout both base and policy-delayed scenarios. Same-day expected inflows cannot conceal insufficient cash at execution. Cost-pressure shortfalls are warnings. Forecasts describe assumptions, not externally verified predictions.

## Persisted agent workflow

`POST /agent/analyze` creates a workflow and returns HTTP 202. The local state machine persists nine observable stages: intake, extraction review, reconciliation, risk, cash flow, recommendation, payment preparation, human authorization, and audit evidence. Each step records its typed tool name, actual stored inputs/outputs, status, and timestamps.

Successful analysis may prepare a proposal and stops at `AWAITING_APPROVAL`. Blocking analysis creates no payable proposal. A restart marks unfinished runs `INTERRUPTED`; authorized users can retry. Repeated analysis reuses an active proposal and does not consume entitlement twice. The workflow runs in the local FastAPI process, not a durable distributed worker.

The copilot handles the brief's five question types deterministically using saved results and current cash data. Optional Ollama prose is labeled, bounded by timeout, and checked for reference validity. Its output cannot change any control or financial state. A provider failure falls back to deterministic explanations.

## Payment-state machine and consistency

The lifecycle records creation and validation, then persists `PENDING_APPROVAL`, `APPROVED`, `EXECUTING`, and `SETTLED`, or terminal `BLOCKED`, `REJECTED`, `FAILED`, or `EXPIRED`. Transient settlement stages are recorded as audit events within the successful transaction. Expiry is enforced on actions; reads also report expired pending/approved proposals accurately.

Approval binds invoice, supplier, beneficiary fingerprint, amount, currency, proposal version, expiry, complete source snapshots, and financial policy. The creator cannot approve. Role limits and membership apply at the backend. Execution also rechecks the approving account's current authority.

Settlement obtains a SQLite immediate write transaction, checks the idempotency record, validates approval/current controls, debits cash, creates one payment, consumes reservations/allocations, posts balanced cash/payable subledger entries, settles linked obligations, writes the receipt, and appends audit events. All succeed or all roll back. Failure status, reservation release, the failed idempotency result, and audit evidence are committed after rollback. Identical successful retries return the original receipt; terminal failed retries return the original failure.

## Security and audit architecture

Passwords use Argon2. Tokens expire after 30 minutes and use a generated private signing secret. Roles and active status are never accepted from login request claims. The browser holds tokens in memory. Resource access requires project membership; archived demo runs are read-only through the API.

Audit events capture actor identity and role, UTC time, resource, structured outcome, previous hash, and SHA-256 of canonical sorted JSON. All appends use serialized write transactions. Integrity verification walks the chain and reports the first failing event. Failed and unauthorized operations are recorded after their business transaction has rolled back. Demo reset archives active projects, creates a new run, and preserves history.

A local chain cannot establish independent immutability. An unrestricted database administrator can rewrite all events or truncate the tail. The security report distinguishes these limits from implemented application controls.

## Testing and actual results

Tests use dedicated temporary SQLite databases and real endpoint requests. They cover financial calculations, document intake/trust, project access, approval boundaries, separation of duties, stale snapshots, execution concurrency, rollback, receipt reuse, prompt injection, optional-provider failure, and audit integrity. Browser checks exercise the desktop payment journey and mobile PDF review. A separate evidence server runs A–H over real TCP/HTTP and stores persistent results.

Actual final counts and command output are in `test-results.md` and the accompanying execution-evidence logs. No test result is inferred solely from intended code.

## Deployment and operational boundaries

The primary delivery is native Windows on loopback with locked dependencies. Optional Docker Compose uses a persistent data volume. Preserve the signing-secret file and database together for a continuing demo; rotating the secret invalidates existing tokens. Runtime data and credentials must not enter a source archive.

This release is intended for a controlled local demonstration. Public deployment would require a separate review of TLS, account lifecycle, rate limits, malware scanning, resource isolation, backup/recovery, independent audit retention, and operational monitoring.

## Limitations and future development

See `limitations.md`. External acceptance includes representative document layouts, professional/accounting review, independent accessibility/security assessment and available platform/provider environments. Composite forecasts, source corrections and controlled procurement amendments now have local acceptance evidence. Supplier changes, certificates/progress, installments, credits and local durable scheduling now have implemented workflows. These should follow the verified financial and authorization boundaries already implemented.

## Current all-suggestions development

The application now includes controlled accounting/journals, invoice installments/credits/retention, supplier change review, source-bound project measurement profiles, optional OCR, expanded trade geometry, separate cost/tender values and cost performance/reporting scenarios. These additions narrow the earlier backlog described above. [Accounting and controls](accounting-and-controls.md) documents formulas, interfaces, migrations and limits. [The 42-item matrix](all-suggestions-implementation.md) records verified behavior and unfinished scope; commercial contracts, RFQs, verified bids, controlled awards, work acceptance, cumulative certificates and prospective variations now exist; broader acceptance remains open.


## Completion release: explicit scopes, amendments and corrections

Migrations 0015–0017 add immutable procurement authorization/amendment relations, receivable correction balances and project-scoped query indexes. A populated-copy rehearsal and live upgrade preserve 54 legacy table/column fingerprints, credentials, original receipts and audit history. Original audit payloads and stored receipt bodies retain their exact historical schema; current authoritative calculation/source views have explicit response contracts and generated frontend types.

`forecasting.py` is the shared estimate/extended cash-overlay service. Whole-item or specific-component allocations retain quantity/unit conversions, disjoint intervals, source hashes, calculation policy, dated segments, tax treatment, retention and sourced advance recovery. Whole-item contracts include their complete scope; component mappings apply estimate overhead/contingency once and contract tax once. Unmapped components retain estimate assumptions; profit and output tax do not become project cost. Missing cash or retention-release dates remain unscheduled. Changed sources retain estimated requirements until fresh review. Existing invoice/certificate obligations and exact installments remain canonical; unrecognized PO exposure and held retention appear separately without fabricated dates.

Procurement value/quantity authorization is separate from estimate budgeting. An independently checked and Admin-approved PO amendment appends retirement events for eligible unreceived scope, then publishes a successor PO. It cannot rewrite original lines/rates or retire received, allocated, certified or settled scope. Entitlement, coverage, cost control and forecasts use effective quantities. Material procurement/supplier/authority changes invalidate affected pending approvals and release live reservations.

Source-linked certificate reversals post compensating financial journals and adjust payable/receivable or supplier/customer credit balances. They never refund cash. A separate linked accepted-cost correction reverses supported cost/accrual without releasing physical quantity. Cumulative source, cost-code, tax, retention, advance and previous-correction limits are checked under the same serialized approval boundary.

The estimate page now delegates BOQ display, measurement/rate editing, basis/allowances and forecast presentation to focused components. Read failures retain request/field/retry details; loading retries preserve the workspace, and failed edits stay available for correction. Paginated registers cover growing accounting and commercial records alongside the original lists.

See [completion-verification.md](completion-verification.md) for actual test results, local workload limitations and separately outstanding external verification.
