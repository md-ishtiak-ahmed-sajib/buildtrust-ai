"""Evidence-bound commercial workflows; approval never changes settled history."""

import json
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select

from . import accounting, advanced_models as a, audit, control_models as c, cost_coding, coverage
from . import commercial_models as cm, finance, models as m, obligations, pricing
from . import procurement as procurement_rules
from .advanced_math import unit_factor
from .advanced_schemas import EstimateFields
from .money import canonical, decimal, digest, minor, money, published
from .security import DomainError

KINDS = {
    "COMMERCIAL_CONTRACT",
    "RFQ",
    "COMMERCIAL_BID",
    "PURCHASE_RECOMMENDATION",
    "PURCHASE_AWARD",
    "CONTRACT_VARIATION",
    "WORK_ACCEPTANCE",
    "INTERIM_CERTIFICATE",
    "ADVANCE_ASSIGNMENT",
    "CONTRACT_ESTIMATE_LINK",
}


def approved(session, identity, kind, project_id):
    record = accounting.scoped(session, c.ControlRecord, identity, project_id)
    if record.kind != kind or record.status != "APPROVED":
        raise ValueError(
            f"An independently approved {kind.lower().replace('_', ' ')} is required"
        )
    return record, json.loads(record.payload_json), json.loads(record.calculated_json)


def records(session, project_id, kind, **filters):
    rows = session.scalars(
        select(c.ControlRecord)
        .where(
            c.ControlRecord.project_id == project_id,
            c.ControlRecord.kind == kind,
            c.ControlRecord.status == "APPROVED",
        )
        .order_by(c.ControlRecord.id)
    )
    return [
        (r, json.loads(r.payload_json), json.loads(r.calculated_json))
        for r in rows
        if all(json.loads(r.payload_json).get(k) == v for k, v in filters.items())
    ]


def unique_reference(session, project_id, kind, number, contract_id=None):
    for _, payload, _ in records(session, project_id, kind):
        if payload.get("number", payload.get("po_number")) == number and (
            contract_id is None or payload.get("contract_id") == contract_id
        ):
            raise DomainError(
                409,
                "DUPLICATE_COMMERCIAL_REFERENCE",
                "This commercial reference is already approved.",
            )


def contract_scope(session, project_id, identity):
    record, contract, calculated = approved(
        session, identity, "COMMERCIAL_CONTRACT", project_id
    )
    lines = {
        line["code"]: {
            **line,
            "segments": [{"quantity": line["quantity"], "rate": line["rate"]}],
        }
        for line in contract["lines"]
    }
    variations = records(
        session, project_id, "CONTRACT_VARIATION", contract_id=identity
    )
    for variation, payload, result in variations:
        line = lines[payload["item_code"]]
        if "scope_segments" in result:
            line["segments"] = result["scope_segments"]
            line["quantity"] = published(
                sum(
                    (decimal(segment["quantity"]) for segment in line["segments"]),
                    Decimal(0),
                )
            )
        else:
            line["segments"].append(
                {
                    "quantity": payload["additional_quantity"],
                    "rate": payload["proposed_rate"],
                }
            )
            line["quantity"] = published(
                decimal(line["quantity"]) + decimal(payload["additional_quantity"])
            )
    return (
        record,
        contract,
        lines,
        [{"id": r.id, "hash": r.snapshot_hash} for r, _, _ in variations],
    )


def valuation(line, quantity):
    remaining, amount = decimal(quantity), 0
    if remaining < 0 or remaining > decimal(line["quantity"]):
        raise ValueError("Quantity exceeds the approved contract and variations")
    for segment in line["segments"]:
        part = min(remaining, decimal(segment["quantity"]))
        amount += minor(part * decimal(segment["rate"]))
        remaining -= part
    return amount


def sourced_advance(session, project, contract, identity):
    source = accounting.scoped(session, c.Journal, identity, project.id)
    opening = session.get(c.ControlRecord, source.record_id) if source.record_id else None
    if (source.currency != project.currency or not opening
            or opening.kind != "OPENING_BALANCE" or opening.status != "APPROVED"):
        raise ValueError("Advance assignment requires a reviewed opening advance journal in project currency")
    account = "ADVANCE" if contract["direction"] == "SUPPLIER" else "CUSTOMER_ADVANCE"
    balance = sum((r.debit_minor - r.credit_minor) * (1 if account == "ADVANCE" else -1)
                  for r in session.scalars(select(c.JournalLine).where(
                      c.JournalLine.journal_id == source.id, c.JournalLine.account == account)))
    return source, account, balance


def build(session, project, values):
    kind = values.kind
    result = {"currency": project.currency, "policy": "commercial-v1"}
    if kind == "COMMERCIAL_CONTRACT":
        unique_reference(session, project.id, kind, values.number)
        policy, terms = accounting.policy(
            session, values.policy_id, project, values.effective_date
        )
        if values.currency != project.currency:
            raise ValueError("Contract currency must match the project")
        if values.completion_date and values.completion_date < values.effective_date:
            raise ValueError("Completion cannot precede the contract's effective date")
        for name in ("tax_percent", "retention_percent", "advance_recovery_percent"):
            if not 0 <= decimal(getattr(values, name)) <= 100:
                raise ValueError(f"{name} must be between 0 and 100")
        if terms["tax_treatment"] == "ZERO" and decimal(values.tax_percent):
            raise ValueError("Contract tax conflicts with the zero-tax policy")
        supplier_source = None
        if values.direction == "SUPPLIER":
            supplier = accounting.scoped(
                session, m.Supplier, values.supplier_id, project.id
            )
            if not supplier.approved or values.customer:
                raise ValueError(
                    "Supplier contract requires an approved supplier master"
                )
            supplier_source = {
                "id": supplier.id,
                "version": supplier.version,
                "beneficiary": supplier.beneficiary_fingerprint,
            }
        elif not values.customer or values.supplier_id:
            raise ValueError("Customer contracts require the customer identity")
        if len({line.code for line in values.lines}) != len(values.lines):
            raise ValueError("Contract item codes must be unique")
        line_results = []
        for line in values.lines:
            code = accounting.code(session, line.cost_code_id, project.id)
            if decimal(line.quantity) <= 0 or decimal(line.rate) <= 0:
                raise ValueError("Contract quantities and rates must be positive")
            source = None
            if line.boq_item_id:
                boq = accounting.scoped(
                    session, m.BOQItem, line.boq_item_id, project.id
                )
                if (
                    boq.item_code != line.code
                    or boq.description.strip().casefold()
                    != line.description.strip().casefold()
                ):
                    raise ValueError(
                        "Linked procurement BOQ code and specification must match"
                    )
                unit_factor(line.unit, boq.unit)
                source = {"id": boq.id, "version": boq.version}
                mapping = cost_coding.link(session, project.id, "BOQ_ITEM", boq.id)
                if mapping and mapping.cost_code_id != line.cost_code_id:
                    raise ValueError(
                        "Resolve the approved BOQ cost-code classification before this contract"
                    )
            line_results.append(
                {
                    "code": line.code,
                    "amount": money(minor(decimal(line.quantity) * decimal(line.rate))),
                    "cost_code_version": code.version,
                    "boq": source,
                }
            )
        result.update(
            total=money(sum(minor(line["amount"]) for line in line_results)),
            lines=line_results,
            source={"policy": policy.snapshot_hash, "supplier": supplier_source},
        )
        return result

    if kind in ("RFQ", "CONTRACT_VARIATION", "WORK_ACCEPTANCE", "INTERIM_CERTIFICATE", "ADVANCE_ASSIGNMENT", "CONTRACT_ESTIMATE_LINK"):
        contract_record, contract, lines, variations = contract_scope(
            session, project.id, values.contract_id
        )
        result["source"] = {
            "contract": contract_record.snapshot_hash,
            "variations": variations,
        }
        if kind in ("WORK_ACCEPTANCE", "INTERIM_CERTIFICATE"):
            accounting.policy(
                session, contract["policy_id"], project, values.recognition_date
            )
            if str(values.recognition_date) < contract["effective_date"]:
                raise ValueError(
                    "Recognition cannot precede the approved contract's effective date"
                )
        if kind not in ("INTERIM_CERTIFICATE", "ADVANCE_ASSIGNMENT"):
            line = lines.get(values.item_code)
            if not line:
                raise ValueError("Item is absent from the approved contract")
    if kind == "ADVANCE_ASSIGNMENT":
        source, account, balance = sourced_advance(session, project, contract, values.advance_source_id)
        if not values.counterparty_attested:
            raise ValueError("Independent evidence must attest the advance belongs to this contract and counterparty")
        amount = accounting.positive(values.amount)
        allocated = sum(r[2]["amount_minor"] for r in records(session, project.id, kind)
                        if r[1]["advance_source_id"] == source.id and r[2]["account"] == account)
        legacy_used = sum(r[2].get("advance_minor", 0)
                          for r in records(session, project.id, "INTERIM_CERTIFICATE")
                          if r[1].get("advance_source_id") == source.id
                          and not r[1].get("advance_assignment_id"))
        if amount > balance - allocated - legacy_used:
            raise ValueError("Advance assignment exceeds the source balance not already assigned or recovered")
        result.update(amount_minor=amount, amount=money(amount), account=account,
                      journal_id=source.id, journal_hash=source.snapshot_hash,
                      journal_date=source.business_date,
                      counterparty=contract.get("supplier_id") or contract.get("customer"))
        return result
    if kind == "CONTRACT_ESTIMATE_LINK":
        from .forecast_links import build as build_forecast_link
        return build_forecast_link(session,project,values)
    if kind == "RFQ":
        unique_reference(session, project.id, kind, values.number)
        if contract["direction"] != "SUPPLIER":
            raise ValueError("An RFQ requires a supplier procurement contract")
        material = accounting.scoped(
            session, a.Material, values.material_id, project.id
        )
        factor = unit_factor(material.unit, line["unit"])
        if decimal(values.quantity) <= 0 or decimal(values.quantity) * factor > decimal(
            line["quantity"]
        ):
            raise ValueError("RFQ quantity exceeds authorized scope")
        if values.closing_date > values.delivery_date:
            raise ValueError("RFQ closing date must precede delivery")
        result.update(
            specification=json.loads(material.specification_json),
            material_version=material.version,
            unit=material.unit,
            contract_item=line,
            notice="Local RFQ record; no messages are sent to suppliers.",
        )
    elif kind == "COMMERCIAL_BID":
        rfq_record, rfq, rfq_result = approved(
            session, values.rfq_id, "RFQ", project.id
        )
        supplier = accounting.scoped(
            session, m.Supplier, values.supplier_id, project.id
        )
        observation = accounting.scoped(
            session, a.PriceObservation, values.observation_id, project.id
        )
        material = accounting.scoped(
            session, a.Material, rfq["material_id"], project.id
        )
        if (
            material.version != rfq_result["material_version"]
            or observation.material_id != material.id
        ):
            raise ValueError("RFQ material/specification changed; approve a fresh RFQ")
        if observation.source_type != "SUPPLIER_QUOTE" or not observation.quotation_id:
            raise ValueError(
                "A verified supplier quotation is required; listings and demonstration offers cannot be awarded"
            )
        quotation = session.get(a.Quotation, observation.quotation_id)
        if not supplier.approved or quotation.status != "VERIFIED":
            raise ValueError(
                "Quotation and supplier master must be independently verified"
            )
        payload = json.loads(observation.payload_json)
        if (
            payload.get("supplier", payload.get("merchant", "")).strip().casefold()
            != supplier.name.strip().casefold()
        ):
            raise ValueError(
                "Quotation merchant must match the approved supplier master"
            )
        request = SimpleNamespace(
            quantity=rfq["quantity"],
            unit=rfq_result["unit"],
            city=rfq["city"],
            country=rfq["country"],
        )
        offer = pricing.normalize_offer(
            session, material, observation, request, project.currency
        )
        if not offer["eligible"]:
            raise ValueError("Bid is ineligible: " + "; ".join(offer["reasons"]))
        if finance.business_date() + timedelta(
            days=payload["delivery_days"]
        ) > date.fromisoformat(rfq["delivery_date"]):
            raise ValueError("Quoted delivery cannot meet the RFQ delivery date")
        result.update(
            rate=offer["landed_unit_cost"],
            amount=money(
                minor(decimal(rfq["quantity"]) * decimal(offer["landed_unit_cost"]))
            ),
            comparison=offer,
            source={
                "rfq": rfq_record.snapshot_hash,
                "quotation_version": quotation.version,
                "evidence_hash": observation.evidence_hash,
                "supplier_version": supplier.version,
                "beneficiary": supplier.beneficiary_fingerprint,
            },
        )
    elif kind == "PURCHASE_RECOMMENDATION":
        rfq, _, _ = approved(session, values.rfq_id, "RFQ", project.id)
        if (
            len(set(values.bid_ids)) != len(values.bid_ids)
            or values.selected_bid_id not in values.bid_ids
        ):
            raise ValueError("Select one of the distinct compared bids")
        compared = []
        for identity in values.bid_ids:
            row, bid, calculated = approved(
                session, identity, "COMMERCIAL_BID", project.id
            )
            if bid["rfq_id"] != values.rfq_id:
                raise ValueError("All compared bids must belong to this RFQ")
            # Recheck expiry, supplier master and material against current evidence.
            from .commercial_schemas import Bid

            current = build(session, project, Bid.model_validate(bid))
            if current != calculated:
                raise ValueError("Bid source changed; obtain fresh bid approval")
            compared.append(
                {
                    "id": identity,
                    "supplier_id": bid["supplier_id"],
                    "amount": calculated["amount"],
                    "rate": calculated["rate"],
                    "hash": row.snapshot_hash,
                }
            )
        selected = next(row for row in compared if row["id"] == values.selected_bid_id)
        result.update(
            compared=compared,
            selected=selected,
            single_source=len(compared) == 1,
            source={"rfq": rfq.snapshot_hash},
            notice="Human selection reason is retained, including any eligible higher-cost selection.",
        )
    elif kind == "PURCHASE_AWARD":
        recommendation, recommended, comparison = approved(
            session, values.recommendation_id, "PURCHASE_RECOMMENDATION", project.id
        )
        if records(session, project.id, kind, recommendation_id=recommendation.id):
            raise ValueError("Recommendation was already awarded")
        from .commercial_schemas import Recommendation

        if (
            build(session, project, Recommendation.model_validate(recommended))
            != comparison
        ):
            raise ValueError("Recommendation evidence changed")
        rfq_record, rfq, rfq_result = approved(
            session, recommended["rfq_id"], "RFQ", project.id
        )
        _, contract, lines, variations = contract_scope(
            session, project.id, rfq["contract_id"]
        )
        line = lines[rfq["item_code"]]
        supplier_id = comparison["selected"]["supplier_id"]
        if supplier_id != contract["supplier_id"]:
            raise ValueError(
                "Award supplier differs from the approved contract; approve the correct contract first"
            )
        quantity = decimal(rfq["quantity"]) * unit_factor(
            rfq_result["unit"], line["unit"]
        )
        prior = sum(
            (
                decimal(r[2]["contract_quantity"])
                for r in records(session, project.id, kind)
                if r[2]["contract_id"] == rfq["contract_id"]
                and r[2]["item_code"] == line["code"]
            ),
            Decimal(0),
        )
        if prior + quantity > decimal(line["quantity"]):
            raise ValueError("Awards exceed the approved contract quantity")
        rate = decimal(comparison["selected"]["rate"]) / unit_factor(
            rfq_result["unit"], line["unit"]
        )
        authorized = valuation(line, prior + quantity) - valuation(line, prior)
        if minor(quantity * rate) > authorized:
            raise ValueError(
                "Award cost exceeds contractual authorization; approve a prospective variation first"
            )
        if not line.get("boq_item_id"):
            raise ValueError(
                "PO publication requires a separately approved procurement BOQ link"
            )
        boq = accounting.scoped(session, m.BOQItem, line["boq_item_id"], project.id)
        if (
            boq.item_code != line["code"]
            or boq.description.strip().casefold()
            != line["description"].strip().casefold()
        ):
            raise ValueError("Procurement BOQ specification changed")
        authorized_quantity, authorized_value = procurement_rules.authorization(session,boq)
        committed_quantity = Decimal(0)
        committed_value = 0
        for existing_line, existing_po in session.execute(
            select(m.POLine, m.PurchaseOrder)
            .join(m.PurchaseOrder)
            .where(
                m.PurchaseOrder.project_id == project.id,
                m.PurchaseOrder.approved.is_(True),
                m.POLine.item_code == boq.item_code,
            )
        ):
            if (
                existing_line.description.strip().casefold()
                != boq.description.strip().casefold()
                or existing_po.currency != project.currency
            ):
                raise ValueError(
                    "Resolve incompatible existing procurement coverage before a further award"
                )
            committed_quantity += procurement_rules.quantity(session,existing_line) * unit_factor(
                existing_line.unit, boq.unit
            )
            committed_value += minor(procurement_rules.quantity(session,existing_line)*decimal(existing_line.rate))
        if (
            committed_quantity + quantity * unit_factor(line["unit"], boq.unit)
            > authorized_quantity
        ):
            raise ValueError(
                "Award exceeds remaining separately approved procurement BOQ quantity"
            )
        if committed_value+minor(quantity*rate)>authorized_value:
            raise ValueError('Award exceeds the separately approved procurement value ceiling')
        if session.scalar(
            select(m.PurchaseOrder.id).where(
                m.PurchaseOrder.project_id == project.id,
                m.PurchaseOrder.number == values.po_number,
            )
        ):
            raise ValueError("PO number already exists")
        result.update(
            contract_id=rfq["contract_id"],
            item_code=line["code"],
            description=line["description"],
            contract_quantity=published(quantity),
            quantity=rfq["quantity"],
            unit=rfq_result["unit"],
            rate=comparison["selected"]["rate"],
            supplier_id=supplier_id,
            amount=comparison["selected"]["amount"],
            due_date=rfq["delivery_date"],
            source={
                "recommendation": recommendation.snapshot_hash,
                "variations": variations,
                "boq_version": boq.version,
            },
            notice="Creates a new PO; approved BOQ, historical POs, receipts and payments are unchanged.",
        )
    elif kind == "CONTRACT_VARIATION":
        unique_reference(session, project.id, kind, values.number, values.contract_id)
        additional, repriced = (
            decimal(values.additional_quantity),
            decimal(values.reprice_quantity),
        )
        if repriced < 0 or (
            additional == 0 and repriced == 0 and values.time_impact_days == 0
        ):
            raise ValueError("Specify a prospective quantity, rate or time change")
        if decimal(values.proposed_rate) < 0 or (
            (additional > 0 or repriced > 0) and decimal(values.proposed_rate) <= 0
        ):
            raise ValueError("Added or repriced work requires a positive rate")
        awarded = sum(
            (
                decimal(r[2]["contract_quantity"])
                for r in records(session, project.id, "PURCHASE_AWARD")
                if r[2]["contract_id"] == values.contract_id
                and r[2]["item_code"] == values.item_code
            ),
            Decimal(0),
        )
        accepted = sum(
            (
                decimal(payload["quantity"])
                for _, payload, _ in records(
                    session,
                    project.id,
                    "WORK_ACCEPTANCE",
                    contract_id=values.contract_id,
                    item_code=values.item_code,
                )
            ),
            Decimal(0),
        )
        certificates = records(
            session, project.id, "INTERIM_CERTIFICATE", contract_id=values.contract_id
        )
        certified = (
            decimal(
                certificates[-1][2]["cumulative_quantities"].get(values.item_code, "0")
            )
            if certificates
            else Decimal(0)
        )
        protected = max(awarded, accepted, certified)
        if line.get("boq_item_id"):
            boq = session.get(m.BOQItem, line["boq_item_id"])
            procurement = sum(
                (
                    procurement_rules.quantity(session,pol) * unit_factor(pol.unit, line["unit"])
                    for pol in session.scalars(
                        select(m.POLine)
                        .join(m.PurchaseOrder)
                        .where(
                            m.PurchaseOrder.project_id == project.id,
                            m.PurchaseOrder.approved.is_(True),
                            m.POLine.item_code == boq.item_code,
                        )
                    )
                ),
                Decimal(0),
            )
            protected = max(protected, procurement)
        if repriced + max(-additional, Decimal(0)) > max(
            Decimal(0), decimal(line["quantity"]) - protected
        ):
            raise ValueError(
                "Repricing would change accepted, certified or committed quantities; procurement amendments require separate approval"
            )
        keep = decimal(line["quantity"]) - repriced - max(-additional, Decimal(0))
        segments = []
        for segment in line["segments"]:
            portion = min(keep, decimal(segment["quantity"]))
            if portion:
                segments.append(
                    {"quantity": published(portion), "rate": segment["rate"]}
                )
                keep -= portion
        if repriced + max(additional, Decimal(0)) > 0:
            segments.append(
                {
                    "quantity": published(repriced + max(additional, Decimal(0))),
                    "rate": published(decimal(values.proposed_rate)),
                }
            )
        old_total = valuation(line, line["quantity"])
        revised_total = sum(
            minor(decimal(segment["quantity"]) * decimal(segment["rate"]))
            for segment in segments
        )
        amount = revised_total - old_total
        result.update(
            claimed=money(minor(values.claimed_value)),
            reviewed=money(amount),
            approved_value=money(amount),
            added_quantity=published(decimal(values.additional_quantity)),
            rate=published(decimal(values.proposed_rate)),
            repriced_quantity=published(repriced),
            protected_quantity=published(protected),
            scope_segments=segments,
            time_impact_days=values.time_impact_days,
            notice="Prospective contract scope only. Budget and existing procurement amendments require separate approval.",
        )
    elif kind == "WORK_ACCEPTANCE":
        if (
            contract["direction"] != "SUPPLIER"
            or values.recognition_date > finance.business_date()
        ):
            raise ValueError(
                "Work acceptance requires actual supplier work with a nonfuture date"
            )
        sheet = accounting.scoped(
            session, a.TakeoffSheet, values.measurement_id, project.id
        )
        if sheet.status != "CHECKED":
            raise ValueError("An independently checked measurement sheet is required")
        sheet_result = json.loads(sheet.result_json)
        quantity = decimal(values.quantity)
        measured = decimal(sheet_result["quantity"]) * unit_factor(
            sheet_result["unit"], line["unit"]
        )
        already = records(
            session,
            project.id,
            kind,
            contract_id=values.contract_id,
            item_code=values.item_code,
        )
        if any(
            p["measurement_id"] == values.measurement_id
            for _, p, _ in records(session, project.id, kind)
        ):
            raise ValueError(
                "This measurement was already recognized; supply a new checked sheet for additional work"
            )
        prior = sum((decimal(p["quantity"]) for _, p, _ in already), Decimal(0))
        if quantity <= 0 or quantity > measured:
            raise ValueError(
                "Accepted quantity must be positive and supported by the checked measurement"
            )
        gross_cost = valuation(line, prior + quantity) - valuation(line, prior)
        incorporated, incorporated_sources = 0, []
        if len(set(values.incorporated_acceptance_ids)) != len(
            values.incorporated_acceptance_ids
        ):
            raise ValueError("Duplicate incorporated-material sources")
        if values.incorporated_acceptance_ids and not values.incorporation_evidence:
            raise ValueError(
                "Material incorporation needs explicit measurement and drawing evidence"
            )
        used_sources = {
            identity
            for _, payload, _ in records(session, project.id, kind)
            for identity in payload.get("incorporated_acceptance_ids", [])
        }
        for identity in values.incorporated_acceptance_ids:
            source_record, source_payload, source_result = approved(
                session, identity, "ACCEPTANCE", project.id
            )
            allocation = session.scalar(
                select(cm.CertificateAllocation).where(
                    cm.CertificateAllocation.acceptance_id == identity
                )
            )
            certificate = (
                session.get(c.ControlRecord, allocation.certificate_id)
                if allocation
                else None
            )
            certificate_payload = (
                json.loads(certificate.payload_json) if certificate else {}
            )
            if (
                identity in used_sources
                or certificate_payload.get("contract_id") != values.contract_id
                or identity
                not in certificate_payload.get("materials_acceptance_ids", [])
                or certificate_payload.get("recognition_date", "9999")
                > str(values.recognition_date)
            ):
                raise ValueError(
                    "Only unused materials previously certified on site under this contract may be incorporated"
                )
            incorporated += source_result["amount_minor"]
            incorporated_sources.append(
                {
                    "id": identity,
                    "hash": source_record.snapshot_hash,
                    "amount_minor": source_result["amount_minor"],
                }
            )
        if incorporated > gross_cost:
            raise ValueError(
                "Previously recognized materials exceed this work valuation; reconcile the scope before recognition"
            )
        amount = gross_cost - incorporated
        result.update(
            amount_minor=amount,
            amount=money(amount),
            gross_cost=money(gross_cost),
            incorporated_minor=incorporated,
            incorporated_sources=incorporated_sources,
            quantity=published(quantity),
            unit=line["unit"],
            cost_code_id=line["cost_code_id"],
            source={
                **result["source"],
                "measurement": digest(
                    {
                        "inputs": sheet.fields_json,
                        "result": sheet.result_json,
                        "checker": sheet.checked_by,
                    }
                ),
            },
        )
    elif kind == "INTERIM_CERTIFICATE":
        unique_reference(session, project.id, kind, values.number, values.contract_id)
        if values.recognition_date > finance.business_date():
            raise ValueError("Certificate recognition date cannot be in the future")
        if len({v.item_code for v in values.lines}) != len(values.lines):
            raise ValueError("Certificate item codes must be unique")
        prior_records = records(
            session, project.id, kind, contract_id=values.contract_id
        )
        if (
            prior_records
            and str(values.recognition_date) < prior_records[-1][1]["recognition_date"]
        ):
            raise ValueError(
                "A cumulative certificate cannot precede the previous certificate's recognition date"
            )
        previous = (
            prior_records[-1][2]
            if prior_records
            else {
                "cumulative_work_minor": 0,
                "materials_minor": 0,
                "cumulative_quantities": {},
            }
        )
        cumulative, quantities = 0, {}
        for item in values.lines:
            if item.item_code not in lines:
                raise ValueError("Certificate references an unauthorized item")
            quantity = decimal(item.cumulative_quantity)
            if quantity < decimal(
                previous["cumulative_quantities"].get(item.item_code, "0")
            ):
                raise ValueError(
                    "Cumulative work cannot decrease; use a separately approved correcting event"
                )
            cumulative += valuation(lines[item.item_code], quantity)
            quantities[item.item_code] = published(quantity)
        if set(previous["cumulative_quantities"]) - set(quantities):
            raise ValueError(
                "Retain previously certified items in cumulative certificates"
            )
        materials = minor(values.materials_on_site)
        if materials and not contract.get("materials_on_site_allowed", False):
            raise ValueError(
                "This contract does not authorize materials-on-site certification"
            )
        if materials < 0 or (materials and not values.materials_evidence):
            raise ValueError(
                "Materials on site require nonnegative valuation and explicit eligibility evidence"
            )
        gross = (
            cumulative
            - previous["cumulative_work_minor"]
            + materials
            - previous["materials_minor"]
        )
        if gross < 0 or (
            gross == 0 and cumulative == previous["cumulative_work_minor"]
        ):
            raise ValueError(
                "Current certification must add value or record supported materials incorporation"
            )
        adjustment = minor(values.adjustment)
        if adjustment and not values.adjustment_reason:
            raise ValueError("Certificate adjustments require an explicit reason")
        recovery = minor(values.advance_recovery)
        if recovery < 0 or recovery > minor(
            Decimal(gross) / 100 * decimal(contract["advance_recovery_percent"]) / 100
        ):
            raise ValueError("Advance recovery exceeds the contract percentage")
        if recovery:
            if values.advance_assignment_id is None:
                raise ValueError("Advance recovery requires an independently approved contract assignment")
            assignment, assignment_payload, allocation = approved(
                session, values.advance_assignment_id, "ADVANCE_ASSIGNMENT", project.id)
            if assignment_payload["contract_id"] != values.contract_id:
                raise ValueError("Advance assignment belongs to a different contract")
            if (values.advance_source_id is not None
                    and values.advance_source_id != assignment_payload["advance_source_id"]):
                raise ValueError("Advance journal conflicts with the approved contract assignment")
            source, _, _ = sourced_advance(session, project, contract, assignment_payload["advance_source_id"])
            if source.business_date > str(values.recognition_date):
                raise ValueError("Certificate cannot recover an advance before its source date")
            used = sum(
                r[2].get("advance_minor", 0)
                for r in records(session, project.id, kind)
                if r[1].get("advance_assignment_id") == assignment.id
            )
            certificate_ids={r.id for r,p,_ in records(session,project.id,kind)
                if p.get('advance_assignment_id')==assignment.id}
            used-=sum(r['advance_minor'] for _,p,r in records(session,project.id,'CERTIFICATE_CORRECTION')
                if p['certificate_id'] in certificate_ids)
            if recovery > allocation["amount_minor"] - used:
                raise ValueError(
                    "Advance recovery exceeds the sourced unrecouped balance"
                )
            result["advance_hash"] = source.snapshot_hash
            result["advance_assignment_hash"] = assignment.snapshot_hash
        retention = minor(
            Decimal(gross) / 100 * decimal(contract["retention_percent"]) / 100
        )
        tax = minor(Decimal(gross) / 100 * decimal(contract["tax_percent"]) / 100)
        current = gross + tax - retention - recovery + adjustment
        if current < 0:
            raise ValueError(
                "Negative net certificates require a separately supported credit or correcting event"
            )
        acceptance_sources = []
        if len(set(values.acceptance_ids)) != len(values.acceptance_ids):
            raise ValueError("Duplicate acceptance references")
        if contract["direction"] == "SUPPLIER":
            if len(set(values.materials_acceptance_ids)) != len(
                values.materials_acceptance_ids
            ) or not set(values.materials_acceptance_ids) <= set(values.acceptance_ids):
                raise ValueError(
                    "On-site material sources must be distinct current acceptance references"
                )
            total, new_materials, incorporated_materials = 0, 0, 0
            for identity in values.acceptance_ids:
                row = accounting.scoped(session, c.ControlRecord, identity, project.id)
                if row.status != "APPROVED" or row.kind not in (
                    "WORK_ACCEPTANCE",
                    "ACCEPTANCE",
                ):
                    raise ValueError("Certificate needs approved acceptance evidence")
                payload, calculated = (
                    json.loads(row.payload_json),
                    json.loads(row.calculated_json),
                )
                if payload["recognition_date"] > str(values.recognition_date):
                    raise ValueError(
                        "Certificate cannot precede its supporting acceptance date"
                    )
                if (
                    row.kind == "WORK_ACCEPTANCE"
                    and payload["contract_id"] != values.contract_id
                ):
                    raise ValueError("Accepted work belongs to another contract")
                if row.id in values.materials_acceptance_ids:
                    if row.kind != "ACCEPTANCE":
                        raise ValueError(
                            "On-site materials require confirmed delivery acceptance"
                        )
                    new_materials += calculated["amount_minor"]
                if row.kind == "WORK_ACCEPTANCE":
                    incorporated_materials += calculated.get("incorporated_minor", 0)
                if row.kind == "ACCEPTANCE":
                    receipt_line = session.get(
                        m.ReceiptLine, payload["receipt_line_id"]
                    )
                    receipt = session.get(m.GoodsReceipt, receipt_line.receipt_id)
                    po = session.get(m.PurchaseOrder, receipt.po_id)
                    pol = session.scalar(
                        select(m.POLine).where(
                            m.POLine.po_id == po.id,
                            m.POLine.item_code == receipt_line.item_code,
                        )
                    )
                    if (
                        po.supplier_id != contract["supplier_id"]
                        or (
                            row.id not in values.materials_acceptance_ids
                            and receipt_line.item_code not in lines
                        )
                        or po.currency != project.currency
                        or not pol
                        or (
                            row.id not in values.materials_acceptance_ids
                            and pol.description.strip().casefold()
                            != lines[receipt_line.item_code]["description"]
                            .strip()
                            .casefold()
                        )
                    ):
                        raise ValueError(
                            "Accepted delivery is incompatible with this contract"
                        )
                    if row.id not in values.materials_acceptance_ids:
                        unit_factor(
                            receipt_line.unit, lines[receipt_line.item_code]["unit"]
                        )
                    recognized = session.scalar(
                        select(c.Recognition).where(c.Recognition.record_id == row.id)
                    )
                    if recognized.invoice_id or session.scalar(
                        select(c.RecognitionAllocation.id).where(
                            c.RecognitionAllocation.recognition_id == recognized.id
                        )
                    ):
                        raise ValueError(
                            "Acceptance already reconciled to a supplier invoice"
                        )
                    if any(
                        a.receipt_line_id == receipt_line.id
                        for a, _, _, _ in finance.used_allocations(session, project.id)
                    ):
                        raise ValueError(
                            "Acceptance already reserved or consumed by a payment"
                        )
                if session.scalar(
                    select(cm.CertificateAllocation.id).where(
                        cm.CertificateAllocation.acceptance_id == row.id
                    )
                ):
                    raise ValueError(
                        "Acceptance already certified; do not recognize it twice"
                    )
                total += calculated["amount_minor"]
                acceptance_sources.append(
                    {
                        "id": row.id,
                        "hash": row.snapshot_hash,
                        "amount_minor": calculated["amount_minor"],
                    }
                )
            if total != gross + adjustment:
                raise ValueError(
                    "Current supplier certification must reconcile to independently accepted cost including adjustments"
                )
            if (
                materials
                != previous["materials_minor"] + new_materials - incorporated_materials
            ):
                raise ValueError(
                    "Held materials must reconcile incoming accepted materials and recorded incorporation"
                )
        elif values.acceptance_ids:
            raise ValueError(
                "Customer revenue is independently certified; supplier acceptance references cannot confer customer authority"
            )
        result.update(
            direction=contract["direction"],
            cumulative_work=money(cumulative),
            cumulative_work_minor=cumulative,
            previous_work=money(previous["cumulative_work_minor"]),
            current_work=money(cumulative - previous["cumulative_work_minor"]),
            cumulative_quantities=quantities,
            materials_minor=materials,
            current_gross=money(gross),
            gross_minor=gross,
            tax_minor=tax,
            retention_minor=retention,
            advance_minor=recovery,
            adjustment_minor=adjustment,
            amount_minor=current,
            amount=money(current),
            acceptances=acceptance_sources,
            source={
                **result["source"],
                "previous_certificates": [
                    {"id": r.id, "hash": r.snapshot_hash} for r, _, _ in prior_records
                ],
            },
        )
    else:
        raise ValueError("Unsupported commercial control")
    return result


def apply(session, actor, project, record, values, result):
    if values.kind == "COMMERCIAL_CONTRACT":
        for line in values.lines:
            if line.boq_item_id:
                cost_coding.ensure(
                    session, project.id, "BOQ_ITEM", line.boq_item_id, line.cost_code_id
                )
    elif values.kind == "PURCHASE_AWARD":
        # This document is generated from an independently approved control, not extracted supplier text.
        document = m.Document(
            project_id=project.id,
            document_type="PO",
            original_filename=f"award-{record.id}.json",
            storage_name="",
            sha256=record.snapshot_hash,
            extraction_status="CONFIRMED",
            extracted_json=canonical({"commercial_control": record.id, **result}),
            text=canonical({"commercial_control": record.id, **result}),
            confirmed_by=actor.id,
            reviewed_by=actor.id,
        )
        session.add(document)
        session.flush()
        contract = json.loads(
            session.get(c.ControlRecord, result["contract_id"]).payload_json
        )
        po = m.PurchaseOrder(
            project_id=project.id,
            document_id=document.id,
            supplier_id=result["supplier_id"],
            number=values.po_number,
            currency=project.currency,
            tax_percent=contract["tax_percent"],
            retention_percent=contract["retention_percent"],
            approved=True,
        )
        session.add(po)
        session.flush()
        session.add(
            m.POLine(
                po_id=po.id,
                item_code=result["item_code"],
                description=result["description"],
                quantity=result["quantity"],
                unit=result["unit"],
                rate=result["rate"],
            )
        )
        session.add(
            cm.CommercialPublication(
                project_id=project.id,
                control_id=record.id,
                source_type="PO",
                source_id=po.id,
            )
        )
        code = next(
            line["cost_code_id"]
            for line in contract["lines"]
            if line["code"] == result["item_code"]
        )
        session.flush()
        line = session.scalar(select(m.POLine).where(m.POLine.po_id == po.id))
        session.add(
            c.CostCodeLink(
                project_id=project.id,
                cost_code_id=code,
                source_type="PO_LINE",
                source_id=line.id,
            )
        )
        audit.append(
            session,
            actor,
            "COMMERCIAL_PO_PUBLISHED",
            "purchase_order",
            po.id,
            {"control_id": record.id, "snapshot_hash": record.snapshot_hash},
            project.id,
        )
    elif values.kind == "WORK_ACCEPTANCE":
        accounting.post(
            session,
            project,
            f"control:{record.id}",
            [
                ("PROJECT_COST", result["amount_minor"], 0, result["cost_code_id"]),
                (
                    "ACCRUED_LIABILITY",
                    0,
                    result["amount_minor"],
                    result["cost_code_id"],
                ),
            ],
            {"kind": values.kind, "snapshot_hash": record.snapshot_hash},
            values.recognition_date,
            record.id,
        )
    elif values.kind == "INTERIM_CERTIFICATE":
        contract = json.loads(
            session.get(c.ControlRecord, values.contract_id).payload_json
        )
        amount, tax, retention, recovery = (
            result[k]
            for k in ("amount_minor", "tax_minor", "retention_minor", "advance_minor")
        )
        gross = result["gross_minor"] + result["adjustment_minor"]
        if result["direction"] == "CUSTOMER":
            entries = [
                ("ACCOUNTS_RECEIVABLE", amount, 0, None),
                ("RETENTION_RECEIVABLE", retention, 0, None),
                ("CUSTOMER_ADVANCE", recovery, 0, None),
                ("REVENUE", 0, gross, None),
                ("OUTPUT_TAX", 0, tax, None),
            ]
            ar = c.Receivable(
                project_id=project.id,
                certificate_id=record.id,
                amount_minor=amount,
                retention_minor=retention,
                currency=project.currency,
                due_date=str(values.due_date) if values.due_date else None,
            )
            session.add(ar)
            session.flush()
            obligations.sync(
                session,
                project,
                "RECEIVABLE",
                ar.id,
                "INFLOW",
                "RECEIVABLE",
                amount,
                ar.due_date,
            )
        else:
            policy = json.loads(
                session.get(c.ControlRecord, contract["policy_id"]).payload_json
            )
            weights = {}
            for source in result["acceptances"]:
                acceptance = session.get(c.ControlRecord, source["id"])
                cost_id = (
                    json.loads(acceptance.calculated_json)
                    if acceptance.kind == "WORK_ACCEPTANCE"
                    else json.loads(acceptance.payload_json)
                )["cost_code_id"]
                weights[cost_id] = weights.get(cost_id, 0) + source["amount_minor"]
            entries = [
                ("ACCRUED_LIABILITY", value, 0, code) for code, value in weights.items()
            ]
            for account, total in (
                ("ACCOUNTS_PAYABLE", amount),
                ("RETENTION_PAYABLE", retention),
                ("ADVANCE", recovery),
            ):
                entries += [
                    (account, 0, value, code)
                    for code, value in cost_coding.spread(total, weights)
                ]
            if tax:
                entries += [
                    (
                        "RECOVERABLE_TAX"
                        if policy["tax_treatment"] == "RECOVERABLE"
                        else "PROJECT_COST",
                        value,
                        0,
                        code,
                    )
                    for code, value in cost_coding.spread(
                        tax, {} if policy["tax_treatment"] == "RECOVERABLE" else weights
                    )
                ]
            payable = c.Payable(
                project_id=project.id,
                supplier_id=contract["supplier_id"],
                record_id=record.id,
                amount_minor=amount,
                retention_minor=retention,
                currency=project.currency,
                due_date=str(values.due_date) if values.due_date else None,
            )
            session.add(payable)
            session.flush()
            obligations.sync(
                session,
                project,
                "PAYABLE",
                payable.id,
                "OUTFLOW",
                "PROCUREMENT",
                amount,
                payable.due_date,
            )
            for source in result["acceptances"]:
                session.add(
                    cm.CertificateAllocation(
                        certificate_id=record.id,
                        acceptance_id=source["id"],
                        amount_minor=source["amount_minor"],
                    )
                )
        accounting.post(
            session,
            project,
            f"control:{record.id}",
            entries,
            {"kind": values.kind, "snapshot_hash": record.snapshot_hash},
            values.recognition_date,
            record.id,
        )
    elif values.kind == "CONTRACT_VARIATION":
        # An estimate and a commitment are different: do not create a payable or cash movement here.
        audit.append(
            session,
            actor,
            "CONTRACT_SCOPE_VARIED",
            "control",
            values.contract_id,
            {
                "variation_id": record.id,
                "approved_value": result["approved_value"],
                "time_impact_days": values.time_impact_days,
                "forecast_due_date": str(values.forecast_due_date)
                if values.forecast_due_date
                else None,
                "budget_amended": False,
                "existing_procurement_amended": False,
            },
            project.id,
        )
