# Security self-assessment

BuildTrust AI is a local payment simulator. This report describes implemented controls and known risks. It is not a penetration-test certificate, regulatory approval or proof that the app is ready for public hosting.

## Accounts and public passwords

Private setup generates random passwords and stores only Argon2 hashes in the database. The local credential file and signing secret stay outside Git and the source archive. Login uses short-lived signed tokens kept in browser memory and linked to revocable server sessions. Logout, password changes, recovery and authority changes revoke affected sessions. Requests reload the current active user, role and project membership.

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
| Password theft/login abuse | Argon2, generic errors, normalized account/IP failure buckets, expiry and Retry-After | Persistent SQLite limits and offline one-use recovery; no MFA/SSO or email recovery |
| Forged/stale token | Fixed signing policy, expiry, issuer/audience and current database access | Host compromise can expose signing material |
| Untrusted document | Private files, explicit human confirmation, escaped text and image previews | Human review may be wrong; parser vulnerabilities remain possible |
| Beneficiary substitution | Source-linked supplier changes with separate checking/approval | Real identity/callback evidence needs people |
| Duplicate quantity/payment | Invoice identity, receipt allocations, payable bounds, one active proposal and unique settlement per proposal | False source records can still misstate physical delivery |
| Changed approval | Source/version/policy/content snapshot and current revalidation | A database owner can rewrite underlying state |
| Partial settlement failure | One cash/payment/ledger/allocation/receipt/audit transaction; rollback | No distributed bank transaction has been exercised |
| Cash shortfall | Current cash and base/delayed reserve checks | Expected inflows are assumptions |
| Prompt injection | Document text is data; deterministic decisions; no AI approval/payment tools | Optional explanation text may still be wrong |
| Resource abuse | Pre-parser body limits, bounded JSON/CSV/XLSX, PDF child time/page/pixel/output/memory/CPU limits | Not antivirus or a complete malware sandbox |
| Provider abuse | Fixed origins, bounded responses, stored task IDs, server-only keys, explicit paid enablement, atomic daily reservations and unknown-submission holds | Paid/live recovery needs separate verification |
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


## Twenty-item security review

Release date: October 20, 2026. “Verified” below means local automated acceptance of the named control, not independent certification. Paid-provider and professional/deployment acceptance remain separate. The four README demo passwords are intentionally public and remain unchanged.

| No. | Requested check | Status and implemented control | Evidence and practical limit |
|---|---|---|---|
| 1 | Keep API keys out of the frontend | Verified locally: credentials stay in backend settings; provider status exposes enabled/disabled state only | Secret scan checks frontend source, built assets and archives; private-profile secrets are compared without printing them |
| 2 | Exclude .env files | Verified locally: Git, Docker and source packaging exclude .env variants and private key/credential files; empty .env.example stays public | Public-folder filename check and release archive checks |
| 3 | Scan Git history | Verified: pinned Gitleaks 8.30.1 scans every available ref, current files/build and historical release archives, including nested contents | Redacted security-secret-scan.json; pattern scans do not prove absence of every possible secret |
| 4 | Rotate exposed keys | No confirmed exposure identified by the scans; no key rotation claimed | Exact local private-value comparisons also found no matches. Any future genuine leak requires provider revocation/replacement by its owner; Git history is preserved |
| 5 | Check permissions every request | Verified locally: session, account active state, current role and membership are checked on the server | Auth and project-isolation tests; no reliance on hidden UI controls |
| 6 | Distrust client IDs, roles and prices | Verified: database identity and policy control authority; monetary calculations and payment snapshots remain server-owned | Forged role/identity tests and financial regression scenarios; authorized users can still prepare explicitly reviewed estimates |
| 7 | Isolate users' data | Verified: unrelated projects, document details and previews are unavailable to an unassigned account | Two-account tests; authorized members deliberately share project business records |
| 8 | Protect database and files | Verified locally: private runtime permissions, safe storage paths and link/traversal rejection | Windows local checks; Linux permission checks run in hosted CI. OS administrators remain trusted; files are not encrypted |
| 9 | Protect direct Admin calls | Verified: direct administration and recovery calls require current Admin authority | Operator and unassigned-account requests are denied; last-Admin safeguards remain |
| 10 | Test login/logout/recovery | Verified locally: persistent 30-minute sessions, server logout, current-password change and hashed single-use 15-minute recovery tokens | Auth tests and browser security workflows. Public demo passwords cannot be changed; Admin recovery needs the local owner |
| 11 | Limit login/signup/expensive calls | Verified locally: persistent account/IP admission and failure buckets, operation limits and Retry-After | Concurrency, restart and boundary tests. No public signup exists; account creation is Admin-only |
| 12 | Cap AI/provider usage | Verified locally: paid providers disabled by default; positive limits and cost bounds required; reservations commit before dispatch | Mocked budget/retry tests. Local model has daily/concurrency/token/time/response bounds. Actual paid billing still needs separately authorized live verification |
| 13 | Validate inputs on server | Verified: typed contracts, bounded decimal/JSON/import parsing, explicit versions and business validation | Input and financial suites; front-end validation is only a convenience |
| 14 | Prevent SQL injection | Verified: ORM/bound parameters and allowlisted register behavior; login injection text grants no access | Query review and adversarial login/financial tests; maintenance SQL operates on controlled schema names |
| 15 | Prevent scripts from user content | Verified locally: escaped React/text content, raster document previews, attachment downloads and same-origin CSP with no inline scripts | Browser CSP test and upload tests. Inline styles remain allowed for charts; authenticated-origin XSS would still be serious |
| 16 | Limit uploads | Verified: file allowlists/signatures, 10 MB file bound, 50 PDF pages, pre-parser body bounds and bounded workers | Existing parser/upload tests; not an antivirus or complete malware sandbox |
| 17 | Verify payments before paid-feature access | Not applicable: this app has no subscription billing or paid-feature unlock endpoint | Sandbox project settlement is revalidated on the server. No real gateway/webhook or real payment verification is claimed |
| 18 | Disable debug and redact errors | Verified locally: debug=False, generic unexpected-error responses with request IDs and fixed metadata logging | Synthetic-secret error/log test and scanner output; no request bodies, tokens or provider URLs are logged |
| 19 | Back up and restore | Verified locally: consistent database plus referenced files/signing material, checksummed private archive and isolated restore | Restore checks hashes, foreign keys and audit integrity; copied sessions/recovery tokens are revoked before fresh login. Never overwrites working data |
| 20 | Test two accounts and anonymous access | Verified: anonymous business endpoints reject access and separate accounts cannot cross project/file boundaries | Security tests plus role/payment browser workflows; public health, sign-in, recovery redemption and static UI are intentionally reachable |

See [account, recovery and backup instructions](account-security.md), [actual release verification](completion-verification.md) and the recorded test logs. Package publication is gated on the complete regression and fresh-install checks. Registration email was sent by the team; organizer confirmation and final project submission remain pending.
