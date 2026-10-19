# Estimates and forecast previews

An estimate is a planning worksheet. It is separate from approved procurement records used to authorize invoices. Copying a BOQ into an estimate does not edit that original BOQ.

## Rate calculation

```text
Component = consumption per work unit × unit price × (1 + material waste / 100)
Direct rate = sum of supported component amounts
Line amount = round(quantity × published analyzed unit rate)
Estimate total = sum of rounded line amounts
```

Material waste applies only to material components. Labour, equipment, subcontract, transport and other components do not receive it. Site overhead, general overhead, profit, output tax and contingency follow the saved sequential calculation bases. The response shows every basis and amount so a charge is not applied twice.

Rates/quantities publish to six decimals and line money to two using ROUND_HALF_UP. Browser numbers do not control saved totals. Manual rates need a source note. No universal concrete mix, productivity, waste or markup is supplied.

## Cost and selling price

The legacy `total` remains the tender/selling total. `cost_total` and `tender_total` are explicit. Cost excludes profit, recoverable tax and output tax. Nonrecoverable tax can be cost when explicitly recorded. Unknown nonzero tax treatment blocks a cost baseline.

Material purchase tax and output tax on work are different obligations. Record their treatment in the Basis of Estimate and do not charge the same tax twice. Approved historical snapshots retain their meaning.

## Independent approval

```mermaid
flowchart LR
  Draft[Draft and evidence] --> Submit[Locked submission]
  Submit --> Check[Different Manager checks]
  Check --> Approve[Separate Admin approves]
  Approve --> Baseline[Immutable budget baseline]
```

Every contributor to retained content remains part of the approval evidence, including imports, price selections and inherited revisions. Contributors cannot independently check or approve their work. Current checker authority and project access are rechecked.

Submission saves quantities, rate calculations, sources, selections, sheets, assumptions, policy and contributors in a hashed snapshot. Source/material changes require fresh review. Revise to change an approved version; the approved record stays unchanged. A pending revision supersedes the old submission. Refreshing prices never replaces a historical selection.

## Commitments and forecast

Show original budget, approved cost baseline, current estimate, commitments, recognized costs and paid cash separately. Do not treat a PO or payment as actual cost recognition.

Explicit compatible BOQ-to-PO coverage prevents already committed quantities being estimated again. Match project, specification, units, currency, quantities and source versions. Incompatible, stale or unresolved coverage cannot hide costs.

The shared forecast service schedules uncommitted quantities only where dates exist. Contract mappings may cover whole lines or specific components with disjoint source/target scope. Keep unrelated labour and other components unchanged. Contract rates remain authoritative until separate procurement approval changes them. Apply allowances/tax once. Retention and advances remain separate from cost.

Unknown dates stay unscheduled. Existing obligations and installments appear once. The preview cannot move cash, amend a PO or authorize payment. The original 30-day payment gate still applies.

## Verified fictional example

| Quantity and rate | Estimate | Forecast cash |
|---|---:|---:|
| 20 tonnes × BDT 70,000 | BDT 1,400,000 | BDT 600,000 |
| 20 tonnes × BDT 74,000 | BDT 1,480,000 | BDT 520,000 |

Opening/recorded cash stays BDT 2,000,000. Cost rises by BDT 80,000. The original BDT 1,450,000 budget shows a BDT 30,000 warning after selection. This sample uses explicit zero tax, retention and markup and schedules the uncommitted purchase on day 20.

## Imports, exports and maturity

Version-2 CSV/XLSX exports keep context, components and allowance settings. Reimport preserves arithmetic but clears material/selection authority for review. External flat rates become manual final rates with zero inherited allowances. Use saved evidence for full original approval provenance.

Record estimate type, inclusions, exclusions, uncertainty and maturity evidence. Historical comparisons flag changed specifications. A project label does not establish an AACE class. See [price sources](price-source-integrations.md), [measurement rules](quantity-surveying-standards.md) and [actual checks](completion-verification.md).
