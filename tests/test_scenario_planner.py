from datetime import date

import pytest

from mortgage_engine import add_months
from sample_data import DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, DEFAULT_SETTINGS
from scenario_planner import (
    DEFAULT_COMPARISON_AMOUNT,
    best_scenario,
    generate_overpayment_scenarios,
)


def scenario_named(comparison, name):
    return next(item for item in comparison.scenarios if item.name == name)


def test_default_scenario_generation_uses_focused_set_and_default_amount():
    comparison = generate_overpayment_scenarios(
        DEFAULT_MORTGAGE,
        DEFAULT_RATE_SCHEDULE,
        DEFAULT_SETTINGS,
    )

    assert comparison.amount == DEFAULT_COMPARISON_AMOUNT == 12_000
    assert comparison.baseline.dashboard["Total extra overpayments"] == 0
    assert [scenario.name for scenario in comparison.scenarios] == [
        "Pay now",
        "Pay when the rate increases",
        "Spread it monthly to the rate increase",
    ]


def test_lump_sum_scenarios_use_next_day_dates():
    comparison = generate_overpayment_scenarios(
        DEFAULT_MORTGAGE,
        DEFAULT_RATE_SCHEDULE,
        DEFAULT_SETTINGS,
        amount=12_000,
    )

    pay_now = scenario_named(comparison, "Pay now")
    rate_change = scenario_named(comparison, "Pay when the rate increases")

    assert [payment.date for payment in pay_now.overpayments] == [date(2026, 6, 2)]
    assert [payment.amount for payment in pay_now.overpayments] == [12_000]
    assert [payment.date for payment in rate_change.overpayments] == [date(2028, 11, 2)]
    assert [payment.amount for payment in rate_change.overpayments] == [12_000]


def test_instalments_split_amount_monthly_through_rate_change_next_day():
    comparison = generate_overpayment_scenarios(
        DEFAULT_MORTGAGE,
        DEFAULT_RATE_SCHEDULE,
        DEFAULT_SETTINGS,
        amount=12_000,
    )

    instalments = scenario_named(comparison, "Spread it monthly to the rate increase")
    payments = instalments.overpayments

    assert payments[0].date == date(2026, 6, 2)
    assert payments[-1].date == date(2028, 11, 2)
    assert [payment.date for payment in payments] == [
        add_months(date(2026, 6, 2), offset) for offset in range(30)
    ]
    assert sum(payment.amount for payment in payments) == pytest.approx(12_000)
    assert {payment.amount for payment in payments} == {400}


def test_scenarios_report_savings_versus_baseline_and_choose_best_by_interest():
    comparison = generate_overpayment_scenarios(
        DEFAULT_MORTGAGE,
        DEFAULT_RATE_SCHEDULE,
        DEFAULT_SETTINGS,
        amount=12_000,
    )

    for scenario in comparison.scenarios:
        assert scenario.total_extra_paid == pytest.approx(12_000)
        assert scenario.interest_saved >= 0
        assert scenario.months_saved >= 0

    ranked = sorted(
        comparison.scenarios,
        key=lambda scenario: (scenario.interest_saved, scenario.months_saved),
        reverse=True,
    )
    assert best_scenario(comparison.scenarios) == ranked[0]
    assert comparison.best == ranked[0]
