from __future__ import annotations

from datetime import date

from models import MortgageInput
from mortgage_engine import contractual_maturity_date


def metric_value(value: object) -> str | int | float:
    if value is None:
        return "n/a"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str | int | float):
        return value
    return str(value)


def recurring_overpayment_date_bounds(mortgage: MortgageInput) -> tuple[date, date]:
    return mortgage.next_payment_date, contractual_maturity_date(mortgage)
