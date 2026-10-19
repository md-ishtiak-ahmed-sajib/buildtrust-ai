from .source_schemas import (
    MeasurementProfileView,
    MeasurementView,
    SavedMeasurementView,
    RecordVersionView,
)
from .calculation_schemas import TakeoffResult
import json
from fastapi import APIRouter, Request
from sqlalchemy import select
from . import (
    advanced_models as a,
    models as m,
    audit,
    estimating,
)
from .advanced_schemas import (
    VersionAction,
    TakeoffInput,
)
from .money import canonical
from .security import DomainError, project_access, require_role
from .governance import calculate_profile


from .upgrade_access import load, author


def create_router(context):
    router = APIRouter(prefix="/api/v1", tags=["Quantity measurement"])

    @router.get(
        "/measurement/profiles",
        response_model=list[MeasurementProfileView],
        response_model_exclude_unset=True,
    )
    def profiles(request: Request, project_id: int | None = None):
        with context(request) as (session, actor):
            if project_id:
                project_access(session, actor, project_id)
            return [
                {
                    "id": p.id,
                    "code": p.code,
                    "name": p.name,
                    "edition": p.edition,
                    "source_url": p.source_url,
                    "verification_status": p.verification_status,
                    "rules": json.loads(p.rules_json),
                }
                for p in session.scalars(select(a.MeasurementProfile))
                if not json.loads(p.rules_json).get("project_id")
                or (
                    (
                        not project_id
                        or json.loads(p.rules_json)["project_id"] == project_id
                    )
                    and session.get(
                        m.Membership, (actor.id, json.loads(p.rules_json)["project_id"])
                    )
                )
            ]

    @router.post(
        "/takeoff/calculate",
        response_model=TakeoffResult,
        response_model_exclude_unset=True,
    )
    def takeoff_calculate(data: TakeoffInput, request: Request):
        with context(request) as (session, actor):
            project_access(session, actor, data.project_id)
            profile = session.get(a.MeasurementProfile, data.profile_id)
            if not profile or profile.code == "ICMS3":
                raise ValueError("Unknown measurement profile")
            return calculate_profile(data, profile)

    @router.post(
        "/takeoff/sheets",
        status_code=201,
        response_model=SavedMeasurementView,
        response_model_exclude_unset=True,
    )
    def takeoff_save(data: TakeoffInput, request: Request):
        with context(request, True) as (session, actor):
            author(actor)
            project_access(session, actor, data.project_id, write=True)
            profile = session.get(a.MeasurementProfile, data.profile_id)
            if not profile or profile.code == "ICMS3":
                raise ValueError(
                    "Choose a measurement profile; ICMS is a reporting classification"
                )
            result = calculate_profile(data, profile)
            record = a.TakeoffSheet(
                project_id=data.project_id,
                profile_id=data.profile_id,
                fields_json=canonical(data.model_dump(mode="json")),
                result_json=canonical(result),
                prepared_by=actor.id,
            )
            session.add(record)
            session.flush()
            audit.append(
                session,
                actor,
                "TAKEOFF_SAVED",
                "takeoff",
                record.id,
                result,
                record.project_id,
            )
            return {
                "id": record.id,
                "version": record.version,
                "status": record.status,
                "result": result,
            }

    @router.get(
        "/takeoff/sheets",
        response_model=list[MeasurementView],
        response_model_exclude_unset=True,
    )
    def takeoff_list(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return [
                {
                    "id": r.id,
                    "version": r.version,
                    "status": r.status,
                    "prepared_by": r.prepared_by,
                    "checked_by": r.checked_by,
                    "fields": json.loads(r.fields_json),
                    "result": json.loads(r.result_json),
                    "created_at": r.created_at,
                }
                for r in session.scalars(
                    select(a.TakeoffSheet)
                    .where(a.TakeoffSheet.project_id == project_id)
                    .order_by(a.TakeoffSheet.id.desc())
                )
            ]

    @router.post(
        "/takeoff/sheets/{identity}/check",
        response_model=RecordVersionView,
        response_model_exclude_unset=True,
    )
    def takeoff_check(identity: int, data: VersionAction, request: Request):
        with context(request, True) as (session, actor):
            require_role(actor, "FINANCE_MANAGER", "ADMIN")
            record = load(session, actor, a.TakeoffSheet, identity, True)
            estimating.version_check(record, data.expected_version)
            if record.prepared_by == actor.id:
                raise DomainError(
                    403, "SELF_CHECK", "An independent checker is required."
                )
            if record.status != "DRAFT":
                raise DomainError(
                    409, "VERSION_LOCKED", "Measurement is already checked."
                )
            record.checked_by, record.status = actor.id, "CHECKED"
            record.version += 1
            audit.append(
                session,
                actor,
                "TAKEOFF_CHECKED",
                "takeoff",
                identity,
                {"reason": data.reason, "geometry_only": True},
                record.project_id,
            )
            return {"id": identity, "version": record.version, "status": record.status}

    return router
