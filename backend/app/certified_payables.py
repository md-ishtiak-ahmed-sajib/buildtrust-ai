"""Certified-payable validation; cash execution is owned by payments.execute."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from . import audit, control_models as c, finance, models as m
from .money import canonical, digest
from .security import DomainError, project_access, require_role


def sources(session, proposal, settings):
    payable = session.get(c.Payable, proposal.payable_id)
    certificate = session.get(c.ControlRecord, payable.record_id)
    supplier = session.get(m.Supplier, payable.supplier_id)
    project = session.get(m.Project, payable.project_id)
    return {
        "payable_id": payable.id,
        "certificate_id": certificate.id,
        "currency": proposal.currency,
        "proposal_version": proposal.version,
        "expires_at": proposal.expires_at,
        "amount_minor": proposal.amount_minor,
        "beneficiary_fingerprint": proposal.beneficiary_fingerprint,
        "payable": {
            "version": payable.version,
            "amount": payable.amount_minor,
            "paid": payable.paid_minor,
            "credit": payable.credit_minor,
            "released": payable.retention_released_minor,
        },
        "certificate": {
            "status": certificate.status,
            "snapshot_hash": certificate.snapshot_hash,
            "content_hash": digest(
                {
                    "payload": certificate.payload_json,
                    "calculated": certificate.calculated_json,
                    "contributors": certificate.contributors_json,
                }
            ),
        },
        "supplier": {
            "id": supplier.id,
            "version": supplier.version,
            "approved": supplier.approved,
            "beneficiary_fingerprint": supplier.beneficiary_fingerprint,
        },
        "policy": {
            "reserve": project.reserve_minor,
            "delay": settings.receivable_delay_days,
            "pressure": settings.cost_pressure_percent,
            "admin_ceiling": settings.admin_ceiling,
        },
    }


def check(session, proposal, settings, reservation=True):
    payable = session.get(c.Payable, proposal.payable_id)
    if not payable or payable.project_id != proposal.project_id or payable.invoice_id:
        raise DomainError(
            409,
            "INVALID_CERTIFIED_PAYABLE",
            "An explicit certified supplier payable is required.",
        )
    certificate = session.get(c.ControlRecord, payable.record_id)
    supplier = session.get(m.Supplier, payable.supplier_id)
    if (
        certificate.kind != "INTERIM_CERTIFICATE"
        or certificate.status != "APPROVED"
        or certificate.snapshot_hash != digest(json.loads(certificate.snapshot_json))
    ):
        raise DomainError(
            409, "CERTIFICATE_INVALID", "Approved certificate evidence is required."
        )
    bound = json.loads(certificate.snapshot_json)
    if (
        bound["payload"] != json.loads(certificate.payload_json)
        or bound["calculated"] != json.loads(certificate.calculated_json)
        or bound["contributors"] != json.loads(certificate.contributors_json)
    ):
        raise DomainError(
            409,
            "CERTIFICATE_INVALID",
            "Certificate contents differ from independent approval.",
        )
    if (
        not supplier.approved
        or supplier.beneficiary_fingerprint != proposal.beneficiary_fingerprint
    ):
        raise DomainError(
            409,
            "BENEFICIARY_CHANGED",
            "Supplier beneficiary requires fresh verification and approval.",
        )
    if (
        proposal.currency != payable.currency
        or proposal.supplier_id != payable.supplier_id
    ):
        raise DomainError(
            409, "PAYABLE_CHANGED", "Payment source differs from its certified payable."
        )
    if (
        not 0
        < proposal.amount_minor
        <= payable.amount_minor - payable.paid_minor - payable.credit_minor
    ):
        raise DomainError(
            409, "OVERPAYMENT", "Installment exceeds the certified unpaid balance."
        )
    report = finance.forecast(
        session,
        session.get(m.Project, payable.project_id),
        settings,
        proposed_minor=proposal.amount_minor,
        payable_id=payable.id,
        exclude_proposal=proposal.id,
    )
    if not report["payment_eligible"]:
        raise DomainError(
            409,
            "PAYMENT_BLOCKED",
            "Current cash or reserve policy blocks this certified installment.",
        )
    if reservation:
        cash = session.scalar(
            select(m.Reservation).where(
                m.Reservation.proposal_id == proposal.id,
                m.Reservation.state == "ACTIVE",
            )
        )
        if not cash or cash.amount_minor != proposal.amount_minor:
            raise DomainError(
                409,
                "RESERVATION_INVALID",
                "An exact active cash reservation is required.",
            )
    return payable


def prepare(session, payable, settings, actor, amount):
    from . import payments

    project_access(session, actor, payable.project_id, write=True)
    require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
    payments.expire(session)
    old = session.scalar(
        select(m.Proposal).where(
            m.Proposal.payable_id == payable.id,
            m.Proposal.status.in_(("PENDING_APPROVAL", "APPROVED")),
        )
    )
    if old:
        if old.amount_minor != amount:
            raise DomainError(
                409,
                "ACTIVE_INSTALLMENT",
                "One active installment is allowed per payable.",
            )
        return old
    supplier = session.get(m.Supplier, payable.supplier_id)
    proposal = m.Proposal(
        payable_id=payable.id,
        project_id=payable.project_id,
        supplier_id=payable.supplier_id,
        amount_minor=amount,
        currency=payable.currency,
        beneficiary_fingerprint=supplier.beneficiary_fingerprint,
        status="CREATED",
        requested_by=actor.id,
        snapshot_json="{}",
        snapshot_hash="",
        expires_at=(
            datetime.now(timezone.utc) + timedelta(minutes=settings.approval_minutes)
        )
        .isoformat()
        .replace("+00:00", "Z"),
    )
    session.add(proposal)
    session.flush()
    check(session, proposal, settings, reservation=False)
    proposal.status = "PENDING_APPROVAL"
    proposal.snapshot_json = canonical(
        payments.snapshot(session, None, proposal, settings)
    )
    proposal.snapshot_hash = digest(json.loads(proposal.snapshot_json))
    session.add(m.Reservation(proposal_id=proposal.id, amount_minor=amount))
    audit.append(
        session,
        actor,
        "PAYMENT_PENDING_APPROVAL",
        "proposal",
        proposal.id,
        {
            "payable_id": payable.id,
            "certificate_id": payable.record_id,
            "snapshot_hash": proposal.snapshot_hash,
        },
        payable.project_id,
    )
    return proposal
