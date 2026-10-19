import asyncio
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
import json
import httpx
from sqlalchemy import select, func
from . import advanced_models as a, audit, jobs
from .models import Project, User, Membership, PurchaseOrder, POLine, Supplier, Document, Invoice, InvoiceLine, Payment
from .database import transaction
from .money import canonical, digest, decimal, utcnow, published, money
from .advanced_math import unit_factor, nonnegative
from .price_providers import SerpApiProvider, DataForSEOProvider, demo_offers, safe_url
from .security import DomainError
from .finance import business_date


def material_view(mat):
    return {
        "id": mat.id,
        "project_id": mat.project_id,
        "name": mat.name,
        "category": mat.category,
        "unit": mat.unit,
        "specification": json.loads(mat.specification_json),
        "version": mat.version,
        "active": mat.active,
    }


def provider_status(settings):
    return [
        {
            "id": "serpapi",
            "source_type": "ONLINE_LISTING",
            "enabled": bool(settings.serpapi_key),
        },
        {
            "id": "dataforseo",
            "source_type": "ONLINE_LISTING",
            "enabled": bool(settings.dataforseo_login and settings.dataforseo_password),
        },
        {"id": "supplier", "source_type": "SUPPLIER_QUOTE", "enabled": True},
        {"id": "reference", "source_type": "OFFICIAL_REFERENCE", "enabled": True},
        {"id": "history", "source_type": "HISTORICAL_INTERNAL", "enabled": True},
        {
            "id": "demo",
            "source_type": "DEMO",
            "enabled": settings.demo_mode,
            "notice": "Explicit synthetic demonstration mode only",
        },
    ]


def observation(
    session, material, payload, provider, source_type, search_id=None, quotation_id=None
):
    if payload.get("source_url"):
        payload["source_url"] = safe_url(payload["source_url"])
    record = a.PriceObservation(
        project_id=material.project_id,
        material_id=material.id,
        search_id=search_id,
        quotation_id=quotation_id,
        provider=provider,
        source_type=source_type,
        payload_json=canonical(payload),
        evidence_hash=digest(payload),
    )
    session.add(record)
    session.flush()
    return record


def search_view(record, cached=False):
    request = json.loads(record.request_json)
    request.pop("query", None)
    return {
        "id": record.id,
        "material_id": record.material_id,
        "status": record.status,
        "request": request,
        "states": json.loads(record.states_json),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "cached": cached,
    }


def start_search(session, material, actor, request, settings):
    if request.mode == "DEMO" and not settings.demo_mode:
        raise DomainError(403, "DEMO_DISABLED", "Demonstration providers are disabled.")
    unit_factor(request.unit or material.unit, material.unit)
    data = request.model_dump(mode="json")
    data["unit"] = request.unit or material.unit
    fingerprint = digest({"material": material_view(material), "request": data})
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    cached = session.scalar(
        select(a.PriceSearch)
        .where(
            a.PriceSearch.fingerprint == fingerprint,
            a.PriceSearch.created_at >= cutoff,
            a.PriceSearch.status.in_(["QUEUED", "RUNNING", "COMPLETE", "EMPTY"]),
        )
        .order_by(a.PriceSearch.id.desc())
    )
    if cached:
        return cached, True
    uncertain = session.scalar(
        select(a.PriceSearch)
        .where(
            a.PriceSearch.fingerprint == fingerprint,
            a.PriceSearch.states_json.contains("UNKNOWN_SUBMISSION"),
        )
        .order_by(a.PriceSearch.id.desc())
    )
    if uncertain:
        raise DomainError(
            409,
            "UNKNOWN_SUBMISSION",
            "An earlier paid submission has an unknown result. Reconcile it with the provider before submitting again.",
        )
    minute = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    count = session.scalar(
        select(func.count())
        .select_from(a.PriceSearch)
        .where(
            a.PriceSearch.actor_id == actor.id,
            a.PriceSearch.project_id == material.project_id,
            a.PriceSearch.created_at >= minute,
        )
    )
    if count >= 5:
        raise DomainError(
            429,
            "PRICE_RATE_LIMIT",
            "Five refreshes per user/project per minute are allowed.",
        )
    data["query"] = " ".join(
        [material.name, *json.loads(material.specification_json).values()]
    )[:400]
    states = (
        {"demo": {"status": "QUEUED"}}
        if request.mode == "DEMO"
        else {
            p["id"]: {"status": "QUEUED" if p["enabled"] else "DISABLED"}
            for p in provider_status(settings)
            if p["id"] in ("serpapi", "dataforseo")
        }
    )
    record = a.PriceSearch(
        project_id=material.project_id,
        material_id=material.id,
        actor_id=actor.id,
        fingerprint=fingerprint,
        request_json=canonical(data),
        states_json=canonical(states),
    )
    session.add(record)
    session.flush()
    audit.append(
        session,
        actor,
        "PRICE_SEARCH_REQUESTED",
        "price_search",
        record.id,
        {"mode": request.mode, "fingerprint": fingerprint},
        material.project_id,
    )
    return record, False


def matching(session, material, record, payload):
    desired = json.loads(material.specification_json)
    offered = payload.get("specification") or {}

    def cleaned(value):
        return " ".join(str(value).lower().split())

    def equal(key, left, right):
        if key.endswith(("_mm", "_mpa")):
            try:
                return decimal(str(left)) == decimal(str(right))
            except ValueError:
                return False
        if key == "standard":
            return cleaned(left).replace(" ", "") == cleaned(right).replace(" ", "")
        return cleaned(left) == cleaned(right)

    mismatches = [
        key
        for key, value in desired.items()
        if value.strip() and key in offered and not equal(key, offered[key], value)
    ]
    missing = [
        key
        for key, value in desired.items()
        if value.strip() and not str(offered.get(key, "")).strip()
    ]
    equivalent = session.scalar(
        select(a.MaterialEquivalent).where(
            a.MaterialEquivalent.material_id == material.id,
            a.MaterialEquivalent.observation_id == record.id,
            a.MaterialEquivalent.material_version == material.version,
        )
    )
    if payload.get("rate_category", "MATERIAL") != "MATERIAL":
        return "Incompatible", [
            "Composite/work-item rates cannot be compared with raw material prices."
        ]
    if equivalent:
        return "Approved Equivalent", [
            "Independent technical approval: " + equivalent.reason
        ]
    if mismatches:
        return "Incompatible", ["Different specification: " + ", ".join(mismatches)]
    if missing or not any(value.strip() for value in desired.values()):
        return "Insufficient Information", [
            "Missing required specifications: "
            + ", ".join(missing or ["material requirements"])
        ]
    if offered.get("requires_review"):
        return "Requires Technical Review", [
            "Source explicitly requires technical review."
        ]
    return "Exact Match", ["All recorded project specification attributes match."]


def normalize_offer(session, material, record, request, project_currency):
    payload = json.loads(record.payload_json)
    compatibility, reasons = matching(session, material, record, payload)
    conversions, breakdown = [], {}
    normalized, landed, factor = None, None, None
    eligible = compatibility in ("Exact Match", "Approved Equivalent")
    try:
        price = nonnegative(payload.get("price"), "Observed price", True)
        factor = unit_factor(
            payload.get("unit") or "",
            material.unit,
            payload.get("package_weight_kg"),
            payload.get("density_kg_m3"),
            payload.get("density_assumption", ""),
        )
        conversions.append(
            {
                "from": payload.get("unit"),
                "to": material.unit,
                "factor": str(factor),
                "package_weight_kg": payload.get("package_weight_kg"),
                "density_kg_m3": payload.get("density_kg_m3"),
                "density_assumption": payload.get("density_assumption", ""),
            }
        )
        fx_factor = Decimal(1)
        if not payload.get("currency"):
            raise ValueError("Source currency is unknown")
        if payload["currency"] != project_currency:
            fx = session.scalar(
                select(a.ExchangeRate)
                .where(
                    a.ExchangeRate.project_id == material.project_id,
                    a.ExchangeRate.base == payload["currency"],
                    a.ExchangeRate.quote == project_currency,
                    a.ExchangeRate.observed_date <= business_date().isoformat(),
                )
                .order_by(a.ExchangeRate.observed_date.desc(), a.ExchangeRate.id.desc())
            )
            if not fx:
                raise ValueError("No recorded exchange rate for this currency pair")
            fx_factor = decimal(fx.factor)
            conversions.append(
                {
                    "exchange_rate_id": fx.id,
                    "base": fx.base,
                    "quote": fx.quote,
                    "factor": fx.factor,
                    "source": fx.source,
                    "date": fx.observed_date,
                }
            )
        normalized = published(price / factor * fx_factor)
        quantity = nonnegative(
            request.quantity, "Required quantity", True
        ) * unit_factor(request.unit or material.unit, material.unit)
        quoted = (
            nonnegative(payload.get("quoted_quantity", "1"), "Quoted quantity", True)
            * factor
        )
        minimum = (
            nonnegative(payload.get("minimum_quantity", "1"), "Minimum quantity")
            * factor
        )
        if minimum > quantity:
            eligible = False
            reasons.append("Minimum order exceeds the requested quantity.")
        total = price * (quantity / factor)
        breakdown["product_cost"] = published(total * fx_factor)
        for charge in ("freight", "tax", "handling", "other_cost"):
            basis = payload.get(charge + "_basis", "EXCLUDED")
            value = payload.get(charge)
            if basis == "UNKNOWN" or (basis == "EXCLUDED" and value is None):
                breakdown[charge] = None
                raise ValueError(
                    f"Unknown {charge}; landed cost is partially comparable"
                )
            if charge == "tax" and payload.get("tax_recoverable") and value is None:
                raise ValueError("Recoverable included tax requires a recorded amount")
            # Fixed freight/handling applies once per quoted order; different order sizes need review.
            if (
                charge != "tax"
                and basis == "EXCLUDED"
                and decimal(value or "0")
                and quoted != quantity
            ):
                raise ValueError(f"{charge} was quoted for a different order quantity")
            amount = nonnegative(value or "0", charge)
            if charge == "tax":
                amount *= quantity / quoted
            addition = Decimal(0) if basis == "INCLUDED" else amount
            if charge == "tax" and payload.get("tax_recoverable"):
                addition = -amount if basis == "INCLUDED" else Decimal(0)
            total += addition
            breakdown[charge] = {
                "basis": basis,
                "increment": published(addition * fx_factor),
                "recoverable": bool(payload.get("tax_recoverable"))
                if charge == "tax"
                else False,
            }
        if total <= 0:
            raise ValueError("Recoverable tax exceeds the observed price")
        landed = published(total / quantity * fx_factor)
        if decimal(landed) <= 0:
            raise ValueError("Price is below the supported six-decimal rate precision")
        breakdown["usable_quantity"] = str(quantity)
        breakdown["currency"] = project_currency
    except (ValueError, TypeError, ArithmeticError) as exc:
        eligible = False
        reasons.append(str(exc))
    if payload.get("can_deliver") is not True or payload.get("delivery_days") is None:
        eligible = False
        reasons.append("Delivery suitability is unconfirmed.")
    if (
        str(payload.get("country", "")).upper() != request.country
        or str(payload.get("city", "")).casefold() != request.city.casefold()
    ):
        eligible = False
        reasons.append("Source location differs from the requested destination.")
    now = datetime.now(timezone.utc)
    age = (
        now - datetime.fromisoformat(record.retrieved_at.replace("Z", "+00:00"))
    ).total_seconds()
    if record.source_type == "ONLINE_LISTING" and age > 86400:
        eligible = False
        reasons.append("Public listing is stale (older than 24 hours).")
    if (
        payload.get("valid_until")
        and date.fromisoformat(payload["valid_until"]) < business_date()
    ):
        eligible = False
        reasons.append("Quotation has expired.")
    if record.source_type == "SUPPLIER_QUOTE" and not payload.get("valid_until"):
        eligible = False
        reasons.append("Firm supplier quotation needs a validity date.")
    if record.source_type in ("OFFICIAL_REFERENCE", "HISTORICAL_INTERNAL"):
        eligible = False
        reasons.append(
            "Reference/historical rate is not a current supplier offer; review separately."
        )
    if record.source_type == "ONLINE_LISTING" and not payload.get("source_url"):
        eligible = False
        reasons.append("Public listing has no usable source link.")
    return {
        "observation_id": record.id,
        "provider": record.provider,
        "source_type": record.source_type,
        "payload": payload,
        "evidence_hash": record.evidence_hash,
        "retrieved_at": record.retrieved_at,
        "compatibility": compatibility,
        "reasons": reasons,
        "normalized_unit_price": normalized,
        "landed_unit_cost": landed,
        "cost_breakdown": breakdown,
        "conversions": conversions,
        "eligible": eligible,
        "score": "0",
        "scoring": {},
        "recommended": False,
        "lowest_comparable": False,
    }


def compare(session, material, request, search_id=None):
    records = list(
        session.scalars(
            select(a.PriceObservation)
            .where(a.PriceObservation.material_id == material.id)
            .order_by(a.PriceObservation.id.desc())
            .limit(300)
        )
    )
    records = [
        r
        for r in records
        if (r.source_type == "DEMO") == (request.mode == "DEMO")
        and (not search_id or r.search_id in (None, search_id))
    ]
    project = session.get(Project, material.project_id)
    results = [
        normalize_offer(session, material, r, request, project.currency)
        for r in records
    ]
    candidates = [r for r in results if r["eligible"]]
    if candidates:
        lowest = min(decimal(r["landed_unit_cost"]) for r in candidates)
        for row in candidates:
            cost = 50 * lowest / decimal(row["landed_unit_cost"])
            evidence = Decimal(
                25 if row["source_type"] in ("SUPPLIER_QUOTE", "DEMO") else 15
            )
            age_hours = max(
                Decimal(0),
                Decimal(
                    str(
                        (
                            datetime.now(timezone.utc)
                            - datetime.fromisoformat(
                                row["retrieved_at"].replace("Z", "+00:00")
                            )
                        ).total_seconds()
                    )
                )
                / 3600,
            )
            freshness = (
                Decimal(10)
                if row["source_type"] == "SUPPLIER_QUOTE"
                else max(Decimal(0), 10 * (1 - age_hours / 24))
            )
            row["scoring"] = {
                "policy": "recommendation-v1",
                "landed_cost_50": format(cost, ".4f"),
                "source_evidence_25": str(evidence),
                "delivery_15": "15",
                "freshness_10": format(freshness, ".4f"),
            }
            row["score"] = format(cost + evidence + 15 + freshness, ".4f")
            row["lowest_comparable"] = decimal(row["landed_unit_cost"]) == lowest
        best = sorted(
            candidates,
            key=lambda r: (
                -decimal(r["score"]),
                decimal(r["landed_unit_cost"]),
                r["observation_id"],
            ),
        )[0]
        best["recommended"] = True
    return {
        "material": material_view(material),
        "offers": results,
        "recommended_observation_id": next(
            (r["observation_id"] for r in candidates if r["recommended"]), None
        ),
        "notice": "Single-source indicative recommendation — additional quotation recommended."
        if len(candidates) == 1
        else ""
        if candidates
        else "No currently verifiable online prices available for this material and location.",
        "mode": request.mode,
        "policy": "recommendation-v1",
        "currency": project.currency,
        "displayed_request": request.model_dump(mode="json"),
        "searched_at": session.get(a.PriceSearch, search_id).created_at
        if search_id
        else None,
    }


async def run_search(engine, settings, identity):
    with transaction(engine, True) as session:
        record = session.get(a.PriceSearch, identity)
        if not record or record.status not in ("QUEUED", "RUNNING", "WAITING", "FAILED", "INTERRUPTED"):
            return
        states = json.loads(record.states_json)
        if any(state["status"] in ("SUBMITTING", "UNKNOWN_SUBMISSION") and not state.get("remote_id") for state in states.values()):
            return
        attempt = jobs.claim(session, "price_search", identity)
    if not attempt:
        return
    try:
        await _run_search(engine, settings, identity, attempt)
    except asyncio.CancelledError:
        with transaction(engine, True) as session:
            record = session.get(a.PriceSearch, identity)
            if record and jobs.owns(session, attempt):
                record.status = "INTERRUPTED"
            jobs.finish(session, attempt, "INTERRUPTED")
        raise
    except Exception:
        with transaction(engine, True) as session:
            record = session.get(a.PriceSearch, identity)
            if record and jobs.owns(session, attempt):
                record.status = "FAILED"
            jobs.finish(session, attempt, "FAILED")
    finally:
        with transaction(engine, True) as session:
            record = session.get(a.PriceSearch, identity)
            jobs.finish(session, attempt, record.status if record else "FAILED")


async def _run_search(engine, settings, identity, attempt):
    with transaction(engine, True) as session:
        record = session.get(a.PriceSearch, identity)
        actor = session.get(User, record.actor_id)
        if (
            not actor
            or not actor.active
            or actor.role not in ("OPERATOR", "FINANCE_MANAGER", "ADMIN")
            or not session.get(Membership, (actor.id, record.project_id))
            or not session.get(Project, record.project_id).active
        ):
            record.status = "INTERRUPTED"
            return
        material = session.get(a.Material, record.material_id)
        states, request = (
            json.loads(record.states_json),
            json.loads(record.request_json),
        )
        record.status = "RUNNING"
        if request["mode"] == "DEMO":
            for payload in demo_offers(material, request):
                observation(session, material, payload, "demo", "DEMO", record.id)
            states["demo"] = {"status": "COMPLETE", "count": 3}
            record.states_json, record.status, record.updated_at = (
                canonical(states),
                "COMPLETE",
                utcnow(),
            )
            return
    for provider in (SerpApiProvider(), DataForSEOProvider()):
        state = states[provider.name]
        if state["status"] in ("DISABLED", "COMPLETE", "EMPTY", "UNKNOWN_SUBMISSION"):
            continue
        try:
            with transaction(engine, True) as session:
                jobs.heartbeat(session, attempt)
            if provider.name == "serpapi":
                offers = await provider.search(request, settings)
            else:
                remote_id = state.get("remote_id")
                if not remote_id:
                    state["status"] = "SUBMITTING"
                    with transaction(engine, True) as session:
                        jobs.heartbeat(session, attempt)
                        session.get(a.PriceSearch, identity).states_json = canonical(
                            states
                        )
                    try:
                        remote_id = await provider.submit(request, settings)
                    except Exception as exc:
                        if "UNSUPPORTED_LOCATION" not in str(exc):
                            state["status"] = "UNKNOWN_SUBMISSION"
                        raise
                    state.update(remote_id=remote_id, status="WAITING")
                    with transaction(engine, True) as session:
                        jobs.heartbeat(session, attempt)
                        session.get(a.PriceSearch, identity).states_json = canonical(
                            states
                        )
                offers = None
                for delay in (0, 2, 5, 10):
                    if delay:
                        await asyncio.sleep(delay)
                    with transaction(engine, True) as session:
                        jobs.heartbeat(session, attempt)
                    offers = await provider.retrieve(remote_id, request, settings)
                    if offers is not None:
                        break
                if offers is None:
                    state["status"] = "WAITING"
                    continue
            with transaction(engine, True) as session:
                record = session.get(a.PriceSearch, identity)
                from .security import project_access, require_role

                actor = session.get(User, record.actor_id)
                project_access(session, actor, record.project_id, write=True)
                require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
                jobs.heartbeat(session, attempt)
                material = session.get(a.Material, record.material_id)
                for payload in offers:
                    observation(
                        session,
                        material,
                        payload,
                        provider.name,
                        "ONLINE_LISTING",
                        identity,
                    )
                state.update(
                    status="COMPLETE" if offers else "EMPTY", count=len(offers)
                )
        except Exception as exc:
            # Never leak request URLs containing API keys or Basic credentials.
            if state["status"] != "UNKNOWN_SUBMISSION":
                state["status"] = (
                    "UNSUPPORTED_LOCATION"
                    if "UNSUPPORTED_LOCATION" in str(exc)
                    else "TIMEOUT"
                    if isinstance(exc, httpx.TimeoutException)
                    else "FAILED"
                )
            state["message"] = (
                "Provider request did not complete. Check coverage, credentials, quota or retry a known task."
            )
        finally:
            with transaction(engine, True) as session:
                jobs.heartbeat(session, attempt)
                session.get(a.PriceSearch, identity).states_json = canonical(states)
    with transaction(engine, True) as session:
        jobs.heartbeat(session, attempt)
        record = session.get(a.PriceSearch, identity)
        count = session.scalar(
            select(func.count())
            .select_from(a.PriceObservation)
            .where(a.PriceObservation.search_id == identity)
        )
        record.status = (
            "WAITING"
            if any(s["status"] == "WAITING" for s in states.values())
            else "COMPLETE"
            if count
            else "NO_PROVIDERS"
            if all(s["status"] == "DISABLED" for s in states.values())
            else "EMPTY"
            if all(s["status"] in ("EMPTY", "DISABLED") for s in states.values())
            else "FAILED"
        )
        record.updated_at = utcnow()
        audit.append(
            session,
            session.get(User, record.actor_id),
            "PRICE_SEARCH_FINISHED",
            "price_search",
            identity,
            {"status": record.status, "providers": states, "observations": count},
            record.project_id,
        )


def add_history(session, material):
    existing = {
        json.loads(r.payload_json).get("history_source_hash")
        for r in session.scalars(
            select(a.PriceObservation).where(
                a.PriceObservation.material_id == material.id,
                a.PriceObservation.source_type == "HISTORICAL_INTERNAL",
            )
        )
    }
    for pol, po, supplier, doc in session.execute(
        select(POLine, PurchaseOrder, Supplier, Document)
        .join(PurchaseOrder, POLine.po_id == PurchaseOrder.id)
        .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        .join(Document, PurchaseOrder.document_id == Document.id)
        .where(
            PurchaseOrder.project_id == material.project_id,
            PurchaseOrder.approved.is_(True),
            POLine.description == material.name,
        )
    ):
        payments = [
            {"payment_id": payment.id, "invoice_id": invoice.id, "invoice_number": invoice.number,
             "invoice_total_paid_amount": money(payment.amount_minor), "currency": payment.currency,
             "executed_at": payment.executed_at, "sandbox_reference": payment.mock_transaction_id}
            for payment, invoice in session.execute(
                select(Payment, Invoice).join(Invoice, Payment.invoice_id == Invoice.id)
                .where(Invoice.project_id == material.project_id, Invoice.po_id == po.id,
                       select(InvoiceLine.id).where(InvoiceLine.invoice_id == Invoice.id,
                           InvoiceLine.active.is_(True), InvoiceLine.item_code == pol.item_code,
                           InvoiceLine.description == pol.description).exists())
                .order_by(Payment.id))
        ]
        source_hash = digest({"po": [po.id, po.version, po.currency], "line": [pol.id, pol.description,
            pol.quantity, pol.rate, pol.unit], "document": [doc.id, doc.created_at], "payments": payments})
        if source_hash not in existing:
            observation(
                session,
                material,
                {
                    "title": pol.description,
                    "supplier": supplier.name,
                    "price": pol.rate,
                    "currency": po.currency,
                    "unit": pol.unit,
                    "po_line_id": pol.id,
                    "po_number": po.number,
                    "document_id": doc.id,
                    "purchase_record_date": doc.created_at,
                    "history_source_hash": source_hash,
                    "po_version": po.version,
                    "settlement_evidence": payments,
                    "notice": "Approved purchase-order unit rate. Linked payments are whole-invoice context, not an allocation of cash to this item. Specifications and landed charges are not inferred.",
                    "specification": {},
                    "rate_category": "MATERIAL",
                    "city": "",
                    "country": "BD",
                    "source_url": None,
                },
                "history",
                "HISTORICAL_INTERNAL",
            )
            existing.add(source_hash)
    return len(existing - {None})
