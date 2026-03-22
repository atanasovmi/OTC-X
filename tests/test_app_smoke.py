from streamlit.testing.v1 import AppTest


def test_app_renders_expected_tabs_without_errors():
    at = AppTest.from_file("app.py", default_timeout=60)
    at.run()

    assert not at.exception
    tab_labels = [t.label.strip() for t in at.tabs]
    assert tab_labels == ["Overview", "Market Data", "Analytics", "Anomaly Monitor"]

