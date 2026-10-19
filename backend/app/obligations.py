"""One source obligation, with an optional dated cash movement; missing dates stay missing."""

from sqlalchemy import select
from . import control_models as c, models as m


def sync(
    session,
    project,
    source_type,
    source_id,
    direction,
    category,
    amount,
    due_date,
    invoice_id=None,
    clear_due_date=False,
):
    movement = None
    row = session.scalar(
        select(c.Obligation).where(
            c.Obligation.project_id == project.id,
            c.Obligation.source_type == source_type,
            c.Obligation.source_id == source_id,
        )
    )
    if not row and invoice_id:
        movement = session.scalar(
            select(m.CashMovement).where(m.CashMovement.invoice_id == invoice_id)
        )
        if movement:
            row = session.scalar(
                select(c.Obligation).where(c.Obligation.cash_movement_id == movement.id)
            )
            if row:
                row.source_type, row.source_id = source_type, source_id
    if not row:
        row = c.Obligation(
            project_id=project.id,
            source_type=source_type,
            source_id=source_id,
            direction=direction,
            category=category,
            amount_minor=amount,
            currency=project.currency,
            due_date=due_date,
            cash_movement_id=movement.id if movement else None,
        )
        session.add(row)
        session.flush()
    row.amount_minor = amount
    row.category = category
    row.version += 1
    # The original contract date remains authoritative unless an explicit new
    # date is supplied; no day is invented for an unscheduled obligation.
    if clear_due_date:
        row.due_date = None
    elif due_date:
        row.due_date = str(due_date)
    if row.cash_movement_id:
        movement = session.get(m.CashMovement, row.cash_movement_id)
        movement.amount_minor = amount
        movement.kind = direction
        movement.currency = project.currency
        if row.due_date:
            movement.due_date = row.due_date
        movement.settled = amount <= 0 or row.due_date is None
    elif row.due_date:
        movement = m.CashMovement(
            project_id=project.id,
            invoice_id=invoice_id,
            kind=direction,
            amount_minor=amount,
            currency=project.currency,
            due_date=row.due_date,
            description=f"{category.title()} obligation {source_type} #{source_id}",
            settled=amount <= 0,
            cost_pressure=False,
        )
        session.add(movement)
        session.flush()
        row.cash_movement_id = movement.id
    return row
