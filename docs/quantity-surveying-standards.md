# Quantity surveying: support and limits

The app calculates supplied quantities. It does not design structures or certify a professional measurement standard. See [the glossary](glossary.md).

## Available calculations

| Calculation | Basis and output |
|---|---|
| Rectangular concrete | Length × breadth × height × count, m³ |
| Circular concrete | π × diameter² / 4 × height × count, m³ |
| Triangular prism / frustum / annular volume | Supplied geometric dimensions, m³ |
| Area / length / count | Supplied dimensions and whole count, m² / m / each |
| Column/footing formwork | Four side contact areas, m² |
| Beam formwork | Two sides and soffit, m² |
| Slab formwork | Soffit, m² |
| Reinforcement and supplied schedules | Length × count × supported nominal mass, kg |
| Earthwork/backfill/disposal/compaction | Supplied geometry and explicit factors, m³ |
| Masonry/openings/finishes | Supplied wall/area dimensions and supported deductions |
| Doors/windows/roofing/pavement | Supplied sizes, quantities, thickness/slope where required |

Lengths support m, mm, cm and ft. Bar diameter is in millimetres. Reinforcement mass can use sourced nominal kg/m, explicit density or `D²/162`, clearly labelled an approximation. No laps, hooks, cover, anchorage or design adequacy is inferred. Supply reviewed schedule lengths.

Quantities publish to six decimals using ROUND_HALF_UP. Dimensions must be positive, counts whole and deductions supported and bounded by gross quantity. Retain drawing/revision, element/location, assumptions, preparer and checker. Changed inputs invalidate old displayed results. Checked sheets are immutable; save a new sheet for a changed design.

## Profiles and professional review

NRM 2 is the default measurement context. NRM 1/3, CESMM4, PWD/LGED and project profiles retain edition/source information. ICMS is a reporting classification, not a detailed takeoff method.

Baseline profiles visibly require professional review. A project profile may enable only recorded deterministic templates and explicit opening rules after evidence, independent checking and approval. Uploaded rule text cannot execute arbitrary code. Approval covers the recorded rule and scope, not every clause of a published standard.

Copyrighted clause tables and universal deduction thresholds are not bundled. Complex design-derived lengths, unprovided special geometry and unreviewed trade conventions remain outside automatic inference.

References: [RICS NRM](https://www.rics.org/profession-standards/rics-standards-and-guidance/sector-standards/construction-standards/nrm), [ICMS](https://icms-coalition.org/the-standard/). See [the rule register](measurement-rule-register.md) and [remaining professional acceptance](../prompt/Not%20implemented.md).
