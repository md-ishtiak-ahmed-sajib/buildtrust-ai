# API guide

All business routes start with `/api/v1`. Open `/docs` on the running app for interactive details. [Generated OpenAPI](openapi.json) is the full current contract, including exact request/response fields. This guide explains the main routes.

## Login and data

`POST /auth/login` accepts email/password and returns a signed short-lived token. Send `Authorization: Bearer …` on protected requests. `GET /auth/me` reloads current identity. Business resources require current project membership and role; health is public.

Public and private demos use the same login API. Their servers/databases and passwords differ. Public accounts come from the sample fixture; no endpoint grants a role based on a client-supplied value.

Money is a decimal string. Quantities/rates are exact strings; timestamps use UTC and business dates use Asia/Dhaka. Mutable writes use `expected_version` where defined. The server computes amounts.

Errors preserve status, domain code, field details and retry information. Request IDs are returned in headers. Typical statuses: 401 login/session failure, 403 denied authority, 409 stale/conflicting state and 422 invalid input. Stored idempotent receipt/failure bodies are returned unchanged; correlation IDs stay in headers where needed.

## Core workflow

| Area | Main routes |
|---|---|
| System/projects | `GET /health`, `/projects`, `/projects/{id}`, `/projects/archived` |
| Overview | `GET /dashboard/summary?project_id=…` |
| Documents | `GET /documents`, `/documents/{id}`, `/documents/{id}/extraction`; multipart `POST /documents/upload` |
| Corrections/trust | `PATCH /documents/{id}/extraction` with version/data; `POST /documents/{id}/confirm`; `GET /documents/{id}/preview?page=1` |
| Invoices | `GET /invoices`, `/invoices/{id}`, `/invoices/{id}/verification`, `/invoices/{id}/workflows`; `POST /invoices/{id}/analyze` |
| Workflow | `POST /agent/analyze` → 202/ID; `GET /agent/workflows/{id}`; `POST /agent/workflows/{id}/retry` |
| Questions | `POST /agent/ask`, `POST /advanced/ask` |
| Cash | `GET /cashflow/forecast?project_id=…`; scenario parameters preview assumptions, not payment-policy changes |
| Proposals | `GET /payments`; `POST /payments/proposals` with invoice ID; `POST /payables/{id}/installments` |
| Approval/settlement | `POST /payments/{id}/approve`, `/reject`, `/execute`; `GET /payments/{id}/receipt` |
| Audit | `GET /audit/events?project_id=…`, `GET /audit/verify` |
| Demo | Admin-only `POST /demo/reset`; disabled outside demo mode |

Payment `{id}` is the **proposal ID**, including receipt lookup. Execution requires `Idempotency-Key`, not a client amount or beneficiary. Retain a key for retries of the same request; conflicting reuse fails. Identical successful retries return the original receipt. Terminal failed retries preserve their failure result.

## Prices, measurement and estimates

| Area | Main routes |
|---|---|
| Catalogue | `GET/POST /materials`; `GET/PATCH/DELETE /materials/{id}` |
| Search | `GET /prices/providers`; `POST /materials/{id}/prices/refresh` → 202/search ID; `GET /prices/searches/{id}`; `POST /prices/searches/{id}/retry` |
| Comparison/selection | `GET /materials/{id}/prices?search_id=…`; `POST /materials/{id}/prices/preview`, `/select`, `/equivalents` |
| History | `GET /prices/history`; `POST /materials/{id}/history/refresh` |
| Quotations | `GET/POST /quotations`; `PATCH /quotations/{id}`; `POST /quotations/{id}/verify`; multipart `POST /quotations/import`; `GET /quotations/{id}/attachment` |
| FX | `GET/POST /prices/exchange-rates`; `POST /prices/exchange-rates/fetch` |
| Takeoff | `GET /measurement/profiles`; `POST /takeoff/calculate`; `GET/POST /takeoff/sheets`; `POST /takeoff/sheets/{id}/check` |
| Estimates | `GET/POST /estimates`; `GET/PATCH /estimates/{id}`; `POST /estimates/{id}/{submit,check,approve,revise,recalculate}` |
| Estimate evidence | `GET /estimates/{id}/forecast`, `/compare?other_id=…`, `/evidence`, `/export?format=csv|xlsx`; multipart `POST /estimates/{id}/import` |
| Upgrade sample | Admin-only `POST /advanced/demo-project`; `?new_run=true` creates a separate fictional run |

Selection identifies the estimate, line/component, observation and expected version. Preview writes no selection, budget or cash. Selection saves an immutable evidence snapshot. It never updates an approved procurement record.

## Accounting, contracts and operations

| Area | Main routes/behavior |
|---|---|
| Reviewed records | `/controls` with typed payloads and submit/check/approve/reject/revise transitions |
| Accounting | `/accounting/{sources,summary,balances,journals,cost-codes,cost-code-position}` |
| Commercial sources | `/commercial/sources` supplies project-scoped contracts, bids, work acceptances, certificates, POs/BOQs and advances |
| Cost control | `/finance/cost-control?project_id=…` |
| Extended forecast | `/finance/extended-forecast` for 7/30/90/project horizons and selected estimate/contract scope |
| Performance | `/finance/performance` for sourced EVM, ratios, FX and saved forecast context |
| Work/registers | `/work-items`, `/registers/{kind}`, `/operations/attempts` |
| Administration | `/administration/users` and project-membership routes |

Control kinds cover accounting, supplier changes, measurement rules, performance, contracts, procurement and corrections. `PROCUREMENT_AUTHORIZATION` is separate from estimate budgeting. `PROCUREMENT_AMENDMENT` retires eligible scope through a successor PO. `CERTIFICATE_CORRECTION` and `ACCEPTED_COST_CORRECTION` are separate linked reviews. `OBLIGATION_SCHEDULE_CHANGE` updates the canonical schedule and its movement.

`CONTRACT_ESTIMATE_LINK` binds whole lines or components, quantities, source/target offsets, source versions, schedules, retention-release dates and supported advance assignments. Reject overlaps and stale authority. The shared forecast response keeps cost, tax, retention, recovery, cash and unscheduled requirements separate.

Current calculation/source views have explicit response models. Original stored audit, approval and receipt bodies remain historical evidence. Regenerate contracts with `scripts/export_contracts.py` and `npm --prefix frontend run types:api`; check drift before release.


## Account security additions

| Method and route | Access and behavior |
|---|---|
| GET /api/v1/auth/options | Public; exposes only whether password management is available and whether this is the public demo |
| POST /api/v1/auth/logout | Authenticated; revokes the current server session |
| POST /api/v1/auth/password/change | Authenticated private account; current_password and new_password; revokes all affected sessions |
| POST /api/v1/auth/password/reset | Single-use token and new_password; generic invalid/expired response; no email or user ID supplied |
| POST /api/v1/administration/users/{id}/recovery | Current Admin; non-Admin target; returns a token once with its expiry |

Passwords require 12–128 characters. The public demo's fixed accounts reject password changes/recovery. Admin recovery uses the local-owner command. A 401 requires fresh authentication; 403 denies authority, 409 reports a changed record and 429 includes Retry-After. The agent answer also reports model_status without granting financial authority. See generated OpenAPI for exact contracts and [the account guide](account-security.md) for limits.
