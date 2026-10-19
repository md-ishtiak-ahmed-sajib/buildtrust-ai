# Who can prepare, check and approve?

The API checks these rules. Hiding a browser button is not the permission boundary. Public demo logins have the same restrictions as private accounts.

| Action | Authority and effect |
|---|---|
| View sources/calculations | Assigned active user; project-scoped access |
| Enter price/estimate/measurement | Operator, Finance Manager or Admin; draft only |
| Confirm supplier quotation | Different Finance Manager/Admin; immutable published observation |
| Approve material equivalence | Independent Finance Manager/Admin with engineering evidence and reason |
| Submit estimate | Preparer locks the version and complete evidence snapshot |
| Check estimate | Different Finance Manager/Admin; unchanged snapshot required |
| Approve estimate/budget | Third independent Admin; current valid checker authority required |
| Prepare/approve/execute payment | Original roles, exact approval binding, BDT limits, liquidity and idempotency |

Estimate approval creates a separate budget baseline. It does not amend procurement BOQs, POs, accepted delivery, beneficiaries or existing commitments. Refreshing prices cannot change an old selection. A new revision supersedes a pending submission; an approved version stays unchanged. Changed sources need fresh review.

Payment defaults remain minimum reserve BDT 100,000, Finance Manager payment ceiling
BDT 100,000, Admin payment ceiling BDT 1,000,000 and 30-minute approval validity.
Both base and 15-day delayed-receivables projections gate payment. Forecast previews,
cost warnings and a new approved estimate do not bypass these deterministic controls.

All transfers remain local simulations. No bank, real card or real funds are connected.
Audit events use the local SHA-256 chain. A full database owner can rewrite it. See [security limits](security-self-assessment.md) and the [glossary](glossary.md).
