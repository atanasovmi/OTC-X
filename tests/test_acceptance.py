"""Acceptance tests for the OTC-X platform using pytest-bdd.

Validates business requirements through Gherkin feature files, ensuring
the system meets acceptance criteria defined by stakeholders.
"""
import pytest
import polars as pl
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, timedelta
from pytest_bdd import scenarios, given, when, then, parsers

# ═══════════════════════════════════════════════════════════
#  Feature: Anomaly Detection
# ═══════════════════════════════════════════════════════════

scenarios("features/anomaly_detection.feature")


def _build_normal_days(n: int, price: float = 100.0, volume: float = 50.0) -> list[dict]:
    """Helper to build N days of uniform trading data."""
    base_date = date(2024, 1, 1)
    records = []
    for d in range(n):
        dt = base_date + timedelta(days=d)
        records.append({
            "Isin": "CH0000000001",
            "Datum": dt.isoformat(),
            "Zeit": "10:00:00",
            "Kurs": price,
            "Volumen": volume,
            "Off Book": False,
        })
    return records


def _spike_date(n: int) -> str:
    """Return a date string one day after n normal days."""
    base_date = date(2024, 1, 1)
    dt = base_date + timedelta(days=n)
    return dt.isoformat()


@given("a security with 30 days of normal volume around 50 units", target_fixture="anomaly_context")
def normal_volume_context():
    records = _build_normal_days(30, price=100.0, volume=50.0)
    return {"records": records, "result": None}


@when("a trading day has volume exceeding 1.5 times the 30-day median")
def add_volume_spike(anomaly_context):
    spike_dt = _spike_date(30)
    anomaly_context["records"].append({
        "Isin": "CH0000000001",
        "Datum": spike_dt,
        "Zeit": "10:00:00",
        "Kurs": 100.0,
        "Volumen": 500.0,  # 10x normal
        "Off Book": False,
    })
    from backend.operations.metrics import compute_daily_metrics
    df = pl.DataFrame(anomaly_context["records"]).with_columns(
        pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d")
    )
    anomaly_context["result"] = compute_daily_metrics(df)


@then("the volume_spike flag should be True")
def check_volume_spike(anomaly_context):
    result = anomaly_context["result"]
    last = result.sort("Datum").tail(1)
    assert bool(last["volume_spike"][0]) is True


@then(parsers.parse("the anomaly_score should be at least {score:d}"))
def check_min_anomaly_score(anomaly_context, score):
    result = anomaly_context["result"]
    last = result.sort("Datum").tail(1)
    assert last["anomaly_score"][0] >= score


# --- No anomaly for uniform trading ---

@given(
    "a security with 30 days of identical trades at price 100 and volume 50",
    target_fixture="uniform_context",
)
def uniform_context():
    records = _build_normal_days(30, price=100.0, volume=50.0)
    return {"records": records, "result": None}


@when("the metrics pipeline processes the data")
def process_uniform_data(uniform_context):
    from backend.operations.metrics import compute_daily_metrics
    df = pl.DataFrame(uniform_context["records"]).with_columns(
        pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d")
    )
    uniform_context["result"] = compute_daily_metrics(df)


@then("all anomaly_score values should be 0")
def check_all_zero(uniform_context):
    result = uniform_context["result"]
    assert result["anomaly_score"].max() == 0


# --- Price gap detection ---

@given("a security with 30 days of stable prices at 100", target_fixture="anomaly_context")
def price_gap_context():
    records = _build_normal_days(30, price=100.0, volume=50.0)
    return {"records": records, "result": None}


@when("a trading day has a price change exceeding 5 percent")
def add_price_gap(anomaly_context):
    spike_dt = _spike_date(30)
    # Two trades on the spike day: first at 100, last at 110 (10% gap)
    anomaly_context["records"].append({
        "Isin": "CH0000000001",
        "Datum": spike_dt,
        "Zeit": "09:00:00",
        "Kurs": 100.0,
        "Volumen": 50.0,
        "Off Book": False,
    })
    anomaly_context["records"].append({
        "Isin": "CH0000000001",
        "Datum": spike_dt,
        "Zeit": "15:00:00",
        "Kurs": 110.0,
        "Volumen": 50.0,
        "Off Book": False,
    })
    from backend.operations.metrics import compute_daily_metrics
    df = pl.DataFrame(anomaly_context["records"]).with_columns(
        pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d")
    )
    anomaly_context["result"] = compute_daily_metrics(df)


@then("the price_gap flag should be True")
def check_price_gap(anomaly_context):
    result = anomaly_context["result"]
    last = result.sort("Datum").tail(1)
    assert bool(last["price_gap"][0]) is True


# --- Combined spike yields maximum score ---

@given("a security with 30 days of normal trading", target_fixture="anomaly_context")
def combined_context():
    records = _build_normal_days(30, price=100.0, volume=50.0)
    return {"records": records, "result": None}


@when("a day has volume spike and activity spike and price gap")
def add_combined_spike(anomaly_context):
    spike_dt = _spike_date(30)
    # Multiple trades with high volume and price gap on spike day
    for t in range(10):  # 10 trades (activity spike: 10 >> 1 trade/day median)
        anomaly_context["records"].append({
            "Isin": "CH0000000001",
            "Datum": spike_dt,
            "Zeit": f"{9 + t}:00:00",
            "Kurs": 100.0 + t * 2,  # price goes from 100 to 118 (18% gap)
            "Volumen": 500.0,  # each trade has 10x normal volume
            "Off Book": False,
        })
    from backend.operations.metrics import compute_daily_metrics
    df = pl.DataFrame(anomaly_context["records"]).with_columns(
        pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d")
    )
    anomaly_context["result"] = compute_daily_metrics(df)


@then("the anomaly_score should be 7")
def check_max_score(anomaly_context):
    result = anomaly_context["result"]
    last = result.sort("Datum").tail(1)
    assert last["anomaly_score"][0] == 7


# ═══════════════════════════════════════════════════════════
#  Feature: Data Pipeline Metrics
# ═══════════════════════════════════════════════════════════

scenarios("features/data_pipeline.feature")


@given(
    "raw trade data with 3 ISINs and 5 trading days each",
    target_fixture="pipeline_context",
)
def pipeline_context():
    import random
    random.seed(99)
    records = []
    isins = ["CH0000000001", "CH0000000002", "CH0000000003"]
    for isin in isins:
        for d in range(1, 6):
            records.append({
                "Isin": isin,
                "Datum": f"2024-03-{d:02d}",
                "Zeit": "10:00:00",
                "Kurs": 100.0 + random.uniform(-5, 5),
                "Volumen": 50.0 + random.uniform(0, 50),
                "Off Book": False,
            })
    return {"records": records, "result": None}


@when("the metrics pipeline processes the trades")
def process_pipeline_trades(pipeline_context):
    from backend.operations.metrics import compute_daily_metrics
    df = pl.DataFrame(pipeline_context["records"]).with_columns(
        pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d")
    )
    pipeline_context["result"] = compute_daily_metrics(df)


@then(parsers.parse("the output should have {count:d} rows"))
def check_row_count(pipeline_context, count):
    assert len(pipeline_context["result"]) == count


@then("each row should have a positive trade count")
def check_positive_trades(pipeline_context):
    assert pipeline_context["result"]["trades_today"].min() >= 1


# --- Price bounds consistency ---

@given("raw trade data with multiple intraday prices", target_fixture="bounds_context")
def bounds_context():
    records = []
    for d in range(1, 4):
        for t, price in enumerate([95.0, 100.0, 105.0, 98.0]):
            records.append({
                "Isin": "CH0000000001",
                "Datum": f"2024-04-{d:02d}",
                "Zeit": f"{9 + t}:00:00",
                "Kurs": price + d,
                "Volumen": 20.0,
                "Off Book": False,
            })
    return {"records": records, "result": None}


@when("the metrics pipeline processes the intraday data")
def process_bounds(bounds_context):
    from backend.operations.metrics import compute_daily_metrics
    df = pl.DataFrame(bounds_context["records"]).with_columns(
        pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d")
    )
    bounds_context["result"] = compute_daily_metrics(df)


@then("price_min should be less than or equal to price_max for every row")
def check_price_min_max(bounds_context):
    df = bounds_context["result"]
    assert (df["price_min"] <= df["price_max"]).all()


@then("price_first and price_last should be within the min-max range")
def check_price_within_range(bounds_context):
    df = bounds_context["result"]
    assert (df["price_first"] >= df["price_min"]).all()
    assert (df["price_first"] <= df["price_max"]).all()
    assert (df["price_last"] >= df["price_min"]).all()
    assert (df["price_last"] <= df["price_max"]).all()


# ═══════════════════════════════════════════════════════════
#  Feature: Dashboard Data Loading
# ═══════════════════════════════════════════════════════════

scenarios("features/dashboard_loading.feature")


@given("the daily_metrics parquet file exists", target_fixture="loader_context")
def loader_context():
    path = Path(__file__).resolve().parent.parent / "backend" / "data" / "daily_metrics.parquet"
    assert path.exists(), "Precondition failed: daily_metrics.parquet not found"
    return {"df_hist": None, "latest": None}


@when("the data loader reads the file")
def load_via_loader(loader_context):
    from frontend.operations.data_loader import load_data
    df_hist, latest = load_data()
    loader_context["df_hist"] = df_hist
    loader_context["latest"] = latest


@then("it should return two DataFrames")
def check_two_dfs(loader_context):
    assert isinstance(loader_context["df_hist"], pd.DataFrame)
    assert isinstance(loader_context["latest"], pd.DataFrame)


@then("the latest DataFrame should have one row per ISIN")
def check_latest_unique(loader_context):
    assert loader_context["latest"]["Isin"].is_unique


@then("the historical DataFrame should have more rows than the latest")
def check_hist_larger(loader_context):
    assert len(loader_context["df_hist"]) > len(loader_context["latest"])


@then(parsers.parse("both DataFrames should contain column {col}"))
def check_column_present(loader_context, col):
    assert col in loader_context["df_hist"].columns, f"{col} missing from df_hist"
    assert col in loader_context["latest"].columns, f"{col} missing from latest"


# ═══════════════════════════════════════════════════════════
#  Feature: Formatting Utilities
# ═══════════════════════════════════════════════════════════

scenarios("features/formatting.feature")


@given(parsers.parse("a numeric value {value:d}"), target_fixture="fmt_context")
def numeric_value(value):
    return {"value": value, "result": None}


@given(parsers.parse("a numeric value {value:f}"), target_fixture="fmt_context")
def numeric_float_value(value):
    return {"value": value, "result": None}


@given("a NaN value", target_fixture="fmt_context")
def nan_value():
    return {"value": float("nan"), "result": None}


@given(parsers.parse("a positive percentage value {value:f}"), target_fixture="pct_context")
def positive_pct_value(value):
    return {"value": value, "result": None}


@given(parsers.parse("a negative percentage value {value:f}"), target_fixture="pct_context")
def negative_pct_value(value):
    return {"value": value, "result": None}


@when("formatted as CHF")
def format_as_chf(fmt_context):
    from frontend.operations.utils import fmt_chf
    fmt_context["result"] = fmt_chf(fmt_context["value"])


@when("formatted as percentage")
def format_as_pct(pct_context):
    from frontend.operations.utils import fmt_pct
    pct_context["result"] = fmt_pct(pct_context["value"])


@then(parsers.parse('the result should contain "{expected_part}"'))
def check_result_contains(fmt_context, expected_part):
    assert expected_part in fmt_context["result"], (
        f"Expected '{expected_part}' in '{fmt_context['result']}'"
    )


@then("the result should be the dash character")
def check_dash(fmt_context):
    assert fmt_context["result"] == "\u2014"


@then("the result should start with a plus sign")
def check_plus_sign(pct_context):
    assert pct_context["result"].startswith("+")


@then("the result should start with a minus sign")
def check_minus_sign(pct_context):
    assert pct_context["result"].startswith("-")
