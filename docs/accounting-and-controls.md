# Accounting and commercial controls

The app separates estimated cost, contractual commitments, accepted cost, liabilities, revenue and cash. These records are related, but they are not interchangeable. All money movements are simulated.

## Independent review

An Operator prepares and submits a control. A different Finance Manager checks it. A separate Admin approves it. Retained contributors cannot review their own work. Submitted records are locked. Approval binds content, source versions, calculations, contributors and evidence. Current roles and project access are checked again before publication.

Approved records are corrected through supported linked events, not rewritten. Journals and approval audit commit together. Settlement also commits cash, payable changes, reservations, ledger and receipt atomically.

## Recognition and cash

| Event | Debit | Credit | Cash effect |
|---|---|---|---|
| Approved accepted cost | Project cost | Accrued liability | None |
| Exact invoice reconciliation | Supported accrual; explicit tax asset where applicable | Payable/retention and recorded adjustments | None |
| Supplier payment | Payable | Cash | Decrease |
| Customer certificate | Receivable/held retention | Revenue and explicit output tax | None |
| Customer receipt | Cash | Receivable | Increase |

Every journal balances in integer minor units. Source keys prevent duplicate posting. Explicit cost codes connect budgets, POs, acceptances, invoices, journals and reports. Historical gaps require reviewed opening journals with source evidence and dates. Opening journals do not invent dates or silently change existing cash.

An accepted source may be split across invoices using bounded recognition allocations. All claimed quantities and amounts must reconcile. The final allocation receives rounding residue. A source already used by a supplier certificate cannot also fund an invoice.

## Installments, credit and retention

A reconciled invoice claims accepted delivery quantities once. Installments do not claim them again. One active installment proposal may exist for the payable. Each installment binds an expected payable version, exact amount and separate approval.

The original invoice proposal route pays the full remaining supported balance. Legacy invoices without a recognized payable retain their previous full-payment behavior. Settlement stays unique per proposal; aggregate payable controls prevent overpayment. Migration 0008 preserved original IDs and receipt bodies while changing invoice-wide uniqueness.

Reservations cover only installment cash. The unpaid remainder keeps its due date or remains unscheduled. Expiry, authority changes and invalidation release live reservations. Failure rolls back all financial effects.

Credits reduce unpaid balances; excess becomes supplier credit. A credit never automatically refunds cash or frees physical quantity. Tax-bearing credits need explicit source/tax/retention allocation. Retention release needs separate approval and creates a balance requiring its own payment proposal.

## Contracts, procurement and certificates

Contracts record customer/supplier direction, currency, scope, rates, codes, tax, retention, advance recovery and payment conditions. RFQs are local records; the app sends no supplier messages.

Bids need independently verified quotations, suitable specifications/units, known costs, valid dates and matching suppliers. Public listings and synthetic offers cannot be awarded. Recommendations retain alternatives and the human choice reason. Single-source comparisons remain labelled.

An approved award creates a linked confirmed PO within separately approved procurement quantity/value authority. Estimate budget approval alone is not procurement authority. Variations retain claimed/reviewed/approved quantity, rate, value, reason and time impact. Accepted/certified/committed rates stay protected.

Checked measurements support work acceptance and recognize cost once. Supplier certificates clear supported acceptance accrual into payable/retention/tax/advance accounts. Customer certificates recognize revenue and receivables. Cumulative/previous/current work and materials-on-site evidence remain visible. Unique source allocations prevent repeated recognition.

Advance assignments link reviewed opening advance journals to one contract/counterparty. Assigned/recovered amounts cannot exceed supported balances. Assignment itself does not move cash.

## Protected PO amendments

Procurement authorization controls approved scope separately from an estimate budget. An amendment needs independent checking and Admin approval. It retires only eligible unreceived quantities and publishes replacements in a linked successor PO.

Original PO lines and rates remain unchanged. Received, allocated, certified and settled quantities cannot be retired or repriced. Entitlement, coverage, cost reports and forecasts all use effective quantities. A material approved change invalidates affected pending payments and releases reservations, without changing past settlements.

## Separate corrections

A source-linked certificate correction posts compensating journals. Supplier reversal restores supported accrual or supplier credit. Customer reversal reduces revenue/receivable or creates customer credit. Neither refunds cash or creates negative receivables.

Accepted base cost stays unchanged until a separate linked accepted-cost correction has evidence and independent approval. Cumulative corrections are bounded by original source, cost code, tax, retention, advance and prior allocations. Physical entitlement is not released by a financial correction.

Example: reversing BDT 10,000 of a BDT 70,000 supplier certificate leaves accepted base cost at 70,000. A separately approved supported cost correction reduces cost to 60,000. Settled cash remains unchanged.

## Shared forecasts and performance

Approved contract mappings can cover complete BOQ lines or named rate components. They save source/target quantities and offsets, conversions, source hashes and dated segments. Overlap is rejected. Unmapped components keep estimate assumptions; mapped portions use supported contract terms. Allowances and tax apply once.

Recoverable/output tax, retention, advance recovery, cost and cash stay separate. Missing payment/release dates remain unscheduled. Existing obligations/installments appear once. Stale mappings retain estimated requirements and need fresh review. Updating an approved obligation schedule updates its linked movement consistently.

Performance baselines bind cost BAC and dated PV. Checked progress supplies EV. AC comes from recognized cost journals, not payments. Missing inputs and zero denominators remain unavailable.

```text
CV = EV - AC                  SV = EV - PV
CPI = EV / AC                 SPI = EV / PV
EAC remaining-at-budget = AC + BAC - EV
EAC CPI-based = BAC / CPI
EAC combined = AC + (BAC - EV) / (CPI × SPI)
EAC bottom-up = AC + sourced remaining cost
ETC = EAC - AC                VAC = BAC - EAC
```

TCPI uses the selected supported completion target and displays its basis. Reporting FX uses dated evidence and never changes settlement currency. Non-BDT payment authority needs a supported BDT conversion.

## Evidence, operations and limits

Exports retain project, revision, state, currency, components, allowance settings and calculation basis. Reimport preserves arithmetic but clears imported material/price-selection authority for review. Flat external rates are final manual rates; allowances are not silently added twice.

Jobs keep leases, attempts, bounded retries and restart recovery. Unknown paid submissions stay held. The supported runtime is one local process. Actual load measurements exist, but do not establish production capacity. See [technical details](technical-documentation.md), [verification](completion-verification.md) and [remaining prerequisites](../prompt/Not%20implemented.md).
