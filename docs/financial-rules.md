# Financial rules

All authoritative calculations run in Python. Monetary inputs are decimal strings, amounts are quantized using Decimal `ROUND_HALF_UP` to BDT 0.01, and SQLite stores monetary minor units as integers. No binary floating-point value is accepted as an authoritative monetary/quantity input. UI chart conversion is presentation only.

## Quantities and rates

Supported canonical units are kg, bag, each, m2, and m3. `t`, `tonne`, `tonnes`, and `metric tonnes` convert to kg by multiplying quantities by 1,000 and dividing rates by 1,000. Kilogram aliases, bags, and pcs are normalized explicitly. No bag-to-kg, volume-to-mass, specification, or fuzzy product-name conversion is assumed.

For each exact item/specification:

```text
Approved scope = BOQ quantity + separately Admin-approved variation quantities
Remaining BOQ quantity = approved scope - allocations across the project item
Remaining PO quantity = ordered quantity - allocations against that PO item
Remaining accepted quantity = confirmed accepted receipts - allocations against that PO item
Supported entitlement = max(0, min(remaining BOQ, remaining PO, remaining accepted))
Verified quantity = min(current claimed quantity, supported entitlement)
Excess quantity = max(0, claimed quantity - supported entitlement)
Quantity variance % = excess / supported entitlement × 100, when entitlement > 0
```

Only active unexpired proposal allocations and consumed settled allocations count. The proposal being revalidated excludes its own allocations. Rejected, failed, and expired allocations are released. Reanalysis does not create allocations.

Confirmed receipt quantities are allocated by receipt-line ID in deterministic order under the proposal write transaction. Different invoices cannot reserve the same accepted quantity. The PO and BOQ limits still apply even if multiple receipts exist.

## Invoice amounts and approved value

```text
Claimed line calculation = round(claimed quantity × claimed rate)
Verified line amount = round(verified quantity × contracted PO rate)
Remaining BOQ value = round(approved scope × approved BOQ rate - prior allocated values)
Supported line value = min(verified line amount, remaining BOQ value)
Subtotal = sum(rounded line amounts)
Tax = round(subtotal × explicit PO tax percent / 100)
Retention = round(subtotal × explicit PO retention percent / 100)
Grand total = subtotal + tax - retention - fixed per-invoice contractual discount
```

Claimed headers and line amounts must agree exactly after rounding. Rate differences require review even if a supplier claims less. A value above the remaining BOQ budget requires an approved change; no unapproved increase is inferred. The MVP variation import extends approved quantities at the BOQ rate. A negotiated rate revision requires a separately supported implementation, not an invoice override.

Zero tax/retention is an explicit fictional demonstration assumption, not a statement about applicable tax law. Fixed discounts apply per invoice under the recorded PO terms. Order-wide discount apportionment over progress invoices remains unsupported. Separately approved retention releases now create an additional payable balance and require their own payment approval.

## Supplier, duplication, and source trust

Supplier IDs, PO supplier, project, currency, and approved beneficiary fingerprint must agree. Invoice beneficiary text cannot update the master. Unknown suppliers and beneficiary changes block execution. Supplier-master changes now require evidence, independent checking and a separate Admin approval; a blocked invoice cannot override beneficiary authority.

Duplicate controls check raw document hash, project/supplier/invoice identity, prior settlements, active proposals, and receipt allocations. Duplicate uploads are retained as held documents without creating a second invoice. Each project is an independent financial scope; reset creates new project identities and preserves previous evidence.

## Liquidity

```text
Available cash = recorded cash balance - other active unexpired cash reservations
Cash immediately after proposed payment = available cash - proposed payment
Daily closing = daily opening + recorded expected inflows - committed outflows
```

Forecast horizon: today through today + 29 days, using Asia/Dhaka business dates. Overdue unsettled movements are placed on the first day. A delayed-receivables scenario moves inflow due dates by the configured delay before checking overdue handling. Cost pressure increases only flagged future outflows; it does not rewrite recorded cash or liabilities.

Each linked invoice obligation is counted once: as a scheduled obligation, a reserved proposal, or a settled movement. A current proposal is removed from other-reservation totals and applied once. Receivables are assumptions, never available settled cash.

Eligibility requires available cash to cover the payment, the immediate post-payment balance to preserve the reserve, and every projected day in both base and policy-delayed scenarios to preserve it. Cost-pressure breaches warn. Foreign-currency cash movements block the project assessment rather than silently supplying FX conversions.

## Approval and settlement

Operator prepares; Finance Manager approves/executes up to BDT 100,000; Admin approves/executes up to the configured ceiling (BDT 1,000,000 by default). Auditor is read-only. Limits are inclusive. The creator cannot approve their proposal. Every settlement needs a distinct account's exact, unexpired approval.

Default approval validity is 30 minutes. The snapshot includes amount, currency, supplier, beneficiary, proposal version, expiry, source content/versions, and policy inputs. Material changes invalidate approval. Current cash, current allocations, financial findings, executor authority, and approving-account authority are checked again at execution.

Reservations reduce spendable availability but never debit the ledger. Settlement consumes them, deducts recorded cash once, records a cash credit and payable debit, marks linked obligations settled, and writes a mock receipt atomically. Failures roll back all monetary effects. Identical successful retries return the same receipt; a key used for another request is rejected. A terminal failure remains a failure on replay.

## Independent headline examples

- Steel: 95 tonnes × BDT 70,000 = BDT 6,650,000 claimed; 80 tonnes × BDT 70,000 = BDT 5,600,000 supported; excess BDT 1,050,000; 15 / 80 = 18.75%.
- Valid cement: 100 bags × BDT 700 = BDT 70,000; BDT 1,000,000 opening cash becomes BDT 930,000 once.
- Liquidity stress: BDT 150,000 - BDT 70,000 = BDT 80,000, below the BDT 100,000 reserve; no settlement.

## Reviewed accounting and installments

Accepted cost debits project cost and credits accrued liability once. Exact invoice reconciliation moves that liability to AP/retention without recognizing original cost again; explicit tax treatment separates tax accounts. Historical recognition dates are not reconstructed automatically.

A reconciled invoice claims physical entitlement once. Each installment reserves its exact cash and requires independent approval. Unpaid amounts retain their actual scheduled date, or remain unscheduled. BDT 30,000 then 40,000 moves opening cash from 1,000,000 to 970,000 and 930,000. Separate 66,500 net payment and 3,500 retention release total 70,000. Excess credits become supplier credit without automatic refund or quantity release.

New cost totals exclude profit/recoverable/output tax; unknown nonzero tax treatment blocks a cost baseline. Legacy approved snapshots retain their meaning. EVM uses approved cost BAC, dated PV, checked EV and recognized AC. Formula details and remaining allocation/certification limits are in [accounting-and-controls.md](accounting-and-controls.md).


## Completion release: explicit scopes, amendments and corrections

Migrations 0015–0017 add immutable procurement authorization/amendment relations, receivable correction balances and project-scoped query indexes. A populated-copy rehearsal and live upgrade preserve 54 legacy table/column fingerprints, credentials, original receipts and audit history. Original audit payloads and stored receipt bodies retain their exact historical schema; current authoritative calculation/source views have explicit response contracts and generated frontend types.

`forecasting.py` is the shared estimate/extended cash-overlay service. Whole-item or specific-component allocations retain quantity/unit conversions, disjoint intervals, source hashes, calculation policy, dated segments, tax treatment, retention and sourced advance recovery. Whole-item contracts include their complete scope; component mappings apply estimate overhead/contingency once and contract tax once. Unmapped components retain estimate assumptions; profit and output tax do not become project cost. Missing cash or retention-release dates remain unscheduled. Changed sources retain estimated requirements until fresh review. Existing invoice/certificate obligations and exact installments remain canonical; unrecognized PO exposure and held retention appear separately without fabricated dates.

Procurement value/quantity authorization is separate from estimate budgeting. An independently checked and Admin-approved PO amendment appends retirement events for eligible unreceived scope, then publishes a successor PO. It cannot rewrite original lines/rates or retire received, allocated, certified or settled scope. Entitlement, coverage, cost control and forecasts use effective quantities. Material procurement/supplier/authority changes invalidate affected pending approvals and release live reservations.

Source-linked certificate reversals post compensating financial journals and adjust payable/receivable or supplier/customer credit balances. They never refund cash. A separate linked accepted-cost correction reverses supported cost/accrual without releasing physical quantity. Cumulative source, cost-code, tax, retention, advance and previous-correction limits are checked under the same serialized approval boundary.

The estimate page now delegates BOQ display, measurement/rate editing, basis/allowances and forecast presentation to focused components. Read failures retain request/field/retry details; loading retries preserve the workspace, and failed edits stay available for correction. Paginated registers cover growing accounting and commercial records alongside the original lists.

See [completion-verification.md](completion-verification.md) for actual test results, local workload limitations and separately outstanding external verification.
