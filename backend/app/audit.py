import json
from sqlalchemy import select
from .models import AuditEvent, User
from .money import canonical, digest, utcnow

GENESIS = "0" * 64


def payload(event):
    return {
        "id": event.id,
        "project_id": event.project_id,
        "actor_id": event.actor_id,
        "actor_name": event.actor_name,
        "role": event.role,
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "details": json.loads(event.details_json),
        "previous_hash": event.previous_hash,
        "created_at": event.created_at,
    }


def append(
    session,
    actor: User | None,
    event_type,
    entity_type,
    entity_id,
    details=None,
    project_id=None,
):
    previous = session.scalar(
        select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)
    )
    event = AuditEvent(
        project_id=project_id,
        actor_id=actor.id if actor else None,
        actor_name=actor.name if actor else "System",
        role=actor.role if actor else "SYSTEM",
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details_json=canonical(details or {}),
        previous_hash=previous.event_hash if previous else GENESIS,
        event_hash="",
        created_at=utcnow(),
    )
    session.add(event)
    session.flush()
    event.event_hash = digest(payload(event))
    session.flush()
    return event


def verify(session):
    previous = GENESIS
    count = 0
    for event in session.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        if event.previous_hash != previous or event.event_hash != digest(
            payload(event)
        ):
            return {
                "valid": False,
                "checked_events": count,
                "failed_event_id": event.id,
                "head_hash": previous,
            }
        previous = event.event_hash
        count += 1
    return {
        "valid": True,
        "checked_events": count,
        "failed_event_id": None,
        "head_hash": previous,
        "limitation": "Local hash chain; an unrestricted database administrator can rewrite the complete chain.",
    }
