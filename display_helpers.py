from __future__ import annotations

from datetime import date


def metric_value(value: object) -> str | int | float:
    if value is None:
        return "n/a"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str | int | float):
        return value
    return str(value)

