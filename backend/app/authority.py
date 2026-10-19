"""BDT-denominated authority needs a dated source for a non-BDT project."""

from sqlalchemy import select

from .advanced_models import ExchangeRate
from .money import decimal, minor
from .security import DomainError


def conversion(session, project_id, currency, amount_minor):
    if currency == "BDT":
        return {
            "factor": "1",
            "amount_minor": amount_minor,
            "source": "Project currency is BDT",
        }
    from .finance import business_date

    rate = (
        session.scalar(
            select(ExchangeRate)
            .where(
                ExchangeRate.project_id == project_id,
                ExchangeRate.base == currency,
                ExchangeRate.quote == "BDT",
                ExchangeRate.observed_date <= str(business_date()),
            )
            .order_by(ExchangeRate.observed_date.desc(), ExchangeRate.id.desc())
        )
        if session
        else None
    )
    if not rate or decimal(rate.factor) <= 0:
        raise DomainError(
            409,
            "AUTHORITY_FX_REQUIRED",
            "A dated, sourced BDT conversion is required for this non-BDT authority check.",
            project_id,
        )
    return {
        "rate_id": rate.id,
        "factor": rate.factor,
        "date": rate.observed_date,
        "source": rate.source,
        "amount_minor": minor(decimal(str(amount_minor)) / 100 * decimal(rate.factor)),
    }
