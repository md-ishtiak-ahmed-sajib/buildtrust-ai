"""Deterministic, dimension-aware calculations; no standard-specific deductions invented."""

from decimal import Decimal, localcontext
from .money import decimal, minor, money, published

PI = Decimal("3.1415926535897932384626433832795028841971693993751")
UNITS = {
    "kg": ("mass", Decimal(1)),
    "tonne": ("mass", Decimal(1000)),
    "tonnes": ("mass", Decimal(1000)),
    "t": ("mass", Decimal(1000)),
    "m": ("length", Decimal(1)),
    "mm": ("length", Decimal("0.001")),
    "cm": ("length", Decimal("0.01")),
    "ft": ("length", Decimal("0.3048")),
    "m2": ("area", Decimal(1)),
    "ft2": ("area", Decimal("0.09290304")),
    "m3": ("volume", Decimal(1)),
    "ft3": ("volume", Decimal("0.028316846592")),
    "each": ("count", Decimal(1)),
    "pcs": ("count", Decimal(1)),
    "thousand": ("count", Decimal(1000)),
    "bag": ("package", Decimal(1)),
    "hour": ("time", Decimal(1)),
    "day": ("day", Decimal(1)),
    "sum": ("sum", Decimal(1)),
}


def nonnegative(value, label="Value", positive=False):
    val = decimal(value)
    if val < 0 or (positive and val == 0):
        raise ValueError(f"{label} must be {'positive' if positive else 'nonnegative'}")
    return val


def unit_factor(source, target, packaging=None, density=None, assumption=""):
    source, target = source.strip().lower(), target.strip().lower()
    if source not in UNITS or target not in UNITS:
        raise ValueError("Unsupported unit; provide a reviewed conversion")
    sd, sf = UNITS[source]
    td, tf = UNITS[target]
    if sd == td:
        return sf / tf
    if source == "bag" and td == "mass":
        return nonnegative(packaging, "Known package weight", True) / tf
    if target == "bag" and sd == "mass":
        return sf / nonnegative(packaging, "Known package weight", True)
    if {sd, td} == {"mass", "volume"}:
        if not assumption.strip():
            raise ValueError(
                "Density conversion requires a documented bulk/moisture assumption"
            )
        rho = nonnegative(density, "Material-specific density", True)
        return sf * (rho if sd == "volume" else 1 / rho) / tf
    raise ValueError("Units have incompatible dimensions")


def calculate_takeoff(data):
    dims = data.dimensions
    factor = unit_factor(data.dimension_unit, "m")
    for key, val in dims.items():
        nonnegative(val, key)

    def raw(key, default=None, positive=True):
        if key not in dims:
            if default is not None:
                return Decimal(default)
            raise ValueError(f"Missing dimension: {key}")
        return nonnegative(dims[key], key, positive)

    def length(key):
        return raw(key) * unit_factor(data.dimension_unit, "m")

    count = raw("count", "1")
    if count != count.to_integral_value():
        raise ValueError("Count must be a whole number")
    kind = data.calculation
    warnings = [
        "Geometry calculation only; selected standard deductions require professional review."
    ]
    with localcontext() as ctx:
        ctx.prec = 40
        if kind == "RECTANGULAR_VOLUME":
            gross, unit, formula = (
                length("length") * length("width") * length("height") * count,
                "m3",
                "L × B × H × count",
            )
        elif kind == "CIRCULAR_VOLUME":
            gross, unit, formula = (
                PI * length("diameter") ** 2 / 4 * length("height") * count,
                "m3",
                "π × D² / 4 × height × count",
            )
        elif kind == "AREA":
            gross, unit, formula = (
                length("length") * length("width") * count,
                "m2",
                "L × B × count",
            )
        elif kind == "LENGTH":
            gross, unit, formula = length("length") * count, "m", "length × count"
        elif kind == "COUNT":
            gross, unit, formula = count, "each", "count"
        elif kind == "REBAR":
            # Diameter is explicitly millimetres; bar length uses dimension_unit.
            diameter = raw("diameter_mm")
            if data.mass_method == "SPECIFIED":
                if not data.nominal_mass_source.strip():
                    raise ValueError("Specified nominal mass requires its source")
                unit_mass = raw("unit_mass_kg_m")
                formula = "length × count × specified kg/m"
            elif data.mass_method == "DENSITY":
                unit_mass = PI * (diameter / 1000) ** 2 / 4 * raw("density_kg_m3")
                formula = "length × count × π × (diameter_mm/1000)² / 4 × density"
            else:
                unit_mass = diameter**2 / 162
                formula = "length × count × diameter_mm² / 162 (approximation)"
                warnings.append(
                    "D²/162 is an engineering approximation, not a nominal mass certification."
                )
            gross, unit = length("length") * count * unit_mass, "kg"
            warnings.append(
                "Structural adequacy, hooks, laps and anchorage are not inferred; use approved design lengths."
            )
        elif kind in ("FORMWORK_COLUMN", "FORMWORK_FOOTING"):
            gross, unit, formula = (
                2 * (length("length") + length("width")) * length("height") * count,
                "m2",
                "2 × (L + B) × H × count; four sides only",
            )
        elif kind == "FORMWORK_BEAM":
            gross, unit, formula = (
                (2 * length("height") + length("width")) * length("length") * count,
                "m2",
                "(2 × depth + width) × length × count; sides and soffit",
            )
        elif kind == "FORMWORK_SLAB":
            gross, unit, formula = (
                length("length") * length("width") * count,
                "m2",
                "L × B × count; slab soffit only",
            )
        elif kind == "EARTHWORK":
            a1 = length("top_length") * length("top_width")
            a2 = length("bottom_length") * length("bottom_width")
            gross, unit, formula = (
                length("depth") * (a1 + a2 + (a1 * a2).sqrt()) / 3 * count,
                "m3",
                "depth / 3 × (top area + bottom area + √(top area × bottom area)) × count",
            )
        elif kind in ("BACKFILL", "DISPOSAL"):
            available = raw("excavated_volume") * factor**3
            excluded = raw("excluded_volume", positive=False) * factor**3
            if excluded > available:
                raise ValueError("Excluded/reused volume exceeds excavated volume")
            gross, unit, formula = (
                (available - excluded) * raw("volume_factor") * count,
                "m3",
                "(excavated − excluded/reused volume) × explicitly supplied volume factor × count",
            )
        elif kind == "COMPACTION":
            gross, unit, formula = (raw("loose_volume") * factor**3 * raw("compaction_factor") * count,
                                    "m3", "supplied loose volume × supplied compaction factor × count")
        elif kind == "MASONRY":
            openings = raw("opening_area", positive=False) * factor**2
            wall = length("length") * length("height")
            if openings > wall:
                raise ValueError("Openings exceed wall area")
            gross, unit, formula = (
                (wall - openings) * length("thickness") * count,
                "m3",
                "(length × height − supplied opening area) × thickness × count",
            )
        elif kind in ("FINISHES", "DOORS_WINDOWS"):
            opening = (
                raw("opening_area", positive=False) * factor**2
                if "opening_area" in data.dimensions
                else Decimal(0)
            )
            area = length("length") * length("height")
            if opening > area:
                raise ValueError("Openings exceed gross area")
            faces = raw("faces") if kind == "FINISHES" else Decimal(1)
            gross, unit, formula = (
                (area - opening) * faces * count,
                "m2",
                "(length × height − explicit openings) × selected faces × count",
            )
        elif kind == "ROOFING":
            gross, unit, formula = (
                length("length") * length("width") * raw("slope_factor") * count,
                "m2",
                "plan length × width × explicitly supplied slope factor × count",
            )
        elif kind in ("PAVEMENT", "TRIANGULAR_PRISM"):
            multiplier = Decimal("0.5") if kind == "TRIANGULAR_PRISM" else Decimal(1)
            gross, unit, formula = (
                length("length")
                * length("width")
                * length("height")
                * multiplier
                * count,
                "m3",
                "length × width × height × section factor × count",
            )
        elif kind == "FRUSTUM":
            a1 = length("top_length") * length("top_width")
            a2 = length("bottom_length") * length("bottom_width")
            gross, unit, formula = (
                length("height") / 3 * (a1 + a2 + (a1 * a2).sqrt()) * count,
                "m3",
                "height / 3 × (A1 + A2 + √(A1 × A2)) × count",
            )
        elif kind == "ANNULAR_VOLUME":
            outer, inner = length("outer_diameter"), length("inner_diameter")
            if inner >= outer:
                raise ValueError("Inner diameter must be less than outer diameter")
            gross, unit, formula = (
                PI * (outer**2 - inner**2) / 4 * length("height") * count,
                "m3",
                "π × (outer diameter² − inner diameter²) / 4 × height × count",
            )
        elif kind == "REBAR_SCHEDULE":
            if not data.reinforcement_schedule or not data.nominal_mass_source.strip():
                raise ValueError(
                    "Supply a reinforcement schedule and nominal mass source"
                )
            gross = Decimal(0)
            for row in data.reinforcement_schedule:
                if set(row) != {"length", "count", "unit_mass_kg_m"}:
                    raise ValueError(
                        "Schedule rows require length, count and supplied unit_mass_kg_m"
                    )
                number = nonnegative(row["count"], "Bar count", True)
                if number != number.to_integral_value():
                    raise ValueError("Bar count must be integral")
                gross += (
                    nonnegative(row["length"], "Bar length", True)
                    * factor
                    * number
                    * nonnegative(row["unit_mass_kg_m"], "Supplied nominal mass", True)
                )
            unit, formula = (
                "kg",
                "Σ (supplied length × bar count × sourced nominal kg/m); no inferred laps/hooks",
            )
        else:
            raise ValueError("Unsupported calculation template")
        deduction = nonnegative(data.deduction, "Deduction")
        if deduction and not data.deduction_reason.strip():
            raise ValueError("A deduction requires a documented reason in output units")
        if deduction > gross:
            raise ValueError("Deduction exceeds gross quantity")
        return {
            "quantity": published(gross - deduction),
            "gross_quantity": published(gross),
            "unit": unit,
            "formula": formula,
            "deduction": str(deduction),
            "warnings": warnings,
            "calculation_policy": "geometry-v1",
        }


def rate_analysis(fields):
    totals, cost_totals, results = 0, 0, []
    cost_known = not decimal(fields.tax_percent) or fields.tax_treatment != "UNKNOWN"
    ids, codes = set(), set()
    percentages = [
        "site_overhead_percent",
        "general_overhead_percent",
        "profit_percent",
        "tax_percent",
        "contingency_percent",
    ]
    for key in percentages:
        if not 0 <= decimal(getattr(fields, key)) <= 100:
            raise ValueError(f"{key} must be between 0 and 100")
    for line in fields.lines:
        if line.id in ids or line.code in codes:
            raise ValueError("BOQ IDs and work codes must be unique within a version")
        ids.add(line.id)
        codes.add(line.code)
        if line.unit not in UNITS:
            raise ValueError(f"Unsupported BOQ unit: {line.unit}")
        qty = nonnegative(line.quantity, "Quantity")
        if not line.components:
            raise ValueError("Each BOQ line requires at least one priced component")
        component_ids, components, categories = set(), [], {}
        for comp in line.components:
            if comp.id in component_ids:
                raise ValueError("Component IDs must be unique within each line")
            component_ids.add(comp.id)
            if comp.unit not in UNITS:
                raise ValueError("Unsupported component unit")
            consumption = nonnegative(comp.consumption, "Consumption")
            price = nonnegative(comp.unit_price, "Unit price")
            waste = nonnegative(comp.wastage_percent, "Wastage")
            if waste > 100 or (comp.category != "MATERIAL" and waste):
                raise ValueError("Wastage is 0–100% and applies to materials only")
            amount = consumption * price * (1 + waste / 100)
            categories[comp.category] = (
                categories.get(comp.category, Decimal(0)) + amount
            )
            components.append(
                {
                    "id": comp.id,
                    "category": comp.category,
                    "amount": published(amount),
                    "source": comp.selection_id or comp.source_note,
                }
            )
        direct = sum(categories.values(), Decimal(0))
        current, breakdown = direct, {"direct": published(direct)}
        # Sequential bases are saved and displayed, never implicit.
        for key in percentages:
            charge = current * decimal(getattr(fields, key)) / 100
            breakdown[key.removesuffix("_percent")] = {
                "base": published(current),
                "percent": getattr(fields, key),
                "amount": published(charge),
            }
            current += charge
        analyzed = current.quantize(Decimal("0.000001"), rounding="ROUND_HALF_UP")
        cost = direct
        cost_breakdown = {"direct": published(direct)}
        for key in (
            "site_overhead_percent",
            "general_overhead_percent",
            "tax_percent",
            "contingency_percent",
        ):
            if key == "tax_percent" and fields.tax_treatment != "NONRECOVERABLE_COST":
                continue
            allowance = cost * decimal(getattr(fields, key)) / 100
            cost_breakdown[key] = {
                "base": published(cost),
                "percent": getattr(fields, key),
                "amount": published(allowance),
            }
            cost += allowance
        cost_rate = published(cost)
        cost_amount = minor(qty * decimal(cost_rate))
        cost_totals += cost_amount
        amount_minor = minor(qty * analyzed)
        totals += amount_minor
        results.append(
            {
                "id": line.id,
                "code": line.code,
                "quantity": str(qty),
                "unit": line.unit,
                "unit_rate": published(analyzed),
                "amount": money(amount_minor),
                "cost_unit_rate": cost_rate if cost_known else None,
                "cost_amount": money(cost_amount) if cost_known else None,
                "cost_build_up": cost_breakdown,
                "components": components,
                "categories": {k: published(v) for k, v in categories.items()},
                "build_up": breakdown,
            }
        )
    return {
        "total": money(totals),
        "tender_total": money(totals),
        "cost_total": money(cost_totals) if cost_known else None,
        "cost_policy": "cost-v1: direct, site/general overhead, explicit nonrecoverable tax, contingency; excludes profit/output/recoverable tax",
        "lines": results,
        "policy": "rate-v1: direct → site overhead → general overhead → profit → tax → contingency; line amount HALF_UP 2dp",
    }
