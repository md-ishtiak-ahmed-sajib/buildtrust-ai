import json

from sqlalchemy import select

from .money import canonical, digest
from .operations_models import EvidenceRevision


def append(session, actor, record, evidence):
    session.add(
        EvidenceRevision(
            project_id=record.project_id,
            entity_type="quotation",
            entity_id=record.id,
            version=record.version,
            evidence_json=canonical(evidence),
            snapshot_hash=digest(evidence),
            actor_id=actor.id,
        )
    )
    session.flush()


def history(session, record):
    return [
        {
            "id": r.id,
            "version": r.version,
            "evidence": json.loads(r.evidence_json),
            "snapshot_hash": r.snapshot_hash,
            "actor_id": r.actor_id,
            "created_at": r.created_at,
        }
        for r in session.scalars(
            select(EvidenceRevision)
            .where(
                EvidenceRevision.entity_type == "quotation",
                EvidenceRevision.entity_id == record.id,
            )
            .order_by(EvidenceRevision.id)
        )
    ]
