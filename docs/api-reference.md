# API reference

Base path: `/api/v1`. The running interactive reference is `/docs`; `openapi.json` is exported from the implementation, not hand-written. Frontend generated contracts are produced with `npm --prefix frontend run types:api`.

## Estimating upgrade endpoints

| Area | Routes |
|---|---|
| Material catalogue | `GET/POST /materials`, `GET/PATCH/DELETE /materials/{id}`; project-scoped specifications, versions and archive |
| Price comparison | `GET /prices/providers`, `POST /materials/{id}/prices/refresh` → 202 search ID, `GET /prices/searches/{id}`, `POST /prices/searches/{id}/retry`, `GET /materials/{id}/prices?search_id=…` |
| Rate evidence | `POST /materials/{id}/prices/preview`, `POST /materials/{id}/prices/select`, `POST /materials/{id}/equivalents`, `GET /prices/history?project_id=…` |
| Quotations/schedules | `GET/POST /quotations`, `PATCH /quotations/{id}`, `POST /quotations/{id}/verify`, multipart `POST /quotations/import`, `GET /quotations/{id}/attachment` |
| Exchange rates | `GET/POST /prices/exchange-rates`, `POST /prices/exchange-rates/fetch` |
| Measurement | `GET /measurement/profiles`, `POST /takeoff/calculate`, `GET/POST /takeoff/sheets`, `POST /takeoff/sheets/{id}/check` |
| Estimates | `GET/POST /estimates`, `GET/PATCH /estimates/{id}`, `POST /estimates/{id}/{submit,check,approve,revise,recalculate}` |
| Estimate analysis | `GET /estimates/{id}/forecast`, `/compare?other_id=…`, `/evidence`, `/export?format=csv|xlsx`; multipart `POST /estimates/{id}/import` |
| Finance/copilot | `GET /finance/cost-control?project_id=…`, `POST /advanced/ask` |
| Safe demo | Admin-only `POST /advanced/demo-project`, available only in demo mode |

Writes carry `expected_version` where applicable. Price selection identifies the
estimate, line, component, observation and optionally search. The server calculates
amounts. A preview writes no selection, estimate, budget or cash. Selection persists
an immutable snapshot. Catalogue/evidence changes invalidate pending approval hashes.
New resources enforce current database roles and memberships using the original
authentication mechanism. Full request/response schemas are in generated OpenAPI.

## Authentication and responses

`POST /auth/login` accepts `email` and `password`, returning a short-lived bearer token and the database-authoritative user/limit. Use `Authorization: Bearer …` for protected endpoints. `GET /auth/me` reloads identity. Health is public; business resources require project membership.

Money is represented by decimal strings (for example `"70000.00"`). Timestamp strings are UTC `Z`; business schedules use dates. Errors are structured as `{"error":{"code":"…","message":"…"}}`. Validation errors add field locations without echoing passwords or internal traceback details.

Important status codes: 401 unauthenticated, 403 forbidden/limit violation, 404 unavailable resource, 409 conflicting identity/state/snapshot, 413 upload too large, 415 unsupported/signature mismatch, 422 invalid fields, 429 login rate limit, and 503 transient storage or simulated settlement failure.

## Endpoint groups

| Group | Endpoints and behavior |
|---|---|
| System | `GET /health`, `POST /auth/login`, `GET /auth/me` |
| Projects | `GET /projects`, `GET /projects/{id}`; assigned active projects, balance, and fictional supplier fingerprints |
| Overview | `GET /dashboard/summary?project_id=…`; persisted financial metrics, trend, and recent events |
| Documents | `POST /documents/upload` multipart `project_id` + `file`; `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/extraction` |
| Document trust | `PATCH /documents/{id}/extraction` with `{version,data}`; `POST /documents/{id}/confirm`; `GET /documents/{id}/preview?page=1` |
| Invoices | `GET /invoices`, `GET /invoices/{id}`, `POST /invoices/{id}/analyze`, `GET /invoices/{id}/verification`, `GET /invoices/{id}/workflows` |
| Cash | `GET /cashflow/forecast?project_id=…&delay_days=15&cost_pressure_percent=10`; scenario preview does not modify policy |
| Proposals | `GET /payments`, `POST /payments/proposals` with `{invoice_id}` |
| Authorization | `POST /payments/{id}/approve`, `POST /payments/{id}/reject` |
| Simulation | `POST /payments/{id}/execute` with required `Idempotency-Key`; `GET /payments/{id}/receipt` |
| Workflow | `POST /agent/analyze` with `{invoice_id}` returns 202 and workflow ID; `GET /agent/workflows/{id}`; `POST /agent/workflows/{id}/retry` |
| Questions | `POST /agent/ask` with `{project_id,invoice_id?,question}` |
| Audit | `GET /audit/events?project_id=…&limit=200`, `GET /audit/verify` |
| Demo | `POST /demo/reset`; Admin only, unavailable when demo mode is false |

`{id}` under `/payments` always refers to the **proposal ID**, including receipt retrieval. An execute request supplies no amount or beneficiary; those come from the approved snapshot. Use a new key for a genuinely new request and retain the same key across network retries of the same request. Keys reused for different proposals conflict. Successful retries return the stored original receipt; terminal failed retries preserve the original failure.

## Source trust

Invoice imports register claims. Procurement imports remain untrusted until role-authorized confirmation. The correction endpoint uses an optimistic version check and retains provenance. Confirmed procurement evidence is immutable; BOQ extensions use separately authorized variation documents. A duplicate upload remains a held document instead of becoming a second payable invoice.


## Current controlled extensions

All paths below retain the `/api/v1` prefix and current project/role access checks. Generated [OpenAPI](openapi.json) is the complete route/field contract.

- `/controls`: prepare typed accounting, governance, commercial and performance records; independent `/submit`, `/check`, `/approve`, `/reject` and permitted `/revise` transitions use expected versions.
- `/accounting/{sources,summary,balances,journals,cost-codes,cost-code-position}`: original source lineage, recognized accounting and reconciled cost positions.
- `/payables/{id}/installments`: prepare an exact installment against a current balance. Existing payment approval/execution/receipt routes remain authoritative.
- `/commercial/sources`: authenticated options for contracts, RFQs, verified quotation bids, work acceptances, cumulative certificates and source advances.
- Control kinds `ADVANCE_ASSIGNMENT` and `CONTRACT_ESTIMATE_LINK`: independently bind contract advances and exact direct-cost forecast mappings. Their approval creates no payment authority.
- `/finance/extended-forecast`: 7/30/90/project-duration scenarios; optional `estimate_id`, `use_project_schedule` and `use_contract_links`. `/finance/performance`: EVM, accounting-derived ratios, reporting FX and preserved forecast snapshots with current-source status.
- `/materials/{id}/history/refresh`: append-only approved purchasing/settlement context. Existing `/prices/history` still returns immutable selections.
- `/work-items`, `/registers/{kind}`, `/operations/attempts`, `/projects/archived`: review/expiry state, paginated evidence, durable attempts and read-only archived runs.
- `/administration/users` and project-membership interfaces: local independent reviewers with current authority and last-Admin protections.

Typed error envelopes carry domain codes/fields and retry information. Per-request `X-Request-ID` stays in headers where a stored idempotent terminal-failure body must remain identical. Invalid fields return 422, stale state 409, denied authority 403. No request may supply its own settlement amount, beneficiary or approval authority.


## Completion-release additions

`POST /controls` accepts independently reviewed `PROCUREMENT_AUTHORIZATION`, `PROCUREMENT_AMENDMENT`, `CERTIFICATE_CORRECTION`, `ACCEPTED_COST_CORRECTION` and `OBLIGATION_SCHEDULE_CHANGE` payloads. Current source versions come from project-scoped source/balance interfaces. Submit/check/approve binds the source snapshot; conflicts return 409. Procurement authorization does not alter an estimate baseline. A financial reversal does not release physical entitlement or refund cash.

`CONTRACT_ESTIMATE_LINK` supports `component_id`, allocated quantity, explicit source/target offsets, optional supersession, quantity/date schedules, retention-release dates and approved advance assignments. The backend rejects unsupported or overlapping scope. Estimate and extended previews share calculated overlays with distinct project cost, tax, retention, recovery and cash fields. Unscheduled commitments remain separate from dated movements.

Additive `/registers/{kind}` pages cover growing accounting, commercial and procurement records with project scope, search/status, stable order and paging. Original list endpoints remain available. `POST /advanced/demo-project?new_run=true` creates an explicitly fictional separate run; the default reuses the current fictional project and returns its estimate/material identities.

Current financial calculation and source views use explicit response models. Original stored audit/approval/receipt payloads remain unchanged historical evidence. Exported OpenAPI and generated frontend contracts pass drift verification.
