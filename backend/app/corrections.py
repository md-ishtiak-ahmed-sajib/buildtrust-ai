"""Append financial/cost corrections with independent reviews and no cash refunds."""

import json
from sqlalchemy import select
from . import accounting, audit, finance, obligations, cost_coding
from . import models as m, control_models as c, commercial_models as cm
from .money import minor, money
from .security import DomainError

KINDS = {"CERTIFICATE_CORRECTION", "ACCEPTED_COST_CORRECTION"}


def events(session, project, kind):
    return [
        (row, json.loads(row.payload_json), json.loads(row.calculated_json))
        for row in session.scalars(
            select(c.ControlRecord).where(
                c.ControlRecord.project_id == project,
                c.ControlRecord.kind == kind,
                c.ControlRecord.status == "APPROVED",
            )
        )
    ]


def source(session, project, identity, kinds):
    record = accounting.scoped(session, c.ControlRecord, identity, project.id)
    if record.kind not in kinds or record.status != "APPROVED":
        raise ValueError("An independently approved source is required")
    return record, json.loads(record.payload_json), json.loads(record.calculated_json)


def build(session, project, values):
    if values.recognition_date > finance.business_date():
        raise ValueError("Corrections require an actual nonfuture recognition date")
    if values.kind == "ACCEPTED_COST_CORRECTION":
        correction, cp, cr = source(
            session, project, values.financial_correction_id, {"CERTIFICATE_CORRECTION"}
        )
        acceptance, ap, ar = source(
            session, project, values.acceptance_id, {"ACCEPTANCE", "WORK_ACCEPTANCE"}
        )
        if cr["direction"] != "SUPPLIER":
            raise ValueError(
                "Accepted-cost corrections require a supplier financial reversal"
            )
        allocation = session.scalar(
            select(cm.CertificateAllocation).where(
                cm.CertificateAllocation.certificate_id == cp["certificate_id"],
                cm.CertificateAllocation.acceptance_id == acceptance.id,
            )
        )
        if not allocation:
            raise ValueError("Acceptance is not part of this corrected certificate")
        code = (ar if acceptance.kind == "WORK_ACCEPTANCE" else ap)["cost_code_id"]
        previous = events(session, project.id, values.kind)
        used = sum(
            r["amount_minor"]
            for _, p, r in previous
            if p["financial_correction_id"] == correction.id
        )
        source_used = sum(
            r["amount_minor"]
            for _, p, r in previous
            if p["acceptance_id"] == acceptance.id
        )
        code_used = sum(
            r["amount_minor"]
            for _, p, r in previous
            if p["financial_correction_id"] == correction.id
            and r["cost_code_id"] == code
        )
        amount = accounting.positive(values.amount)
        available = next(
            (
                v["amount_minor"]
                for v in cr["base_by_code"]
                if v["cost_code_id"] == code
            ),
            0,
        )
        if amount > min(
            cr["base_minor"] - used,
            ar["amount_minor"] - source_used,
            available - code_used,
        ):
            raise ValueError(
                "Cost correction exceeds its restored accrual or original accepted cost"
            )
        if str(values.recognition_date) < max(
            ap["recognition_date"], cp["recognition_date"]
        ):
            raise ValueError(
                "Cost correction cannot precede its supporting financial/acceptance sources"
            )
        return {
            "amount_minor": amount,
            "amount": money(amount),
            "cost_code_id": code,
            "financial_hash": correction.snapshot_hash,
            "acceptance_hash": acceptance.snapshot_hash,
            "previous_restored_use_minor": used,
            "previous_source_use_minor": source_used,
            "notice": "Compensating cost/accrual entry only. Physical quantities and original evidence remain unchanged.",
        }
    original, payload, calculated = source(
        session,
        project,
        values.certificate_id,
        {"INTERIM_CERTIFICATE", "CUSTOMER_CERTIFICATE"},
    )
    if str(values.recognition_date) < payload["recognition_date"]:
        raise ValueError("A correction cannot precede certification")
    if any(
        p["reference"] == values.reference
        for _, p, _ in events(session, project.id, values.kind)
    ):
        raise ValueError("Correction reference was already approved")
    supplier = calculated.get("direction") == "SUPPLIER"
    balance = session.scalar(
        select(c.Payable if supplier else c.Receivable).where(
            (c.Payable.record_id if supplier else c.Receivable.certificate_id)
            == original.id
        )
    )
    if not balance or balance.version != values.expected_balance_version:
        raise DomainError(
            409,
            "VERSION_CONFLICT",
            "Certificate balance changed; reload and review again.",
        )
    parts = {
        name: minor(getattr(values, f"{name}_amount"))
        for name in ("base", "tax", "retention", "advance")
    }
    if any(value < 0 for value in parts.values()) or not any(parts.values()):
        raise ValueError(
            "Correction allocations must be nonnegative and contain an actual reversal"
        )
    caps = {
        "base": calculated.get("gross_minor", calculated.get("revenue_minor", 0))
        + calculated.get("adjustment_minor", 0),
        "tax": calculated.get("tax_minor", 0),
        "retention": calculated.get("retention_minor", 0),
        "advance": calculated.get("advance_minor", 0),
    }
    previous = events(session, project.id, values.kind)
    for _, p, r in previous:
        if p["certificate_id"] == original.id:
            for key in caps:
                caps[key] -= r[f"{key}_minor"]
    if supplier:
        for _, p, r in events(session, project.id, "CREDIT_NOTE"):
            if p["payable_id"] == balance.id:
                caps["base"] -= r.get("base_minor", r["amount_minor"])
                caps["tax"] -= r.get("tax_minor", 0)
                caps["retention"] -= r.get("retention_credit_minor", 0)
    net = parts["base"] + parts["tax"] - parts["retention"] - parts["advance"]
    if any(parts[key] > caps[key] for key in caps) or net < 0:
        raise ValueError(
            "Correction exceeds the source base/tax/retention/advance or has a negative net allocation"
        )
    held = balance.retention_minor - (
        balance.retention_released_minor if supplier else 0
    )
    if parts["retention"] > held:
        raise ValueError("Retention reversal exceeds the amount still held")
    weights = cost_coding.weights(session, balance) if supplier else {}
    treatment = "OUTPUT"
    if supplier:
        contract = json.loads(
            session.get(c.ControlRecord, payload["contract_id"]).payload_json
        )
        policy = json.loads(
            session.get(c.ControlRecord, contract["policy_id"]).payload_json
        )
        treatment = policy["tax_treatment"]
    return {
        "direction": "SUPPLIER" if supplier else "CUSTOMER",
        "balance_id": balance.id,
        "balance_version": balance.version,
        "source_hash": original.snapshot_hash,
        "amount_minor": net,
        "amount": money(net),
        **{f"{key}_minor": value for key, value in parts.items()},
        "tax_treatment": treatment,
        "source_weights": [
            {"cost_code_id": code, "amount_minor": amount}
            for code, amount in weights.items()
        ],
        "base_by_code": [
            {"cost_code_id": code, "amount_minor": amount}
            for code, amount in cost_coding.spread(parts["base"], weights)
        ],
        "notice": "Financial reversal only; accepted cost and physical entitlement require separate supported review.",
    }


def apply(session, actor, project, record, values, result):
    if values.kind == "ACCEPTED_COST_CORRECTION":
        amount, code = result["amount_minor"], result["cost_code_id"]
        entries = [
            ("ACCRUED_LIABILITY", amount, 0, code),
            ("PROJECT_COST", 0, amount, code),
        ]
    else:
        supplier = result["direction"] == "SUPPLIER"
        balance = session.get(
            c.Payable if supplier else c.Receivable, result["balance_id"]
        )
        outstanding = (
            balance.amount_minor
            - (balance.paid_minor if supplier else balance.received_minor)
            - balance.credit_minor
        )
        applied = min(outstanding, result["amount_minor"])
        excess = result["amount_minor"] - applied
        balance.credit_minor += applied
        if supplier:
            balance.supplier_credit_minor += excess
        else:
            balance.customer_credit_minor += excess
        balance.retention_minor -= result["retention_minor"]
        balance.version += 1
        weights = {
            v["cost_code_id"]: v["amount_minor"] for v in result["source_weights"]
        }
        entries = []

        def append(account, total, debit):
            for code, amount in cost_coding.spread(
                total,
                weights
                if supplier and account not in ("SUPPLIER_CREDIT", "RECOVERABLE_TAX")
                else {},
            ):
                entries.append(
                    (account, amount if debit else 0, 0 if debit else amount, code)
                )

        if supplier:
            append("ACCOUNTS_PAYABLE", applied, True)
            append("SUPPLIER_CREDIT", excess, True)
            append("RETENTION_PAYABLE", result["retention_minor"], True)
            append("ADVANCE", result["advance_minor"], True)
            append("ACCRUED_LIABILITY", result["base_minor"], False)
            append(
                "RECOVERABLE_TAX"
                if result["tax_treatment"] == "RECOVERABLE"
                else "PROJECT_COST",
                result["tax_minor"],
                False,
            )
            from .payments import release

            for proposal in session.scalars(
                select(m.Proposal).where(
                    m.Proposal.payable_id == balance.id,
                    m.Proposal.status.in_(("PENDING_APPROVAL", "APPROVED")),
                )
            ):
                proposal.status = "BLOCKED"
                proposal.version += 1
                release(session, proposal)
        else:
            append("REVENUE", result["base_minor"], True)
            append("OUTPUT_TAX", result["tax_minor"], True)
            append("ACCOUNTS_RECEIVABLE", applied, False)
            append("CUSTOMER_CREDIT", excess, False)
            append("RETENTION_RECEIVABLE", result["retention_minor"], False)
            append("CUSTOMER_ADVANCE", result["advance_minor"], False)
        obligations.sync(
            session,
            project,
            "PAYABLE" if supplier else "RECEIVABLE",
            balance.id,
            "OUTFLOW" if supplier else "INFLOW",
            "PROCUREMENT" if supplier else "RECEIVABLE",
            outstanding - applied,
            balance.due_date,
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
    audit.append(
        session,
        actor,
        "SUPPORTED_CORRECTION_POSTED",
        "control",
        record.id,
        {"kind": values.kind, "cash_changed": False},
        project.id,
    )
