> Historical plan. Some features described below as future work now exist. Read [current features](../features.md), [the implementation ledger](all-suggestions-implementation.md) and [remaining tasks](../docs/remaining-work.md) for today's status. This original plan is preserved as background.

# Advanced upgrade implementation plan

The accepted first release adds material price intelligence, core quantity takeoff,
versioned estimates and financial previews to the existing application. The full
approved implementation plan is the specification. Existing invoice/payment controls remain authoritative.

## Integration and dependency map

- Existing authentication, project memberships, transactions and audit chain are reused.
- New feature routers → pricing/measurement/estimating services → additive records
  sharing the existing SQLAlchemy Base. The existing `models.py` remains a module.
- Estimate BOQ copies optionally reference approved procurement BOQ rows; editing an
  estimate never updates procurement, supplier beneficiaries or settled cash.
- Immutable observations → immutable selections → versioned rate analysis → draft
  estimate → independent checking → Admin approval → separate budget baseline.
- Forecast previews layer scheduled, uncommitted quantities onto existing cash flow.
  Missing dates remain unscheduled. Payment eligibility retains the original policy.

## Implementation gates

1. Backup SQLite using its online backup API; migrate additive tables and test recovery.
2. Provider adapters, typed imports, matching, normalization and truthful source states.
3. Persistent price selection, BOQ/rate analysis, revision locking and independent approval.
4. Concrete/rebar/formwork/generic measurement sheets and financial previews.
5. Functional React pages, API contracts, regression and browser tests, Windows startup.

## Interfaces and migration risks

New `/api/v1` routers cover materials, prices/searches, quotations, exchange rates,
measurement, estimates and finance previews. Requests remain project scoped. API
credentials stay server-side. Search tasks persist remote IDs; uncertain paid submissions
are not retried automatically. Unknown quote costs remain unknown.

All migrations are additive, with no rewriting of existing users, payments, approvals,
balances or audit records. Data import and approved procurement remain separate from
estimating. New records use exact decimal strings, integer money totals and explicit
optimistic versions. Existing main/API contracts remain compatible.

## Validation and delivery boundaries

The pre-upgrade planning baseline was 61 backend tests and 6 frontend tests, with a
passing frontend build. Run them again alongside the 30 upgrade test categories and
real browser/API integration checks. Fixtures do not prove live market connectivity.
Live checks await locally configured keys. Advanced trades, EVM, RFQ/certification and
accrual modules are later releases. Do not modify submission media/archive/evidence
files without a separate user request.
