# Security self-assessment

BuildTrust AI is a local, fictional payment simulator. This report describes implemented controls and remaining risks. It is not regulatory certification, a penetration-test attestation, or proof of production suitability.

## Assets and boundaries

Assets include source documents and extracted claims, approved procurement/supplier records, cash balances, receipt entitlement, payment reservations, approval snapshots, credentials/signing material, settlement evidence, and audit history.

Trust boundaries separate browser input from the API, uploaded content from approved project evidence, workflow automation from human authorization, optional LLM prose from deterministic decisions, and application access from unrestricted host/database administration. The API binds only to localhost in the primary delivery. All beneficiary tokens are explicitly fictional.

## Permission tiers

| Role | Implemented authority | Restrictions |
|---|---|---|
| Operator | Intake, correction, analysis, preparation | Cannot approve or execute |
| Finance Manager | PO/receipt confirmation; approval and execution up to BDT 100,000 | Cannot approve own proposal or publish BOQ/variations |
| Admin | BOQ/variation confirmation, demo reset, approval/execution up to configured ceiling | Cannot bypass financial blocks or approve own proposal |
| Auditor | Read assigned project records and verify integrity | No financial or document writes |

Each request reloads account role, active status, and project membership from the database. An authoritative role cannot be selected in a login or financial request. Payment execution rechecks the approving account's active authority. Archived demo runs remain readable and cannot receive ordinary API financial changes.

## Implemented controls and known risks

| Threat | Implemented control | Residual risk / boundary |
|---|---|---|
| Stolen password database | Argon2 password hashes; generated local passwords | Host administrator can access local secrets; no MFA |
| Forged/expired tokens | Signed 30-minute JWTs, fixed algorithm/issuer/audience; current account lookup | No complete production session-revocation service |
| Browser token persistence | Memory-only bearer token; no auth cookies or token localStorage | XSS on an authenticated origin could access memory |
| Login abuse | Per-process email/address attempt window | Not distributed; not a production rate-limiting system |
| Unauthorized operation | Backend role and membership checks; forbidden/not-found errors; audit outcome | Trusted administrators can alter the host/database |
| Uploaded “approval” | Separate authorized procurement confirmation | Human certification can be mistaken or dishonest |
| Beneficiary substitution | Match invoice fingerprint to approved supplier master; no document-driven master update | Supplier-master verification/administration UI is not implemented |
| Duplicate invoice | File hash and business identity detection; unique invoice identity | Identity normalization is limited; altered numbers still need financial review |
| Reused receipt | Per-receipt-line allocation under serialized transactions; PO/BOQ caps | Accepted delivery truth depends on authorized records |
| Unapproved financial changes | Canonical exact approval snapshot; current source/content/policy revalidation | Complete database compromise can rewrite all relevant state |
| Double execution | Mandatory idempotency key, stored original result, unique proposal settlement and authoritative invoice/certificate payable balances | Local SQLite availability and lock capacity are limited |
| Partial settlement failure | Atomic cash/payment/subledger/allocation/audit commit; rollback; separately recorded failure | No external banking provider or distributed transaction is exercised |
| Liquidity pressure | Current settled-cash check; reserve gating in base and delayed scenarios | Scheduled receivables remain assumptions; no external confirmation |
| Prompt injection | Document content remains untrusted; deterministic controls; no LLM payment/write tools | Instruction heuristics do not detect every attack; optional prose can be incorrect |
| Dangerous upload | Type/size checks, PDF signature, UUID storage names, private storage, bounded PDF child process | No antivirus service, hardened OS sandbox, or memory cgroup isolation |
| Malicious document preview | Authenticated raster PDFs/escaped text; no active original-file rendering | A native parser vulnerability remains possible |
| Sensitive response leakage | Explicit user/document/receipt models; structured errors; private paths/secrets omitted | Local credentials are readable by the local operator/host account |
| Audit manipulation | Canonical SHA-256 chain, serialized appends, verifier identifying first failure | Whole-chain rewrite and tail truncation need an external trusted checkpoint to detect |

## Payment controls verified by tests

The automated suite exercises role denial, account inactivity, entity access, independent approval, inclusive role thresholds, changed approval fields and source data, expiry, current cash changes, concurrent execution requests, exact retry results, injected failure rollback, and protected receipt retrieval. It also verifies matching/units/tax arithmetic, prompt-injection holds, and tampered audit-event detection.

Actual counts and command logs are referenced in `test-results.md`. A–H evidence uses a real HTTP server and persistent SQLite, with mock references and balance changes captured from execution. No externally settled banking transaction is claimed.

## Deployment limitations and recommended future controls

The release is designed for an attended local judge demonstration. A public or organizational deployment requires TLS, protected account provisioning and recovery, stronger token/session lifecycle, MFA where appropriate, centralized rate limits, least-privilege OS accounts, isolated parsing and resource quotas, malware scanning, backup/restore drills, independently retained audit checkpoints, monitoring, retention policy, and a separate security review.

Those are recommendations, not implemented certifications. Optional Docker configuration is provided; its actual validation status is stated in the test report. There is no live banking integration, verified credit offer, regulatory certification, or mainnet transaction.

## Price intelligence and estimating controls

The upgrade adds fixed-origin API adapters, server-only credentials, bounded responses,
provider failure isolation, explicit paid-task IDs, search deduplication and refresh
limits. Unknown paid submissions are held for manual provider reconciliation. No
generic URL-fetch endpoint exists. External links require public HTTPS syntax and
are opened with noreferrer/noopener; they are not fetched by the backend.

PDF/CSV/XLSX quotations remain drafts until a different authorized person verifies
them. Financial fields are validated server-side; files and extraction suggestions
never confer engineering or financial authority. Spreadsheet formulas and oversized
expanded workbooks are rejected; export cells are escaped against formula injection.

Estimates are separate from procurement entitlement. Version checks, submission locks,
independent checking, a separate Admin, retained full evidence snapshots, and current
checker-authority checks protect budget approval. Selected prices are immutable,
and their material requirements must remain compatible. Price previews and copilot
sensitivity calculations have no procurement/payment/cash mutation authority.

Remaining limits: standards profiles require professional review; provider listing
availability/completeness is not guaranteed; no live paid-provider validation without
credentials; single-process rate limiting/workers are not a distributed operations
system. The local audit chain retains its previously documented administrator limits.

## Current control extensions

Retained estimate and quotation contributors survive edits/revisions and bind submission evidence. Older pending estimate submissions require fresh review during migration; approved history is preserved. Source-bound commitment mappings replace item-code-only forecast deductions. Accounting/governance controls retain every contributor and require independent checking and a separate Admin approval. Supplier changes preserve master snapshots and invalidate affected pending payment approvals.

Installments use authoritative payable balances and one persistent invoice entitlement claim. Unique settlement per proposal, exact cash reservations, current liquidity/authority, idempotency and atomic cash/ledger/audit publication remain enforced. Non-BDT payment authority requires sourced BDT conversion evidence. Credits do not refund cash or release physical entitlement automatically.

The request envelope is bounded before multipart parsing. Import iteration, XLSX expansion and PDF/OCR page/pixel/output/time limits precede expensive publication. OCR uses pinned local models, no runtime downloads, and human review. Diagnostics contain request IDs and timing metadata, not request bodies or passwords. Argon2 and expensive parsing run outside writer locks, followed by current authority/version checks.

These are implemented controls, not a security certification. Local automatic recovery and dedicated-parser OS memory/CPU quotas are implemented and locally tested. A complete accessibility assessment, load testing and independent penetration testing remain outstanding. See [current controls](accounting-and-controls.md) and [per-item status](all-suggestions-implementation.md).


## Completion release controls

New procurement/correction/mapping workflows use the existing contributor-aware preparation, independent checking and independent Admin approval. Snapshots bind current source versions and calculations. Pending payment proposals are retired after material source or account-authority changes; executing code also rechecks preparer and approver access. Competing credits and settlements serialize within SQLite; failed operations preserve cash and retain denied-attempt evidence after rollback.

The media recorder requires an isolated runtime marker and explicit localhost address, rejects the working app port, and never resets the user's database. Video provenance binds application source hashes and actual duration/decoding checks. Release packaging excludes credentials, uploads, databases, environments and dependencies; source fingerprints, archive contents and checksums are validated.

Actual checks and assessment limits are in [completion-verification.md](completion-verification.md). Paid-provider, professional, assistive-technology and independent security acceptance require their external prerequisites.
