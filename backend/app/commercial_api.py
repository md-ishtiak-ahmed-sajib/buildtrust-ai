"""Project-scoped commercial source register; mutations use independent controls."""

import json
from fastapi import APIRouter, Request
from sqlalchemy import select
from . import advanced_models as a, control_models as c, models as m
from .commercial import KINDS
from .security import project_access
from .interface_schemas import CommercialSources


def create_router(context):
    router = APIRouter(prefix="/api/v1/commercial", tags=["Commercial management"])

    @router.get("/sources", response_model=CommercialSources)
    def sources(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return {
                "materials": [
                    {"id": r.id, "label": f"{r.name} · {r.unit}"}
                    for r in session.scalars(
                        select(a.Material).where(
                            a.Material.project_id == project_id,
                            a.Material.active.is_(True),
                        )
                    )
                ],
                "observations": [
                    {
                        "id": r.id,
                        "label": f"#{r.id} · {json.loads(r.payload_json).get('supplier', '')} · {json.loads(r.payload_json).get('title', '')}",
                    }
                    for r in session.scalars(
                        select(a.PriceObservation).where(
                            a.PriceObservation.project_id == project_id,
                            a.PriceObservation.source_type == "SUPPLIER_QUOTE",
                        )
                    )
                ],
                "measurements": [
                    {
                        "id": r.id,
                        "label": f"#{r.id} · {json.loads(r.fields_json)['name']} · {json.loads(r.result_json)['quantity']} {json.loads(r.result_json)['unit']}",
                    }
                    for r in session.scalars(
                        select(a.TakeoffSheet).where(
                            a.TakeoffSheet.project_id == project_id,
                            a.TakeoffSheet.status == "CHECKED",
                        )
                    )
                ],
                "boq": [
                    {
                        "id": r.id,
                        "version": r.version,
                        "label": f"{r.item_code} · {r.description}",
                    }
                    for r in session.scalars(
                        select(m.BOQItem).where(m.BOQItem.project_id == project_id)
                    )
                ],
                "acceptances": [
                    {
                        "id": r.id,
                        "label": f"#{r.id} · {r.name} · {json.loads(r.calculated_json).get('amount')}",
                    }
                    for r in session.scalars(
                        select(c.ControlRecord).where(
                            c.ControlRecord.project_id == project_id,
                            c.ControlRecord.kind.in_(("ACCEPTANCE", "WORK_ACCEPTANCE")),
                            c.ControlRecord.status == "APPROVED",
                        )
                    )
                ],
                "advances": [
                    {"id": r.id, "label": f"Journal #{r.id} · {r.business_date}"}
                    for r in session.scalars(
                        select(c.Journal)
                        .where(c.Journal.project_id == project_id)
                        .join(c.JournalLine)
                        .where(
                            c.JournalLine.account.in_(("ADVANCE", "CUSTOMER_ADVANCE")),
                        )
                    )
                ],
                "procurement_lines": [
                    {
                        "id": line.id,
                        "version": po.version,
                        "label": f"{po.number} · {line.item_code} · {line.quantity} {line.unit} @ {line.rate}",
                    }
                    for line, po in session.execute(
                        select(m.POLine, m.PurchaseOrder)
                        .join(m.PurchaseOrder)
                        .where(
                            m.PurchaseOrder.project_id == project_id,
                            m.PurchaseOrder.approved.is_(True),
                        )
                    )
                ],
                "obligations": [
                    {
                        "id": r.id,
                        "version": r.version,
                        "label": f"#{r.id} · {r.category} · {r.source_type} #{r.source_id} · {r.due_date or 'Unscheduled'}",
                    }
                    for r in session.scalars(
                        select(c.Obligation).where(
                            c.Obligation.project_id == project_id,
                            c.Obligation.amount_minor > 0,
                        )
                    )
                ],
                "kinds": sorted(
                    KINDS
                    | {
                        "PROCUREMENT_AUTHORIZATION",
                        "PROCUREMENT_AMENDMENT",
                        "CERTIFICATE_CORRECTION",
                        "ACCEPTED_COST_CORRECTION",
                    }
                ),
            }

    return router
