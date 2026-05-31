from datetime import date

from models import Overpayment
from mortgage_engine import project_mortgage
from sample_data import DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, DEFAULT_SETTINGS


def test_overpayment_on_payment_date_applies_after_scheduled_payment():
    baseline = project_mortgage(DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, [], DEFAULT_SETTINGS)
    scenario = project_mortgage(
        DEFAULT_MORTGAGE,
        DEFAULT_RATE_SCHEDULE,
        [Overpayment(date(2026, 6, 1), 5_000, "Same-day lump sum")],
        DEFAULT_SETTINGS,
    )

    baseline_first = baseline.ledger.iloc[0]
    scenario_first = scenario.ledger.iloc[0]

    assert scenario_first["Scheduled Payment"] == baseline_first["Scheduled Payment"]
    assert scenario_first["Scheduled Interest"] == baseline_first["Scheduled Interest"]
    assert scenario_first["Extra Principal"] == 5_000
    assert scenario_first["Closing Balance"] == baseline_first["Closing Balance"] - 5_000


def test_overpayment_on_next_day_reduces_following_interest():
    baseline = project_mortgage(DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, [], DEFAULT_SETTINGS)
    scenario = project_mortgage(
        DEFAULT_MORTGAGE,
        DEFAULT_RATE_SCHEDULE,
        [Overpayment(date(2026, 6, 2), 5_000, "Next-day lump sum")],
        DEFAULT_SETTINGS,
    )

    assert list(scenario.ledger["Date"].head(2).astype(str)) == ["2026-06-01", "2026-06-02"]
    assert scenario.ledger.iloc[1]["Event Type"] == "Overpayment"
    assert scenario.ledger.iloc[1]["Extra Principal"] == 5_000

    baseline_july = baseline.ledger[baseline.ledger["Date"].astype(str) == "2026-07-01"].iloc[0]
    scenario_july = scenario.ledger[scenario.ledger["Date"].astype(str) == "2026-07-01"].iloc[0]
    assert scenario_july["Interest Accrued"] < baseline_july["Interest Accrued"]


def test_first_and_second_june_overpayments_are_not_identical_in_daily_mode():
    june_first = project_mortgage(
        DEFAULT_MORTGAGE,
        DEFAULT_RATE_SCHEDULE,
        [Overpayment(date(2026, 6, 1), 5_000, "June 1")],
        DEFAULT_SETTINGS,
    )
    june_second = project_mortgage(
        DEFAULT_MORTGAGE,
        DEFAULT_RATE_SCHEDULE,
        [Overpayment(date(2026, 6, 2), 5_000, "June 2")],
        DEFAULT_SETTINGS,
    )

    assert list(june_first.ledger["Date"].head(2).astype(str)) != list(
        june_second.ledger["Date"].head(2).astype(str)
    )
    first_july = june_first.ledger[june_first.ledger["Date"].astype(str) == "2026-07-01"].iloc[0]
    second_july = june_second.ledger[june_second.ledger["Date"].astype(str) == "2026-07-01"].iloc[0]
    assert first_july["Interest Accrued"] != second_july["Interest Accrued"]

