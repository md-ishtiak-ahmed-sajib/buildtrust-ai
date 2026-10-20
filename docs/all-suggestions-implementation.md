# Implementation ledger

This ledger covers all **42 recommendations**: B01–B09, F01–F11, A01–A10 and Q01–Q12. It records completed local work and links to evidence. Only unfinished tasks belong in [Not implemented.md](../docs/remaining-work.md).

**Local checks passed** means the implemented local behavior has test/API/browser evidence. It does not mean live providers, real documents, professional acceptance or production hosting have been certified. See [current verification](completion-verification.md) for actual counts and dates.

## Nine reproduced problems

| ID | Completed work | Evidence/limit |
|---|---|---|
| B01 | Retain all contributors across estimate edits/revisions; block their independent checking/approval | Estimate, quotation and equivalent-review tests; old approved history preserved |
| B02 | Use compatible, versioned BOQ-to-PO coverage; keep unresolved costs visible | Incompatible commitment and source-change tests |
| B03 | Apply explicit HALF_UP rounding to money and published rates | Tie `1.2345665` becomes `1.234567`; old snapshots retained |
| B04 | Normalize login identifiers before lookup and throttling | Whitespace variants share bounded account/IP limits |
| B05 | Validate required/duplicate import headers and stop at row limits | Structured 422 errors; failed imports leave drafts unchanged |
| B06 | Invalidate takeoff results when inputs change | Browser checks 9.6 m³ becoming stale, then 19.2 m³ after recalculation |
| B07 | Protect unsaved estimates during navigation, project/version changes and failed saves | Save/Discard/Stay browser checks |
| B08 | Separate estimate and receipt print styles | Actual printed BOQ codes/totals and receipt checks |
| B09 | Bound numeric text before expansion | Pathological exponents/digits rejected before formatting |

## Eleven feature recommendations

| ID | Completed local work | Separate acceptance still needed |
|---|---|---|
| F01 | Quotation page evidence, correction history, listing drafts and role-aware review inbox | Representative real supplier files |
| F02 | Cost codes, accepted cost/accrual, invoice reconciliation, balanced journals, liabilities and revenue | Evidenced opening records for real historical gaps |
| F03 | 7/30/90/project forecasts, shared scope mapping, checked progress and earned-value calculations | Complete dated project inputs; no production forecast guarantee |
| F04 | More trade geometry and finite versioned measurement profiles | Qualified review of supplied standards/rules |
| F05 | Saved sensitivity, maturity evidence and historical estimate comparisons | Professional classification; no automatic AACE class |
| F06 | Contracts, RFQs, bids, awards, certificates, variations, procurement authority/amendments and corrections | Real contract/source acceptance |
| F07 | Margins, aging, retention, working capital, supported ratios and dated reporting FX | Completeness of real accounting inputs |
| F08 | Optional pinned English/Bengali OCR with bounded workers and manual fallback | Representative Bengali/layout accuracy |
| F09 | Reviewed supplier/beneficiary changes, access management and last-Admin protection | Real identity/callback attestations |
| F10 | Installments, credits and separately approved retention release for invoice/certificate payables | Real banking is intentionally absent |
| F11 | Deterministic explanations for quantity, price, estimate, performance and commercial evidence | Live optional model check; no AI approval authority |

## Ten foundation recommendations

| ID | Completed work | Evidence/limit |
|---|---|---|
| A01 | Split routers/services and large frontend workflows | Focused invoice, payment, estimate, price and control modules |
| A02 | Shorten ordinary financial write locks; recheck authority/versions | Hashing/parsing outside ordinary request writers; CLI sample seed runs before serving |
| A03 | Typed errors and authoritative response contracts | Generated OpenAPI/types; original stored audit/receipt bodies preserved |
| A04 | Saved job attempts, leases, heartbeat fencing, retry and restart recovery | Fixture recovery tests; unknown paid submissions held for manual reconciliation |
| A05 | Request IDs, safe diagnostics and actual local workload measurements | No secrets/document bodies in logs; no production-capacity claim |
| A06 | Load routes/charts as needed and enforce an asset budget | Actual gzip measurement exceeds the requested 25% initial reduction |
| A07 | Project-scoped search, filtering, stable sorting and 18 register types | Indexes and synthetic workload checks; broad audit search remains the slow group |
| A08 | Keyboard, modal, contrast, narrow-screen and automated accessibility checks | Real screen-reader/user assessment remains external |
| A09 | Isolated tests/evidence, locked installs and hosted workflow | Actual hosted/platform results are revision-specific, not inferred from YAML |
| A10 | Bound request envelopes, imports, JSON and PDF/OCR resources | Windows child-memory test; not antivirus or full adversarial assessment |

## Twelve interface recommendations

| ID | Completed work | Evidence/limit |
|---|---|---|
| Q01 | Role-specific next steps and disabled-action explanations | Review/approval guidance uses current authority |
| Q02 | Show the parameters/time belonging to displayed prices | Saved search identity, quantity, location and source mode |
| Q03 | Searchable selectors and retained project/user filters | Browser navigation/register search |
| Q04 | Field errors, retry, loading/empty states and failed-edit preservation | Typed errors and read-error retry checks |
| Q05 | Readable secondary text, grouped forms, touch targets and mobile layouts | Automated/narrow-screen scope; real usability review still needed |
| Q06 | Data-table alternatives for cash charts | Same API values supply chart and daily table |
| Q07 | Read-only archived-run navigation | Archived reads pass; writes are denied |
| Q08 | Context-rich exports and safe arithmetic round-trip | Project/revision/currency, components and allowances; imported authority cleared for review |
| Q09 | Review/expiry guidance derived from current records | Five-minute warning; no separate email/SMS service |
| Q10 | First-run guidance and easy sample access | Separate public demo, four documented passwords, private setup unchanged |
| Q11 | Shared draft/error/modal/field and readable evidence components | Focused estimate components and protected audit disclosure |
| Q12 | Accurate guides and safe release tools | Plain-English README/features/guides; isolated recorder, checked artifacts and archive installation |

## Completion evidence

Backend test groups cover stabilization, accounting, cost coding, governance/trades, performance, commercial records, advances, composite forecasts, procurement amendments, corrections, installments, jobs and parser limits. Public-demo tests check all four logins, permissions, repeat startup, conflicts and private defaults. Browser and real HTTP runs supply separate evidence.

The existing migration rehearsal/live upgrade preserved 54 legacy table/column fingerprints and original credentials, balances, receipts and audit history. The documentation/public-demo update needs no new migration. Preservation of the working profile is checked separately.

The recorded synthetic workload contains 2,000 invoices, 500 estimates, 10,000 quotations and 50,000 audit events. Three ten-client runs completed 900 requests without errors. Broad audit contains-search is the slow group. These are local measurements, not a production claim.

A free USD/BDT observation was fetched and persisted with date/provider attribution. Paid providers, real model acceptance, representative documents, professional reviews and human submission retain their own prerequisites.

The presentation, recording and archive have separate render, decode, fingerprint, checksum and installation records. The user authorized publishing to [the GitHub repository](https://github.com/md-ishtiak-ahmed-sajib/buildtrust-ai). Actual remote revisions and hosted status are recorded in the execution evidence. Competition upload remains a separate human action.

## October 20 security extension

The additional 20-item [security review](security-self-assessment.md) covers revocable sessions, offline recovery, persistent admission/provider budgets, secret scanning, private storage, CSP and private backup/restore. The four README passwords remain public-demo-only. New acceptance evidence is recorded separately from the original 42-item review.

## Documentation-first security checkpoint

The next 19-control checklist is distinct from the earlier 20-item review. Both current guides now include six editable security diagrams and readable PDF exports. That historical checkpoint preceded implementation. MFA and request protection are now implemented and verified in the current reports. Native database RLS is deferred while SQLite stays in use; incoming webhooks remain disabled. The four README credentials are unchanged. PDF rendering, page inspection and documentation checks are recorded in the report evidence.

## Accepted MFA and request-security release

The documentation-first checkpoint was published before application changes. Migration 0019 now provides encrypted factors, hashed restricted challenges and recovery codes, current-role session assurance and owner-only reset. Request markers, explicit origin/host checks, strict outbound origins and source-map denial are accepted. The four README passwords and public MFA exemption remain unchanged.

Executed results: 251 backend tests, 10 frontend tests, 20 browser workflows and eight original HTTP scenarios passed. Separate migration/restore and working-profile preservation receipts retain financial history and private credentials. The new 19-control checklist records 17 locally verified controls, native RLS deferred and webhooks not applicable. These results do not replace independent security, real-device or provider acceptance.

The final public-launch check found and corrected a module-entry profile identity issue. The launcher now uses its canonical validated public-profile factory. A regression test and raw public sign-ins prevent test helpers from hiding an unwanted MFA challenge. Fresh Windows public setup and all four browser logins pass without MFA; private privileged accounts still require it.

The first hosted MFA release passed both platform test suites, then the history scanner flagged two diagram SHA-256 checksums in the release manifest. The provenance-only checksum exception now includes Mermaid and SVG files. Full history, current assets and nested historical archives pass with no findings; no credential exception was added and history was retained. The final matching hosted result is recorded in `submission/security-publication.json`.

## Reader-focused documentation refresh

Current submission reports, the README and feature guide now state that application implementation and the security checks are complete for the local judge package. The October 20 hosted run passed Windows and Linux; optional OCR model skips remain explicit. Original logs and historical receipts are retained. External reviews, optional-service checks and human submission steps remain in the remaining-work register.
