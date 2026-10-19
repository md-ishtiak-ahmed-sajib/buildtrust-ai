# Security self-assessment

BuildTrust AI is a local payment simulator. This report describes implemented controls and known risks. It is not a penetration-test certificate, regulatory approval or proof that the app is ready for public hosting.

## Accounts and public passwords

Private setup generates random passwords and stores only Argon2 hashes in the database. The local credential file and signing secret stay outside Git and the source archive. Login uses short-lived signed tokens kept in browser memory. Requests reload the current active user, role and project membership.

The separate public demo intentionally publishes four fictional passwords. It uses a marked `data/public-demo` profile and localhost port 8003. It refuses unrelated data and conflicting accounts; it never resets existing private passwords. Its settings ignore private environment/.env values. Public passwords are not a secret or a suitable configuration for an Internet-facing app. Signing secrets are still generated privately. The launcher disables paid services and optional model access.

## Roles and independent review

| Role | Authority | Boundary |
|---|---|---|
| Operator | Prepare, upload, correct and analyze | Cannot approve/execute payments |
| Finance Manager | Confirm procurement, check estimates/controls and approve eligible payments | Independent work only; BDT 100,000 payment ceiling |
| Admin | Approve checked budgets/controls, manage access and eligible payments | Cannot approve retained work they prepared/checked; configured payment ceiling |
| Auditor | Read assigned records, receipts and integrity results | No writes |

Retained contributors survive edits and revisions. Approvals bind exact snapshots and current sources. Execution rechecks preparer, approver and executor authority. Account/source changes invalidate affected pending proposals and release reservations. Archived runs remain read-only through ordinary business endpoints.

## Controls and remaining risks

| Risk | Implemented protection | Remaining boundary |
|---|---|---|
| Password theft/login abuse | Argon2, generic errors, normalized account/IP failure buckets, expiry and Retry-After | Per-process limits; no MFA/SSO or enterprise recovery |
| Forged/stale token | Fixed signing policy, expiry, issuer/audience and current database access | Host compromise can expose signing material |
| Untrusted document | Private files, explicit human confirmation, escaped text and image previews | Human review may be wrong; parser vulnerabilities remain possible |
| Beneficiary substitution | Source-linked supplier changes with separate checking/approval | Real identity/callback evidence needs people |
| Duplicate quantity/payment | Invoice identity, receipt allocations, payable bounds, one active proposal and unique settlement per proposal | False source records can still misstate physical delivery |
| Changed approval | Source/version/policy/content snapshot and current revalidation | A database owner can rewrite underlying state |
| Partial settlement failure | One cash/payment/ledger/allocation/receipt/audit transaction; rollback | No distributed bank transaction has been exercised |
| Cash shortfall | Current cash and base/delayed reserve checks | Expected inflows are assumptions |
| Prompt injection | Document text is data; deterministic decisions; no AI approval/payment tools | Optional explanation text may still be wrong |
| Resource abuse | Pre-parser body limits, bounded JSON/CSV/XLSX, PDF child time/page/pixel/output/memory/CPU limits | Not antivirus or a complete malware sandbox |
| Provider abuse | Fixed origins, bounded responses, stored task IDs, server-only keys and unknown-submission holds | Paid/live recovery needs separate verification |
| Spreadsheet injection | Reject imported formulas; escape exported formula-like cells | Review files in a suitable local environment |
| Browser disclosure | Memory-only tokens, protected previews/downloads and typed responses | XSS on an authenticated origin can access browser memory |
| Audit tampering | Canonical SHA-256 chain, serialized appends and first-failure verification | Full rewrite or tail removal needs an independent trusted checkpoint |

## Financial records and jobs

Estimates do not authorize procurement or payments. Cost and selling totals remain separate. Installments use one accepted quantity claim and exact cash reservations. Credits/corrections do not refund cash or release physical entitlement. Financial correction and accepted-cost reversal need separate linked reviews.

Jobs retain attempts, leases, heartbeats, bounded retry and restart recovery. Stale publishers are fenced. Unknown paid submissions require manual reconciliation. The supported deployment is one local process, not a distributed worker platform.

Logs contain request IDs and timing/status metadata. They omit credentials, tokens, provider keys and document contents. Numeric and upload bounds apply before expensive expansion/parsing. Hashing and parser work stay outside ordinary financial write locks, followed by current authority/version checks.

## Evidence and deployment limits

See [actual verification](completion-verification.md) for tests, HTTP/browser workflows, parser checks and local workload results. Known-advisory scans describe published issues at their execution time; they do not prove complete security. Automated accessibility checks do not replace human assessment.

Recordings use isolated databases and addresses. Their provenance binds application source, duration and decoding. Packaging excludes private credentials, databases and uploads. The public sample-password fixture is intentionally included and labelled.

Before any wider deployment, independently review hosting, TLS, identity lifecycle, MFA, OS isolation, malware handling, backups, external audit checkpoints, monitoring, data retention and incident response. See [remaining work](../docs/remaining-work.md). No real bank transfer, professional standards certification or security certification is claimed.
