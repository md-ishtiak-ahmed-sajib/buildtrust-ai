# Estimating and financial preview methodology

Estimate BOQ lines are versioned worksheet data, separate from approved procurement
BOQ/PO/receipts used by invoice controls. Existing BOQs copy into drafts without being
edited. Each estimate groups revisions by estimate_key and has an optimistic version.

## Rate build-up

Component amount = consumption per work unit × unit price × (1 + material waste/100).
Labour/equipment/subcontract/transport/other components cannot receive material waste.
Sum direct components, then apply site overhead, general overhead, profit, output
work tax and contingency sequentially to the running subtotal, once each. All bases
and amounts are displayed. Procurement tax in a selected material's landed cost is
different from output tax on the finished work: specify the treatment in the Basis
of Estimate and avoid setting a second charge for the same tax obligation.

Analyzed unit rates round HALF_UP to six decimals; quantity × analyzed rate rounds
HALF_UP to integer minor units for each BOQ line. Estimate total sums rounded line
amounts. Browser numbers are display only; server Decimal calculations are authoritative.

Manual rates require a source note before submission. No universal concrete mix,
productivity, wastage or markup is supplied. AACE classification is not automatically
assigned. Record maturity/uncertainty and estimate type in the Basis of Estimate.

## Version/approval lifecycle

DRAFT → SUBMITTED → CHECKED → APPROVED. Submission locks edits and saves a canonical
snapshot of calculation inputs, results, selected-price snapshots, measurement sheets,
material requirements and policy. Its SHA-256 hash is checked again for checking and
approval. Edits to supporting material requirements require fresh selection/revision.
`GET /estimates/{id}/evidence` exposes the retained snapshot and hash validation.

Operator prepares; another Finance Manager checks; a third Admin approves. Admin
cannot approve a version they prepared or checked. Checker activity, current role
and project membership are rechecked before final approval. Approval creates a
separate budget baseline, not a payment/procurement instruction.

Revising a pending submission supersedes it. Revising an approved version retains
that version unchanged. Revisions copy snapshot references rather than refreshing
prices. Choosing a new offer is explicit, audited and optimistic-version protected.

## Cash and budget context

The original project budget is preserved. Cost control shows the latest independently
approved estimate baseline and current draft/approved total. Approved PO line values
are shown before taxes/retention/per-invoice discounts, labeled accordingly. Paid cash
comes from settled payments. Accrual costs/liabilities remain unavailable rather than
being equated with PO or payment totals.

Estimate forecast overlays uncommitted BOQ quantities onto the original 30-day cash
scenarios. A linked approved BOQ item subtracts its already-approved PO quantities.
Each approved BOQ link is unique within the estimate. Contracted quantities keep
their contractual prices. Explicit due dates schedule remaining work; missing dates
are reported as unscheduled costs. Dates outside the 30-day preview are flagged.
Existing cash movements/reservations are retained. No forecast preview changes cash,
payment eligibility, procurement entitlement or an existing approval.

## Demonstration

Admin can create/locate the separate Price & QS Upgrade fictional project from
Materials & Prices. Operator opens BOQ & Estimates and clicks the steel material.
Choose synthetic demonstration mode explicitly, search and select the recommended
74,000 BDT/tonne offer. A cheaper wrong-grade entry remains blocked.

20 t × 70,000 = 1,400,000 BDT; 20 t × 74,000 = 1,480,000 BDT. Difference 80,000.
Opening cash 2,000,000; day-20 planned outflow changes the preview minimum from 600,000
to 520,000; recorded cash remains 2,000,000. Original budget 1,450,000 means a 30,000
overrun warning before a new baseline is approved. No real transfer occurs.

CSV/XLSX exports preserve calculated work-item rates and source references. Imports
create manual component rates from those exported work rates; they do not reconstruct
the original detailed component model. Use version/evidence JSON for full fidelity.
