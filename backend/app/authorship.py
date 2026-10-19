"""Retained-content authorship cannot be erased by a later editor."""

from sqlalchemy import select

from .review_models import Contributor


def contributors(session, kind, identity):
    return sorted(
        session.scalars(
            select(Contributor.actor_id).where(
                Contributor.entity_type == kind, Contributor.entity_id == identity
            )
        )
    )


def contribute(session, kind, record, actor, evidence="edit"):
    session.flush()
    # Include the legacy preparer as well, even on records seeded by older code.
    for identity in {record.prepared_by, actor.id}:
        if identity not in contributors(session, kind, record.id):
            session.add(
                Contributor(
                    entity_type=kind,
                    entity_id=record.id,
                    actor_id=identity,
                    evidence=evidence,
                )
            )
            session.flush()


def inherit(session, parent, child, actor):
    contribute(session, "estimate", child, actor, "revision")
    for identity in contributors(session, "estimate", parent.id):
        if identity not in contributors(session, "estimate", child.id):
            session.add(
                Contributor(
                    entity_type="estimate",
                    entity_id=child.id,
                    actor_id=identity,
                    evidence=f"retained from revision:{parent.id}",
                )
            )
            session.flush()
