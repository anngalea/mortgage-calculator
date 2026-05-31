from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

import pandas as pd


InterestMode = Literal["daily", "monthly"]
PaymentMode = Literal["use_current_until_reset", "recalculate_immediately"]


@dataclass(frozen=True)
class MortgageInput:
    original_amount: float
    start_date: date
    original_term_years: int
    current_balance: float
    current_monthly_payment: float
    next_payment_date: date
    payment_day: int = 1
    current_rate: float = 0.01
    inflation_rate: float = 0.0
    currency: str = "EUR"


@dataclass(frozen=True)
class RatePeriod:
    effective_date: date
    annual_rate: float
    notes: str = ""


@dataclass(frozen=True)
class Overpayment:
    date: date
    amount: float
    description: str = ""


@dataclass(frozen=True)
class ProjectionSettings:
    interest_mode: InterestMode = "daily"
    payment_mode: PaymentMode = "use_current_until_reset"
    recalculate_on_rate_change: bool = True
    monthly_overpayment: float = 0.0
    monthly_overpayment_start: date | None = None
    monthly_overpayment_end: date | None = None
    include_historical_events: bool = False
    advanced_payment_day: bool = False
    max_projection_years: int = 60


@dataclass(frozen=True)
class LedgerEntry:
    date: date
    event_type: str
    opening_balance: float
    rate: float
    days_since_prior_event: int
    interest_accrued: float
    scheduled_payment: float
    scheduled_principal: float
    scheduled_interest: float
    extra_principal: float
    closing_balance: float
    notes: str = ""


@dataclass
class ProjectionResult:
    ledger: pd.DataFrame
    monthly_summary: pd.DataFrame
    dashboard: dict[str, float | int | str | date | None]
    warnings: list[str] = field(default_factory=list)

