from datetime import date

from display_helpers import metric_value, recurring_overpayment_date_bounds
from sample_data import DEFAULT_MORTGAGE


def test_metric_value_formats_dates_for_streamlit_metrics():
    assert metric_value(date(2057, 12, 1)) == "2057-12-01"


def test_metric_value_formats_missing_values():
    assert metric_value(None) == "n/a"


def test_recurring_overpayment_date_bounds_match_contractual_term():
    assert recurring_overpayment_date_bounds(DEFAULT_MORTGAGE) == (
        date(2026, 6, 1),
        date(2057, 10, 31),
    )
