from __future__ import annotations

from datetime import date

from models import MortgageInput, ProjectionSettings, RatePeriod


DEFAULT_MORTGAGE = MortgageInput(
    original_amount=315_800.0,
    start_date=date(2024, 11, 1),
    original_term_years=33,
    current_balance=285_534.0,
    current_monthly_payment=938.0,
    next_payment_date=date(2026, 6, 1),
    payment_day=1,
    current_rate=0.01,
    inflation_rate=0.0,
)


DEFAULT_RATE_SCHEDULE = [
    RatePeriod(date(2024, 11, 1), 0.01, "Initial rate"),
    RatePeriod(date(2028, 11, 1), 0.028, "Post-initial-rate assumption"),
]


DEFAULT_SETTINGS = ProjectionSettings(
    interest_mode="daily",
    payment_mode="use_current_until_reset",
    recalculate_on_rate_change=True,
    monthly_overpayment=0.0,
    monthly_overpayment_start=date(2026, 6, 1),
    monthly_overpayment_end=None,
)
