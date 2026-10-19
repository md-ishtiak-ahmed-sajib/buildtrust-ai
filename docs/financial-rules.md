# Financial rules

The server makes financial decisions using saved records and fixed rules. Browser numbers and AI explanations cannot authorize payment. See the [glossary](glossary.md) for terms.

## Exact arithmetic

Store money as integer minor units. Return money as decimal strings. Use Decimal and ROUND_HALF_UP: money to two decimal places, published rates/quantities to six. Round each line amount before summing. For example, `1.2345665` publishes as `1.234567`. Preserve exact intermediate values and old approved snapshots.

## Supported quantities

Match project, supplier, item code, specification and compatible units. Tonnes convert to kilograms by multiplying quantity by 1,000 and dividing rate by 1,000. Invoice entitlement does not guess package weight, density or similar product names. Pricing has its own explicit conversion evidence.

```text
Approved scope = BOQ quantity + separately approved quantity variations
Remaining scope = approved scope - existing allocations
Remaining PO = effective ordered quantity - allocations against that PO item
Remaining delivery = confirmed accepted quantity - allocations against that PO item
Supported quantity = max(0, min(remaining scope, remaining PO, remaining delivery))
Verified quantity = min(claimed quantity, supported quantity)
Excess = max(0, claimed quantity - supported quantity)
Variance % = excess / supported quantity × 100, when supported quantity > 0
```

Effective PO quantities include approved retirement events. An amendment cannot retire received, allocated, certified or settled scope. Original PO lines/rates remain in history; replacements use a linked successor PO.

Active unexpired reservations and consumed allocations count. Revalidation excludes the proposal's own reservation. Rejection, expiry, invalidation and terminal failure release live reservations. Analysis alone does not allocate quantities. Each receipt line can support its quantity only once.

## Supported amounts

```text
Claimed line = round(claimed quantity × claimed rate)
Verified line = round(verified quantity × contracted PO rate)
Remaining BOQ value = round(approved scope × approved BOQ rate - allocated values)
Supported line value = min(verified line, remaining BOQ value)
Subtotal = sum(rounded line amounts)
Tax = round(subtotal × explicit PO tax percent / 100)
Retention = round(subtotal × explicit PO retention percent / 100)
Grand total = subtotal + tax - retention - fixed per-invoice discount
```

Headers and line calculations must agree. Rate differences need review even when the claim is lower. An invoice cannot override the PO rate or approve a budget increase. Tax/retention are explicitly zero in the headline samples, not a claim about tax law. Whole-order discount allocation across progress invoices is not implemented.

## Source and supplier checks

An invoice is a claim. BOQ/quantity variations require Admin confirmation; PO/receipts require Manager/Admin confirmation. Supplier/beneficiary changes have their own independently reviewed workflow. Invoice text cannot update the supplier master.

Duplicate checks cover file hash, invoice identity, prior payment, active proposal and receipt use. A duplicate remains a held document rather than a second payable invoice. Projects and archived demo runs have separate identities.

## Cash and reserve

```text
Available cash = recorded cash - other active unexpired cash reservations
Immediate balance = available cash - proposed payment
Daily closing = daily opening + expected inflows - committed outflows
```

The payment gate checks today through today + 29 days in Asia/Dhaka. Overdue unsettled movements fall on the first day. The delayed scenario shifts receivable dates by the policy delay before overdue handling. Cost pressure affects only eligible future costs.

The payment must have enough recorded available cash now. Its immediate balance and every daily balance in both base and delayed scenarios must preserve the reserve. Expected receipts do not become settled cash. Cost-pressure breaches warn. Foreign-currency movements cannot silently supply an FX conversion.

One obligation appears once as scheduled, reserved or settled. Installments reserve only their exact cash amount. The unpaid remainder keeps its recorded date or remains unscheduled. Retention without a release date remains unscheduled.

## Approval and settlement

| Rule | Default |
|---|---|
| Required reserve | BDT 100,000 |
| Finance Manager payment ceiling | BDT 100,000, inclusive |
| Admin payment ceiling | BDT 1,000,000, inclusive |
| Approval validity | 30 minutes |
| Delayed receivables | 15 days |
| Cost-pressure preview | 10% on eligible future costs |

The creator cannot approve. Approval binds the exact amount, currency, supplier, beneficiary, proposal version, sources, policy and expiry. Material changes require fresh validation and approval. Execution rechecks preparer/approver/executor authority, project access, source versions, entitlement, risks and current cash.

Settlement consumes reservations and commits payment, cash, payable, allocations, ledger, receipt and success audit together. Failures roll back money. An identical successful retry returns the original receipt. Conflicting key reuse is rejected. Terminal failed retries retain the original failure. Denied/failed attempts are recorded separately after rollback.

## Accounting, corrections and forecasts

Accepted delivery/work recognizes cost/accrual once. Invoice/certificate reconciliation moves supported accrual into payable and explicit tax/retention/advance accounts. Payment reduces liability and cash. Customer certification records revenue/receivable; collection is a separate event.

A credit can create supplier credit after settlement, but cannot refund cash or release quantities. Financial certificate reversal and accepted-cost correction need separate linked reviews. Cumulative source/code/tax/retention/advance limits apply.

Estimates have separate cost and tender totals. Cost excludes profit, recoverable tax and output tax. Explicit nonrecoverable tax may enter cost; unknown nonzero tax treatment blocks a cost baseline. Approved historical snapshots retain their original meaning.

Shared forecast calculations cover reviewed whole-line/component scope. Reject overlaps, keep unrelated components and contractual rates, apply allowances once, and retain unresolved/stale requirements until fresh review. Estimates and scenarios do not authorize payment.

## Verified fictional examples

| Example | Expected result |
|---|---|
| Steel: 95 vs 80 tonnes at BDT 70,000 | BDT 1,050,000 excess; 18.75%; blocked |
| Cement: 100 bags at BDT 700 | BDT 70,000; cash 1,000,000 → 930,000 once |
| Stress cash: 150,000 less 70,000 | 80,000 below reserve; no payment |
| Installments: 30,000 then 40,000 | Cash 1,000,000 → 970,000 → 930,000; one quantity claim |
| Retention: 66,500 plus approved 3,500 release | Total 70,000 with separate settlement authority |
| Estimate: 20 tonnes at 70,000 → 74,000 | Cost +80,000; forecast 600,000 → 520,000; recorded cash unchanged |

See [accounting details](accounting-and-controls.md), [estimating](estimating-methodology.md) and [actual verification](completion-verification.md).
