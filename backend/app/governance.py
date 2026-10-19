import json

from sqlalchemy import select

from . import advanced_models as a
from . import audit, payments
from . import models as m
from .accounting import scoped
from .advanced_schemas import TakeoffInput
from .money import canonical, digest
from .price_providers import safe_url
from .security import DomainError
from .money import decimal, published
from .advanced_math import unit_factor
from decimal import Decimal

KINDS = {"SUPPLIER_CHANGE", "RULE_PROFILE", "COST_CODE_ASSIGNMENT"}


def calculate_profile(data, profile):
    from .advanced_math import calculate_takeoff

    rules = json.loads(profile.rules_json)
    if rules.get("project_id") and rules["project_id"] != data.project_id:
        raise ValueError("Measurement rule belongs to another project")
    if (
        profile.verification_status == "REVIEWED_PROJECT_RULES"
        and data.calculation not in rules.get("templates", [])
    ):
        raise ValueError("This template is outside the reviewed profile scope")
    applicable = [rule for rule in rules.get("opening_rules", []) if rule["calculation"] == data.calculation]
    applied = []
    effective = data
    if data.openings:
        if profile.verification_status != "REVIEWED_PROJECT_RULES" or len(applicable) != 1:
            raise ValueError("Individual openings require an independently reviewed rule for this calculation")
        if decimal(data.deduction) or decimal(data.dimensions.get("opening_area", "0")):
            raise ValueError("Use the reviewed opening schedule or an explicit deduction, not both")
        rule = applicable[0]
        factor = unit_factor(data.dimension_unit, "m")
        threshold = decimal(rule["threshold_m2"])
        total = Decimal(0)
        for opening in data.openings:
            width, height, count = decimal(opening.width), decimal(opening.height), decimal(opening.count)
            if width <= 0 or height <= 0 or count <= 0 or count != count.to_integral_value():
                raise ValueError("Opening dimensions must be positive and count a positive whole number")
            each = width * height * factor**2
            deduct = each > threshold if rule["comparison"] == "GT" else each >= threshold
            if deduct:
                total += each * count
            applied.append({"reference": opening.reference, "each_area_m2": published(each), "count": opening.count,
                            "deducted": deduct, "threshold_m2": rule["threshold_m2"], "comparison": rule["comparison"]})
        if data.calculation == "MASONRY":
            total *= decimal(data.dimensions.get("thickness", "0")) * factor
        if rule["multiply_selected_faces"]:
            total *= decimal(data.dimensions["faces"])
        effective = data.model_copy(update={"deduction": str(total), "deduction_reason": "Independently reviewed profile opening rule; schedule counts cover the complete sheet"})
    result = calculate_takeoff(effective)
    if applied:
        result["profile_applied_rules"] = applied
    result["profile_snapshot"] = {
        "name": profile.name,
        "edition": profile.edition,
        "source_url": profile.source_url,
        "rules": rules,
        "verification_status": profile.verification_status,
    }
    if profile.verification_status == "REVIEWED_PROJECT_RULES":
        result["warnings"].append(
            "Only the recorded project rule was independently reviewed; external professional acceptance remains required."
        )
    return result


def build(session, project, values):
    if values.kind == "COST_CODE_ASSIGNMENT":
        from . import accounting, cost_coding

        row, version, fingerprint = cost_coding.source(
            session, project.id, values.source_type, values.source_id
        )
        cost = accounting.code(session, values.cost_code_id, project.id)
        existing = cost_coding.link(
            session, project.id, values.source_type, values.source_id
        )
        if (
            version != values.expected_source_version
            or (existing.version if existing else None) != values.expected_link_version
        ):
            raise DomainError(
                409, "VERSION_CONFLICT", "Cost-code source or mapping changed."
            )
        return {
            "source_hash": fingerprint,
            "source_version": version,
            "cost_code_version": cost.version,
            "previous_code_id": existing.cost_code_id if existing else None,
            "cost_code_id": cost.id,
            "notice": "Changes future source lineage; historical journals and receipts are preserved.",
        }
    if values.kind == "SUPPLIER_CHANGE":
        if not values.verification_attested:
            raise ValueError(
                "Beneficiary verification attestation and independent evidence are required"
            )
        before = None
        if values.supplier_id:
            supplier = scoped(session, m.Supplier, values.supplier_id, project.id)
            if supplier.version != values.expected_supplier_version:
                raise DomainError(409, "VERSION_CONFLICT", "Supplier changed.")
            if supplier.code != values.code:
                raise ValueError("Supplier identity code is immutable")
            before = {
                "name": supplier.name,
                "version": supplier.version,
                "beneficiary_fingerprint": supplier.beneficiary_fingerprint,
                "approved": supplier.approved,
            }
        elif session.scalar(
            select(m.Supplier.id).where(
                m.Supplier.project_id == project.id, m.Supplier.code == values.code
            )
        ):
            raise DomainError(
                409, "DUPLICATE_SUPPLIER", "Supplier code already exists."
            )
        return {
            "before": before,
            "after": {
                "code": values.code,
                "name": values.name,
                "beneficiary_fingerprint": digest(values.beneficiary_token),
            },
            "notice": "Independently verified sandbox beneficiary. Invoice text cannot publish supplier master changes.",
        }
    if values.kind == "RULE_PROFILE":
        safe_url(values.source_url)
        allowed = set(TakeoffInput.model_fields["calculation"].annotation.__args__)
        if not set(values.templates) <= allowed or len(set(values.templates)) != len(
            values.templates
        ):
            raise ValueError("Unknown or duplicate deterministic calculation template")
        if len({rule.calculation for rule in values.opening_rules}) != len(values.opening_rules):
            raise ValueError("Only one opening rule may apply to each template")
        for rule in values.opening_rules:
            if rule.calculation not in values.templates or decimal(rule.threshold_m2) < 0:
                raise ValueError("Opening rules require an enabled template and a nonnegative sourced area threshold")
            if rule.multiply_selected_faces and rule.calculation != "FINISHES":
                raise ValueError("Selected-face multiplication is supported only for finishes")
        code = f"{values.code}_P{project.id}"
        if session.scalar(
            select(a.MeasurementProfile.id).where(a.MeasurementProfile.code == code)
        ):
            raise ValueError(
                "Profile codes are immutable; use a new edition-specific code"
            )
        return {
            "profile_code": code,
            "edition": values.edition,
            "rule_reference": values.rule_reference,
            "rule_policy": "explicit-geometry-v1",
            "professional_acceptance": "REQUIRES_EXTERNAL_ACCEPTANCE",
            "notice": "Approval covers only the recorded templates and explicit measurement rule, not complete compliance with a published standard.",
        }
    raise ValueError("Unsupported governance control")


def apply(session, actor, project, record, values, result):
    if values.kind == "COST_CODE_ASSIGNMENT":
        from . import cost_coding, control_models as c

        existing = cost_coding.link(
            session, project.id, values.source_type, values.source_id
        )
        if existing:
            existing.cost_code_id, existing.version = (
                values.cost_code_id,
                existing.version + 1,
            )
        else:
            session.add(
                c.CostCodeLink(
                    project_id=project.id,
                    source_type=values.source_type,
                    source_id=values.source_id,
                    cost_code_id=values.cost_code_id,
                )
            )
        return
    if values.kind == "SUPPLIER_CHANGE":
        supplier = (
            session.get(m.Supplier, values.supplier_id)
            if values.supplier_id
            else m.Supplier(
                project_id=project.id,
                code=values.code,
                name=values.name,
                beneficiary_token=values.beneficiary_token,
                beneficiary_fingerprint=digest(values.beneficiary_token),
            )
        )
        if not values.supplier_id:
            session.add(supplier)
            session.flush()
        material = (
            supplier.beneficiary_fingerprint != digest(values.beneficiary_token)
            or supplier.name != values.name
        )
        supplier.name = values.name
        supplier.beneficiary_token = values.beneficiary_token
        supplier.beneficiary_fingerprint = digest(values.beneficiary_token)
        supplier.approved = True
        supplier.version += 1
        if material:
            for proposal in session.scalars(
                select(m.Proposal).where(
                    m.Proposal.supplier_id == supplier.id,
                    m.Proposal.status.in_(("PENDING_APPROVAL", "APPROVED")),
                )
            ):
                proposal.status = "BLOCKED"
                proposal.version += 1
                payments.release(session, proposal)
                audit.append(
                    session,
                    actor,
                    "SUPPLIER_CHANGE_INVALIDATED_APPROVAL",
                    "proposal",
                    proposal.id,
                    {"supplier_control": record.id},
                    project.id,
                )
        audit.append(
            session,
            actor,
            "SUPPLIER_MASTER_PUBLISHED",
            "supplier",
            supplier.id,
            {
                "control_id": record.id,
                "version": supplier.version,
                "beneficiary_fingerprint": supplier.beneficiary_fingerprint,
            },
            project.id,
        )
    else:
        session.add(
            a.MeasurementProfile(
                code=result["profile_code"],
                name=values.name,
                edition=values.edition,
                source_url=values.source_url,
                verification_status="REVIEWED_PROJECT_RULES",
                rules_json=canonical(
                    {
                        "project_id": project.id,
                        "control_id": record.id,
                        "snapshot_hash": record.snapshot_hash,
                        "templates": values.templates,
                        "deduction_rule": values.deduction_rule,
                        "opening_rules": [rule.model_dump(mode="json") for rule in values.opening_rules],
                        "rule_reference": values.rule_reference,
                        "reviewer_evidence": values.reviewer_evidence,
                        "professional_acceptance": "REQUIRES_EXTERNAL_ACCEPTANCE",
                    }
                ),
            )
        )
