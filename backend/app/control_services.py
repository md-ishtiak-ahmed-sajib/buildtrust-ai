"""Dispatch controls by business boundary; settlement remains in payments.py."""

from . import accounting, governance, performance, commercial, procurement, corrections


def service(kind):
    if kind in corrections.KINDS:
        return corrections
    if kind in procurement.KINDS:
        return procurement
    if kind in commercial.KINDS:
        return commercial
    return (
        governance
        if kind in governance.KINDS
        else performance
        if kind in performance.KINDS
        else accounting
    )


def build(session, project, values):
    return service(values.kind).build(session, project, values)


def apply(session, actor, project, record, values, result):
    return service(values.kind).apply(session, actor, project, record, values, result)
