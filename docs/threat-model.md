# Threat model

## Actors

- A supplier submitting an inflated, duplicate, or manipulated invoice.
- A user with an Operator token trying to approve, execute, alter project scope, or cross project boundaries.
- A malicious document attempting to influence an optional language model.
- An authorized staff member making a mistaken procurement or payment decision.
- A local attacker or database administrator with stronger access than the application.

## Boundaries and mitigations

Supplier claims enter private file storage and an extraction-review boundary. Only authorized confirmation publishes BOQ/PO/receipt facts. Exact item matching, Decimal arithmetic, delivery allocations, supplier fingerprints, and currency checks govern verified values. Human authorization is independent of preparation and binds a specific snapshot. Settlement runs under a serialized transaction with database uniqueness and mandatory idempotency.

Automation can read facts, analyze them, and prepare a proposal. Neither document text nor an LLM can grant a role, approve a proposal, or call settlement. Explicit authenticated API actions perform approval and execution. Browser role-aware controls are convenience only; backend checks remain authoritative.

Cash, ledger, and audit success events share the settlement transaction. Denials and failed attempts are recorded after rollback. Hash-chain verification detects changes relative to retained chain links; an independent checkpoint is still needed against complete rewrite or tail truncation.

## Exclusions

The prototype does not validate a real bank account, verify physical delivery, provide lending advice, defend a compromised operating system, certify legal compliance, or support an Internet-facing multi-tenant service. Its fictional fixtures and simulator intentionally avoid real financial credentials.

See `security-self-assessment.md` for controls, test evidence, and deployment residual risks.
