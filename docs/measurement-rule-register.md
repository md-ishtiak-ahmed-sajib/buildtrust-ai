# Implemented measurement rule register

Saved sheets retain the chosen profile edition, source and assumptions. These rules
are generic geometry-v1, not independently verified NRM/CESMM clauses. There are no
bundled copyrighted tables or universal deduction thresholds.

| Rule | Scope | Output |
|---|---|---|
| RECTANGULAR_VOLUME | Explicit L/B/H/count | m3 |
| CIRCULAR_VOLUME | Explicit diameter/height/count | m3 |
| REBAR | Supplied lengths/counts and specified/density/approximate unit mass | kg |
| FORMWORK_COLUMN / FOOTING | Four side contact areas | m2 |
| FORMWORK_BEAM | Two sides plus soffit | m2 |
| FORMWORK_SLAB | Soffit only | m2 |
| AREA / LENGTH / COUNT | Explicit dimensions/count | m2 / m / each |

Arithmetic is regression tested. Professional measurement/design review is required.
D²/162 is labeled approximate; design lengths remain external. Opening, intersection
and special deductions are supplied explicitly in output units, with a reason and
bounded by gross. No structural adequacy or trade-specific waste is inferred.

Prepared/checker IDs, UTC event time, drawing/revision and location are retained.
NRM 2 is the default contextual profile. NRM 1/3, CESMM4, PWD/LGED and project rules
are registered as REQUIRES_PROFESSIONAL_REVIEW. ICMS 3 is reporting classification.
See quantity-surveying-standards.md for edition/source references and exclusions.
