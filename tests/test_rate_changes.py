from datetime import date

import pytest

from models import ProjectionSettings
from mortgage_engine import project_mortgage
from sample_data import DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE


def test_rate_change_applies_on_effective_date_and_recalculates_payment():
    settings = ProjectionSettings(
        interest_mode="daily",
        payment_mode="use_current_until_reset",
        recalculate_on_rate_change=True,
    )
    result = project_mortgage(DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, [], settings)

    october = result.ledger[result.ledger["Date"].astype(str) == "2028-10-01"].iloc[0]
    november = result.ledger[result.ledger["Date"].astype(str) == "2028-11-01"].iloc[0]
    december = result.ledger[result.ledger["Date"].astype(str) == "2028-12-01"].iloc[0]

    assert october["Rate %"] == pytest.approx(1.0)
    assert november["Rate %"] == pytest.approx(1.0)
    assert "Scheduled payment recalculated" in november["Notes"]
    assert december["Rate %"] == pytest.approx(2.8)
    assert december["Scheduled Payment"] != 938
