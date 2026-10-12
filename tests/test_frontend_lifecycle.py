"""Isolated lifecycle, label and refresh-health regression coverage."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from frontend.operations import data_loader as loader
from frontend.operations.charts import chart_anomaly_severity_treemap, chart_sector_treemap


def metrics(rows):
    """Produce the established metric shape without touching real market data."""
    defaults = {
        "Name": None, "Sektor": None, "Datum": pd.Timestamp("2026-10-09"),
        "trades_today": 1, "volume_today_units": 10.0, "volume_today_chf": 100.0,
        "price_min": 10.0, "price_max": 10.0, "price_first": 10.0, "price_last": 10.0,
        "price_change_pct": 0.0, "log_returns": 0.0, "volatility_daily": 0.0,
        "amihud_daily": 0.0, "spread_log_hl": 0.0, "trade_duration_min": 0.0,
        "off_book_pct": 0.0, "trades_30d_median": 1.0, "volume_30d_median": 100.0,
        "volatility_30d_median": 0.0, "amihud_30d_median": 0.0,
        "volume_spike": False, "activity_spike": False, "price_gap": False, "anomaly_score": 0,
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "DATA_DIR", tmp_path)
    panel = metrics([
        {"Isin": "CH0000000001", "Name": "Current AG"},
        {"Isin": "CH0000000002", "Name": "Removed AG", "anomaly_score": 7},
    ])
    panel.to_parquet(tmp_path / "daily_metrics.parquet", index=False)
    registry = pd.DataFrame([
        {"ISIN": "CH0000000001", "VALOR": "1", "NAME": "Current AG", "SEKTOR": "Banking", "is_active": True},
        {"ISIN": "CH0000000002", "VALOR": "2", "NAME": "Removed AG", "SEKTOR": "Banking", "is_active": False},
        {"ISIN": "CH0000000003", "VALOR": "3", "NAME": "New AG", "SEKTOR": "Energy", "is_active": True},
    ])
    registry.to_csv(tmp_path / "security_registry.csv", index=False)
    return tmp_path


def test_labels_are_normalized_on_copies_without_numeric_changes():
    source = metrics([
        {"Isin": "A", "Name": None, "Sektor": float("nan")},
        {"Isin": "B", "Name": " ", "Sektor": pd.NA},
        {"Isin": "C", "Name": 42.0, "Sektor": " Energy "},
    ])
    result = loader.normalize_display_labels(source)
    assert result["Name"].tolist() == ["A", "B", "C"]
    assert result["Sektor"].tolist() == ["Unknown sector", "Unknown sector", "Energy"]
    pd.testing.assert_frame_equal(result.select_dtypes("number"), source.select_dtypes("number"))
    assert source.loc[0, "Name"] is None
    assert source.loc[2, "Name"] == 42.0


def test_null_labels_render_and_sector_volume_is_preserved():
    source = metrics([
        {"Isin": "A", "anomaly_score": 3},
        {"Isin": "B", "Name": "Known", "Sektor": "Energy", "anomaly_score": 3},
    ])
    assert chart_anomaly_severity_treemap(source).data
    sector = chart_sector_treemap(source).data[0]
    assert "Unknown sector" in sector.labels
    assert sum(sector.values) == source["volume_today_chf"].sum()


def test_categorical_labels_allow_new_fallback_values():
    source = pd.DataFrame({"Isin": ["A", "B"],
                           "Name": pd.Categorical([None, "Known"]),
                           "Sektor": pd.Categorical([None, "Energy"])})
    result = loader.normalize_display_labels(source)
    assert result["Name"].tolist() == ["A", "Known"]
    assert result["Sektor"].tolist() == ["Unknown sector", "Energy"]


def test_duplicate_and_truncated_names_keep_distinct_isin_leaves():
    source = metrics([
        {"Isin": "A", "Name": "Duplicated company name longer than twenty eight characters 1", "anomaly_score": 3},
        {"Isin": "B", "Name": "Duplicated company name longer than twenty eight characters 2", "anomaly_score": 3},
    ])
    tree = chart_anomaly_severity_treemap(source).data[0]
    leaves = {node: (label, value) for node, label, value in zip(tree.ids, tree.labels, tree.values) if "/" in node}
    assert set(leaves) == {"Critical/A", "Critical/B"}
    assert leaves["Critical/A"][0] == leaves["Critical/B"][0]
    assert sum(value for _, value in leaves.values()) == 6


def test_lifecycle_keeps_history_and_new_untraded_choices(snapshot):
    history, latest = loader.load_data()
    universe = loader.security_universe(loader.load_security_registry(), latest)
    assert set(history["Isin"]) == {"CH0000000001", "CH0000000002"}
    assert set(latest["Isin"]) == set(history["Isin"])
    current = loader.filter_active(latest, universe)
    assert current["Isin"].tolist() == ["CH0000000001"]
    choices = loader.security_choices(universe)
    assert len(choices) == 3
    removed = choices.set_index("Isin").loc["CH0000000002"]
    new = choices.set_index("Isin").loc["CH0000000003"]
    assert removed["Listing status"] == "Inactive"
    assert new["Trading data"] == "No trading data"
    risk, assessed = loader.risk_assessment(history, universe)
    assert risk.empty  # The removed security's extreme flag is historical.
    assert assessed == {"CH0000000001"}
    assert "CH0000000003" not in assessed  # New listings cannot be Clean.


def test_risk_assessment_excludes_active_but_unobserved_history():
    history = metrics([
        {"Isin": "A", "Datum": date} for date in pd.date_range("2026-09-01", periods=31)
    ] + [{"Isin": "OLD", "Datum": pd.Timestamp("2026-01-01")}])
    universe = pd.DataFrame({"Isin": ["A", "OLD", "NEW"], "is_active": [True, True, True]})
    _, assessed = loader.risk_assessment(history, universe)
    assert assessed == {"A"}


def test_reappearing_listing_reuses_retained_history(snapshot):
    registry = pd.read_csv(snapshot / "security_registry.csv")
    registry.loc[registry["ISIN"] == "CH0000000002", "is_active"] = True
    registry.to_csv(snapshot / "security_registry.csv", index=False)
    history, latest = loader.load_data()
    universe = loader.security_universe(loader.load_security_registry(), latest)
    assert len(history) == 2
    assert len(loader.filter_active(latest, universe)) == 2
    risk, assessed = loader.risk_assessment(history, universe)
    assert risk["Isin"].tolist() == ["CH0000000002"]
    assert assessed == {"CH0000000001", "CH0000000002"}


def test_legacy_registry_retains_removed_identifiers(snapshot):
    (snapshot / "security_registry.csv").unlink()
    pd.DataFrame([
        {"ISIN": "CH0000000001", "VALOR": "1", "NAME": "Current AG", "SEKTOR": "Banking"},
        {"ISIN": "CH0000000003", "VALOR": "3", "NAME": "New AG", "SEKTOR": "Energy"},
    ]).to_csv(snapshot / "securities.csv", index=False)
    registry = loader.load_security_registry().set_index("ISIN")
    assert len(registry) == 3
    assert not registry.loc["CH0000000002", "is_active"]
    assert registry.loc["CH0000000002", "NAME"] == "Removed AG"


def test_search_is_literal_and_includes_untraded_listings(snapshot):
    _, latest = loader.load_data()
    universe = loader.security_universe(loader.load_security_registry(), latest)
    assert loader.security_choices(universe, "New", "Energy")["Isin"].tolist() == ["CH0000000003"]
    assert loader.security_choices(universe, "[").empty


@pytest.mark.parametrize("status", [{}, {"refreshed_at_utc": "bad"}, {"refreshed_at_utc": "2026-10-11T12:00:00"}, {"refreshed_at_utc": "2026-10-13T12:00:00Z"}])
def test_unknown_refresh_is_explicit(status):
    assert loader.refresh_freshness(status, datetime(2026, 10, 12, 12, tzinfo=timezone.utc))["state"] == "unknown"


def test_weekend_market_date_does_not_make_recent_refresh_stale():
    status = {"refreshed_at_utc": "2026-10-11T10:00:00Z", "latest_trade_date": "2026-10-09"}
    assert loader.refresh_freshness(status, datetime(2026, 10, 11, 12, tzinfo=timezone.utc))["state"] == "current"
    assert loader.refresh_freshness(status, datetime(2026, 10, 12, 22, tzinfo=timezone.utc))["state"] == "current"
    assert loader.refresh_freshness(status, datetime(2026, 10, 12, 22, 1, tzinfo=timezone.utc))["state"] == "overdue"


def test_metrics_registry_and_refresh_caches_invalidate_on_file_change(snapshot):
    first_hist, first_latest = loader.load_data()
    replacement = metrics([{"Isin": "CH0000000004", "price_last": 15.0}])
    replacement.to_parquet(snapshot / "daily_metrics.parquet", index=False)
    second_hist, second_latest = loader.load_data()
    assert second_hist["Isin"].tolist() == ["CH0000000004"]
    assert second_latest["price_last"].tolist() == [15.0]
    assert len(first_latest) == 2

    first_registry = loader.load_security_registry()
    changed = first_registry.copy()
    changed.loc[changed["ISIN"] == "CH0000000002", "is_active"] = True
    changed.to_csv(snapshot / "security_registry.csv", index=False)
    assert loader.load_security_registry()["is_active"].all()
    assert not first_registry["is_active"].all()

    status_path = snapshot / "refresh_status.json"
    assert loader.load_refresh_status() == {}
    status_path.write_text(json.dumps({"refreshed_at_utc": "2026-10-11T10:00:00Z"}), encoding="utf-8")
    assert loader.load_refresh_status()["refreshed_at_utc"] == "2026-10-11T10:00:00Z"
    status_path.write_text(json.dumps({"refreshed_at_utc": "2026-10-12T10:00:00Z"}), encoding="utf-8")
    assert loader.load_refresh_status()["refreshed_at_utc"] == "2026-10-12T10:00:00Z"


def test_dashboard_all_tabs_and_new_listing_no_data_state(snapshot):
    from streamlit.testing.v1 import AppTest

    app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=20).run()
    assert not app.exception
    selector = next(control for control in app.selectbox if control.label == "Select security")
    assert len(selector.options) == 3
    selector.set_value("CH0000000003").run()
    assert not app.exception
    assert any("No trading data. This listing" in item.value for item in app.info)
    assert any("Risk coverage: 1 of 2 active listings assessed" in item.value for item in app.caption)


def test_dashboard_safe_when_every_historical_listing_is_inactive(snapshot):
    from streamlit.testing.v1 import AppTest

    registry = pd.read_csv(snapshot / "security_registry.csv")
    registry["is_active"] = False
    registry.to_csv(snapshot / "security_registry.csv", index=False)
    app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=20).run()
    assert not app.exception
    assert any("0 active listings" in item.value for item in app.caption)
