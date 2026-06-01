from pathlib import Path


def test_auto_scenarios_tab_is_not_displayed():
    app_source = Path("app.py").read_text()

    assert '"Auto Scenarios"' not in app_source
    assert "with auto_tab:" not in app_source
