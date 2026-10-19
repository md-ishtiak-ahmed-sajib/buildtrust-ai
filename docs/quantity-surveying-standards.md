# Quantity surveying support and limits

The first upgrade provides a calculation-sheet engine, not professional standards
certification or structural design. Default profile: RICS NRM 2, 2021/reissued 2022.
NRM 1/3, CESMM4, PWD/LGED, ICMS 3 and project rules are registered as contextual
profiles. Their copyrighted clause tables and deduction thresholds are not bundled.
Every profile is visibly REQUIRES_PROFESSIONAL_REVIEW.

ICMS 3 is a cost/reporting classification and cannot be chosen as a takeoff rule.
Profile edition, source, rule register, verification status and explicit assumptions
are retained in each saved measurement result. Checking geometry does not upgrade
a profile to certified standards compliance.

## Implemented geometry-v1

| Calculation | Formula / output |
|---|---|
| Rectangular concrete | L × B × H × count, m³ |
| Circular concrete | π × D² / 4 × H × count, m³ |
| Area / finishes | L × B × count, m² |
| Pipe/cable length | L × count, m |
| Count | Whole item count, each |
| Column/footing formwork | 2 × (L+B) × H × count, four sides, m² |
| Beam formwork | (2 × depth + width) × length × count, sides/soffit, m² |
| Slab formwork | L × B × count, soffit only, m² |
| Reinforcement | Supplied bar length × count × kg/m, kg |

Length inputs support m/mm/cm/ft. Bar diameter is explicitly millimetres. Rebar kg/m
can use D²/162 (labeled approximation), sourced specified nominal mass, or explicit
steel density with circular section. No laps, bends, hooks, cover or anchorage are
invented. Supply approved design/bar-bending lengths. No adequacy conclusion follows
from a calculated mass.

Quantities use Decimal and output six decimals. Dimensions must be positive, counts
whole, and deductions nonnegative/not greater than gross. Deduction is supplied in
output units with a required reason. There is no universal opening deduction or
waste percentage. Save drawing/revision, element/location and assumptions; a different
Finance Manager/Admin checks the immutable sheet. A linked BOQ quantity must match
the saved sheet after dimensional conversion. Checked sheets have no edit endpoint;
save a new sheet for changed design inputs.

Remaining trade templates, standard-specific clause verification, excavation bulking,
complex stairs, BBS cutting-length derivation and detailed masonry deduction rules
belong to later releases. References:
https://www.rics.org/profession-standards/rics-standards-and-guidance/sector-standards/construction-standards/nrm
https://ice.org.uk/areas-of-interest/infrastructure-delivery/civil-engineering-standard-measurement
https://icms-coalition.org/the-standard/
