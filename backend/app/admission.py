"""Short independent SQLite transactions persist limits, including denied attempts."""
import hashlib
import json
import time
from sqlalchemy import select, delete, func
from .database import transaction
from .hardening_models import AdmissionBucket, UsageReservation
from .security import DomainError, project_access, require_role
from .money import minor, utcnow


def consume(engine, keys, *, clock=time.time):
    now = int(clock())
    denied = None
    with transaction(engine, True) as session:
        session.execute(delete(AdmissionBucket).where(AdmissionBucket.updated_at < now - 3600))
        if session.scalar(select(func.count()).select_from(AdmissionBucket)) >= 10000:
            existing = {hashlib.sha256(label.encode()).hexdigest() for label,_,_ in keys}
            if any(session.get(AdmissionBucket,key) is None for key in existing):
                raise DomainError(503, "ADMISSION_CAPACITY", "Admission capacity is temporarily full.", retry_after=60)
        for label, limit, window in keys:
            key = hashlib.sha256(label.encode()).hexdigest()
            row = session.get(AdmissionBucket, key)
            events = [v for v in json.loads(row.events_json) if now - v < window] if row else []
            if len(events) >= limit:
                denied = max(1, window - (now - events[0]))
                break
        if denied is None:
            for label, limit, window in keys:
                key = hashlib.sha256(label.encode()).hexdigest()
                row = session.get(AdmissionBucket, key)
                events = [v for v in json.loads(row.events_json) if now - v < window] if row else []
                if not row:
                    row = AdmissionBucket(key=key, updated_at=now)
                    session.add(row)
                row.events_json, row.updated_at = json.dumps([*events, now]), now
    if denied is not None:
        raise DomainError(429, "RATE_LIMIT", "Usage limit reached. Try again later.", retry_after=denied)


class DurableLoginThrottle:
    def __init__(self, engine):
        self.engine = engine

    def check(self, identifier, address):
        # Check failures without spending a failure allowance on a valid login.
        now = int(time.time())
        with transaction(self.engine) as session:
            for label, limit in (("login-account:" + identifier, 10), ("login-ip:" + address, 50)):
                row = session.get(AdmissionBucket, hashlib.sha256(label.encode()).hexdigest())
                events = [v for v in json.loads(row.events_json) if now-v < 60] if row else []
                if len(events) >= limit:
                    raise DomainError(429, "LOGIN_RATE_LIMIT", "Wait before retrying sign-in.", retry_after=max(1,60-(now-events[0])))
        consume(self.engine, [("login-admission:" + address, 50, 60)])

    def failed(self, identifier, address):
        consume(self.engine, [("login-account:" + identifier, 10, 60), ("login-ip:" + address, 50, 60)])


def paid_ready(settings, provider):
    credentials = bool(settings.serpapi_key) if provider == "serpapi" else bool(settings.dataforseo_login and settings.dataforseo_password)
    return bool(settings.paid_providers_enabled and credentials and settings.paid_user_daily_calls > 0
                and settings.paid_project_daily_calls > 0 and settings.paid_provider_daily_calls > 0
                and minor(settings.paid_operation_ceiling) > 0 and minor(settings.paid_daily_budget) > 0)


def reserve_usage(engine, settings, provider, operation_key, user_id, project_id):
    day = utcnow()[:10]
    with transaction(engine, True) as session:
        from .models import User
        actor = session.get(User, user_id)
        project_access(session, actor, project_id)
        if provider != "ollama":
            require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
            if not paid_ready(settings, provider):
                raise DomainError(403, "PAID_PROVIDER_DISABLED", "Paid access needs explicit enablement, credentials and bounded budgets.")
        existing = session.scalar(select(UsageReservation).where(UsageReservation.provider == provider, UsageReservation.operation_key == operation_key))
        if existing:
            if existing.user_id != user_id or existing.project_id != project_id:
                raise DomainError(409, "USAGE_CONFLICT", "Provider operation belongs to a different request.")
            if existing.state == "UNKNOWN":
                raise DomainError(409, "UNKNOWN_SUBMISSION", "Reconcile the reserved provider operation before retrying.")
            return existing.id
        rows = list(session.scalars(select(UsageReservation).where(UsageReservation.provider == provider, UsageReservation.day == day)))
        user_limit = settings.llm_user_daily_calls if provider == "ollama" else settings.paid_user_daily_calls
        project_limit = settings.llm_project_daily_calls if provider == "ollama" else settings.paid_project_daily_calls
        charge = 0 if provider == "ollama" else minor(settings.paid_operation_ceiling)
        denied = (sum(r.user_id == user_id for r in rows) >= user_limit or sum(r.project_id == project_id for r in rows) >= project_limit)
        if provider != "ollama":
            denied |= len(rows) >= settings.paid_provider_daily_calls or sum(r.reserved_minor for r in rows) + charge > minor(settings.paid_daily_budget)
        if denied:
            raise DomainError(429, "PROVIDER_BUDGET", "Daily provider allowance is exhausted.", retry_after=86400)
        row = UsageReservation(provider=provider, operation_key=operation_key, user_id=user_id, project_id=project_id, day=day, reserved_minor=charge)
        session.add(row)
        session.flush()
        return row.id


def mark_usage(engine, identity, state):
    with transaction(engine, True) as session:
        session.get(UsageReservation, identity).state = state
