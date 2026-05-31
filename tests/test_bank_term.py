from datetime import date

from mortgage_engine import (
    contractual_maturity_date,
    contractual_last_payment_date,
    original_total_payments,
    project_mortgage,
    remaining_scheduled_payments,
)
from sample_data import DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, DEFAULT_SETTINGS


def test_default_current_balance_matches_bank_balance():
    assert DEFAULT_MORTGAGE.current_balance == 285_534.00


def test_bank_term_is_396_monthly_periods_ending_31_october_2057():
    assert original_total_payments(DEFAULT_MORTGAGE) == 396
    assert contractual_maturity_date(DEFAULT_MORTGAGE) == date(2057, 10, 31)


def test_remaining_payments_from_june_2026_match_bank_term():
    assert remaining_scheduled_payments(DEFAULT_MORTGAGE, date(2026, 6, 1)) == 377


def test_default_projection_ends_on_final_contractual_payment_month():
    result = project_mortgage(DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, [], DEFAULT_SETTINGS)

    assert result.ledger.iloc[-1]["Date"] == contractual_last_payment_date(DEFAULT_MORTGAGE)
    assert result.monthly_summary.iloc[-1]["Month"] == "2057-10"
    assert result.ledger.iloc[-1]["Closing Balance"] == 0


def test_dashboard_separates_payment_counts_from_payment_amounts():
    result = project_mortgage(DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, [], DEFAULT_SETTINGS)

    assert result.dashboard["Original total monthly payments"] == 396
    assert result.dashboard["Remaining scheduled payments"] == 377
    assert result.dashboard["Total scheduled payment amount remaining"] > 0
