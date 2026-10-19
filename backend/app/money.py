from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from datetime import datetime, timezone

CENT = Decimal("0.01")
SIX_PLACES = Decimal("0.000001")


def published(value: Decimal) -> str:
    """Authoritative rates and measured quantities; never use context rounding."""
    if not value.is_finite() or abs(value) > Decimal("1000000000000000000"):
        raise ValueError("Calculated quantity/rate exceeds supported output bounds")
    return format(value.quantize(SIX_PLACES, rounding=ROUND_HALF_UP), "f")


def decimal(value) -> Decimal:
    if isinstance(value, float):
        raise ValueError("Binary floats are not financial inputs; use decimal strings")
    raw = str(value).strip()
    # Bound ingress before Decimal parsing or fixed-point expansion. Internal
    # Decimal arithmetic is kept separate from these serialized-input limits.
    if not isinstance(value, Decimal) and len(raw) > 96:
        raise ValueError("Decimal input exceeds 96 characters")
    try:
        result = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal") from exc
    if not result.is_finite() or abs(result) > Decimal("1000000000000"):
        raise ValueError("Decimal out of bounds")
    if not isinstance(value, Decimal):
        parts = result.as_tuple()
        if len(parts.digits) > 48 or abs(parts.exponent) > 24:
            raise ValueError("Decimal input exceeds 48 digits or exponent +/-24")
    return result


def minor(value) -> int:
    return int((decimal(value).quantize(CENT, rounding=ROUND_HALF_UP) * 100))


def money(value: int) -> str:
    return format(Decimal(value) / 100, ".2f")


def canonical(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def utcnow() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def normalize(quantity, unit, rate=None):
    aliases = {
        "t": ("kg", "1000"),
        "tonne": ("kg", "1000"),
        "tonnes": ("kg", "1000"),
        "metric tonnes": ("kg", "1000"),
        "kg": ("kg", "1"),
        "kilogram": ("kg", "1"),
        "kilograms": ("kg", "1"),
        "bag": ("bag", "1"),
        "bags": ("bag", "1"),
        "m3": ("m3", "1"),
        "m2": ("m2", "1"),
        "each": ("each", "1"),
        "pcs": ("each", "1"),
    }
    key = unit.strip().lower()
    if key not in aliases:
        raise ValueError(f"Unsupported unit: {unit}; human review required")
    canonical_unit, factor = aliases[key]
    factor = Decimal(factor)
    return (
        decimal(quantity) * factor,
        canonical_unit,
        decimal(rate) / factor if rate is not None else None,
    )
