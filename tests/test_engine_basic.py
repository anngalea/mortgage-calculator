from sample_data import DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, DEFAULT_SETTINGS
from mortgage_engine import project_mortgage


def test_no_overpayments_projection_starts_with_scheduled_payment():
    result = project_mortgage(DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, [], DEFAULT_SETTINGS)

    assert not result.ledger.empty
    first = result.ledger.iloc[0]
    assert str(first["Date"]) == "2026-06-01"
    assert first["Event Type"] == "Scheduled payment"
    assert first["Closing Balance"] < first["Opening Balance"]
    assert result.dashboard["Total interest from projection start"] > 0
    assert (result.ledger["Closing Balance"] >= 0).all()


def test_final_payment_is_capped_at_zero():
    result = project_mortgage(DEFAULT_MORTGAGE, DEFAULT_RATE_SCHEDULE, [], DEFAULT_SETTINGS)

    assert result.ledger.iloc[-1]["Closing Balance"] == 0
    assert (result.ledger["Closing Balance"] >= 0).all()

