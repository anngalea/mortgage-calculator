from datetime import date

from display_helpers import metric_value


def test_metric_value_formats_dates_for_streamlit_metrics():
    assert metric_value(date(2057, 12, 1)) == "2057-12-01"


def test_metric_value_formats_missing_values():
    assert metric_value(None) == "n/a"
