from .security import DomainError, project_access, require_role


def load(session, actor, cls, identity, write=False):
    record = session.get(cls, identity)
    if not record:
        raise DomainError(404, "NOT_FOUND", "Resource is unavailable.")
    project_access(session, actor, record.project_id, write=write)
    return record


def author(actor):
    require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
