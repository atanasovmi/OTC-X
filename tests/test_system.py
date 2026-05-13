"""System tests for the OTC-X platform.

End-to-end tests that exercise the complete system — from raw trade data
through the metrics engine to chart output — verifying all layers work
together as a cohesive whole.
"""
import pytest
import polars as pl
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ───────────────────────────────────────────────────────────
#  Fixtures
# ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def realistic_trades() -> pl.DataFrame:
    """Build a realistic multi-security, multi-day trade dataset.

    Simulates 3 ISINs across 5 trading days with varying volumes,
    prices, and off-book flags to exercise every pipeline branch.
    """
    import random
    random.seed(42)

    records = []
    isins = ["CH0000000001", "CH0000000002", "CH0000000003"]
    base_prices = [100.0, 50.0, 200.0]

    for day in range(1, 6):  # 5 trading days
        date_str = f"2024-03-{day:02d}"
        for isin, base in zip(isins, base_prices):
            n_trades = random.randint(1, 6)
            for t in range(n_trades):
                hour = 9 + t
                price = base + random.uniform(-5, 5) + day * 0.5
                vol = random.uniform(5, 100)
                records.append({
                    "Isin": isin,
                    "Datum": date_str,
                    "Zeit": f"{hour:02d}:00:00",
                    "Kurs": round(price, 2),
                    "Volumen": round(vol, 2),
                    "Off Book": random.random() < 0.1,
                })

    df = pl.DataFrame(records)
    return df.with_columns(pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d"))


@pytest.fixture(scope="module")
def end_to_end_metrics(realistic_trades) -> pl.DataFrame:
    """Run the full metrics pipeline on realistic trades."""
    from backend.operations.metrics import compute_daily_metrics
    return compute_daily_metrics(realistic_trades)


@pytest.fixture(scope="module")
def real_loaded_data():
    """Load actual production parquet data via frontend loader."""
    from frontend.operations.data_loader import load_data
    return load_data()


# ───────────────────────────────────────────────────────────
#  End-to-End Metrics Pipeline
# ───────────────────────────────────────────────────────────

class TestEndToEndMetricsPipeline:
    """
    Test case ID: SYS-001
    Title: Complete metrics pipeline produces valid output from raw trades.
    Preconditions: Synthetic multi-ISIN, multi-day trade data.
    """

    def test_output_row_count(self, end_to_end_metrics, realistic_trades):
        """Each ISIN × trading-day pair should produce exactly one row."""
        unique_pairs = realistic_trades.select(["Isin", "Datum"]).unique()
        assert len(end_to_end_metrics) == len(unique_pairs)

    def test_output_schema_complete(self, end_to_end_metrics):
        """All 24 metric columns must be present in pipeline output."""
        expected = {
            "Isin", "Datum", "trades_today", "volume_today_units",
            "volume_today_chf", "price_min", "price_max", "price_first",
            "price_last", "price_change_pct", "log_returns",
            "volatility_daily", "amihud_daily", "spread_log_hl",
            "trade_duration_min", "off_book_pct",
            "trades_30d_median", "volume_30d_median",
            "volatility_30d_median", "amihud_30d_median",
            "volume_spike", "activity_spike", "price_gap", "anomaly_score",
        }
        assert expected == set(end_to_end_metrics.columns)

    def test_trades_today_positive(self, end_to_end_metrics):
        """Every row must have at least 1 trade."""
        assert end_to_end_metrics["trades_today"].min() >= 1

    def test_volume_chf_positive(self, end_to_end_metrics):
        """Volume in CHF must be positive (price × volume)."""
        assert end_to_end_metrics["volume_today_chf"].min() > 0

    def test_price_bounds_consistent(self, end_to_end_metrics):
        """price_min <= price_first, price_last <= price_max for every row."""
        df = end_to_end_metrics
        assert (df["price_min"] <= df["price_max"]).all()
        assert (df["price_min"] <= df["price_first"]).all()
        assert (df["price_min"] <= df["price_last"]).all()
        assert (df["price_first"] <= df["price_max"]).all()
        assert (df["price_last"] <= df["price_max"]).all()

    def test_anomaly_score_range(self, end_to_end_metrics):
        """Anomaly scores must be in [0, 7]."""
        scores = end_to_end_metrics["anomaly_score"]
        assert scores.min() >= 0
        assert scores.max() <= 7

    def test_spread_log_hl_non_negative(self, end_to_end_metrics):
        """Spread proxy ln(high/low) must be >= 0 since high >= low."""
        spreads = end_to_end_metrics["spread_log_hl"]
        assert spreads.min() >= 0.0 - 1e-10  # float tolerance

    def test_boolean_flags_are_boolean(self, end_to_end_metrics):
        """volume_spike, activity_spike, price_gap must be boolean typed."""
        for col in ("volume_spike", "activity_spike", "price_gap"):
            assert end_to_end_metrics[col].dtype == pl.Boolean


# ───────────────────────────────────────────────────────────
#  Anomaly Scoring with Known Patterns
# ───────────────────────────────────────────────────────────

class TestAnomalyScoringKnownPatterns:
    """
    Test case ID: SYS-002
    Title: Anomaly scoring correctly identifies known spike patterns.
    Preconditions: Crafted trade data with deliberate spikes.
    """

    @pytest.fixture()
    def spike_trades(self) -> pl.DataFrame:
        """Create trades with an obvious volume, activity, and price spike on day 35."""
        records = []
        for day in range(1, 36):
            date_str = f"2024-01-{day:02d}" if day <= 28 else f"2024-02-{day - 28:02d}"
            if day == 35:
                # Day 35: massive volume spike + activity spike + price gap
                # Multiple trades (activity spike), high volume, large price change
                for t, (p, v) in enumerate([
                    (100.0, 500.0), (105.0, 500.0), (110.0, 500.0), (120.0, 500.0),
                ]):
                    records.append({
                        "Isin": "CH0000000001",
                        "Datum": date_str,
                        "Zeit": f"{9 + t}:00:00",
                        "Kurs": p,
                        "Volumen": v,
                        "Off Book": False,
                    })
            else:
                # Normal day: 1 trade, modest volume, stable price
                records.append({
                    "Isin": "CH0000000001",
                    "Datum": date_str,
                    "Zeit": "10:00:00",
                    "Kurs": 100.0,
                    "Volumen": 50.0,
                    "Off Book": False,
                })
        df = pl.DataFrame(records)
        return df.with_columns(pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d"))

    def test_spike_day_has_high_anomaly_score(self, spike_trades):
        """Arrange: spike on last day. Act: run pipeline. Assert: score >= 5."""
        from backend.operations.metrics import compute_daily_metrics

        result = compute_daily_metrics(spike_trades)
        last_day = result.sort("Datum").tail(1)

        score = last_day["anomaly_score"][0]
        assert score >= 5, f"Expected high anomaly score, got {score}"

    def test_normal_days_have_low_scores(self, spike_trades):
        """Normal days before the spike should have score 0."""
        from backend.operations.metrics import compute_daily_metrics

        result = compute_daily_metrics(spike_trades)
        # First 30 days (after rolling window fills)
        early_days = result.sort("Datum").head(30)
        assert early_days["anomaly_score"].max() <= 2

    @pytest.fixture()
    def no_spike_trades(self) -> pl.DataFrame:
        """Uniform trades — no anomaly expected."""
        records = []
        for day in range(1, 32):
            date_str = f"2024-01-{day:02d}" if day <= 28 else f"2024-02-{day - 28:02d}"
            records.append({
                "Isin": "CH0000000001",
                "Datum": date_str,
                "Zeit": "10:00:00",
                "Kurs": 100.0,
                "Volumen": 50.0,
                "Off Book": False,
            })
        df = pl.DataFrame(records)
        return df.with_columns(pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d"))

    def test_uniform_trades_produce_no_anomalies(self, no_spike_trades):
        """Completely uniform trading should yield anomaly_score == 0 everywhere."""
        from backend.operations.metrics import compute_daily_metrics

        result = compute_daily_metrics(no_spike_trades)
        assert result["anomaly_score"].max() == 0


# ───────────────────────────────────────────────────────────
#  End-to-End Data Flow: Parquet → Data Loader → Charts
# ───────────────────────────────────────────────────────────

class TestEndToEndDataToCharts:
    """
    Test case ID: SYS-003
    Title: Production data flows through loader into every chart function.
    Preconditions: daily_metrics.parquet exists with valid data.
    """

    def test_all_chart_functions_produce_figures(self, real_loaded_data):
        """Every chart factory must return a valid Figure from real data."""
        import plotly.graph_objects as go
        from frontend.operations.charts import (
            chart_market_activity, chart_sector_treemap, chart_top_movers,
            chart_trades_by_sector, chart_scatter_volume_price,
            chart_amihud_by_sector, chart_volatility_trend,
            chart_correlation_heatmap, chart_anomaly_severity_treemap,
            chart_security_history, chart_3d_explorer,
        )

        df_hist, latest = real_loaded_data

        charts = [
            ("market_activity", chart_market_activity(df_hist)),
            ("sector_treemap", chart_sector_treemap(latest)),
            ("top_movers", chart_top_movers(latest)),
            ("trades_by_sector", chart_trades_by_sector(latest)),
            ("scatter_volume_price", chart_scatter_volume_price(latest)),
            ("amihud_by_sector", chart_amihud_by_sector(latest)),
            ("volatility_trend", chart_volatility_trend(df_hist)),
            ("correlation_heatmap", chart_correlation_heatmap(latest)),
            ("anomaly_severity_treemap", chart_anomaly_severity_treemap(latest)),
            ("security_history", chart_security_history(df_hist, latest["Isin"].iloc[0])),
            ("3d_explorer", chart_3d_explorer(
                latest,
                x_col="volume_today_chf",
                y_col="price_change_pct",
                z_col="volatility_daily",
                color_col="anomaly_score",
                size_col="trades_today",
            )),
        ]

        for name, fig in charts:
            assert isinstance(fig, go.Figure), f"{name} did not return a Figure"
            assert len(fig.data) >= 1, f"{name} has no traces"

    def test_chart_3d_explorer_with_various_axes(self, real_loaded_data):
        """3D explorer should accept different column combinations."""
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_3d_explorer

        _, latest = real_loaded_data
        combos = [
            ("trades_today", "volatility_daily", "amihud_daily", "anomaly_score", "volume_today_chf"),
            ("spread_log_hl", "log_returns", "off_book_pct", "anomaly_score", "trades_today"),
        ]
        for x, y, z, c, s in combos:
            fig = chart_3d_explorer(latest, x_col=x, y_col=y, z_col=z, color_col=c, size_col=s)
            assert isinstance(fig, go.Figure)


# ───────────────────────────────────────────────────────────
#  Production Data Quality System Tests
# ───────────────────────────────────────────────────────────

class TestProductionDataQuality:
    """
    Test case ID: SYS-004
    Title: Production parquet satisfies data quality invariants.
    Preconditions: daily_metrics.parquet generated by full pipeline.
    """

    def test_no_duplicate_isin_date_pairs(self, real_loaded_data):
        """Each (Isin, Datum) pair should appear exactly once."""
        df_hist, _ = real_loaded_data
        dupes = df_hist.groupby(["Isin", "Datum"]).size().reset_index(name="count")
        assert dupes["count"].max() == 1

    def test_date_range_is_reasonable(self, real_loaded_data):
        """Dates should span at least 1 year and not extend into the future."""
        df_hist, _ = real_loaded_data
        min_date = df_hist["Datum"].min()
        max_date = df_hist["Datum"].max()
        span = (max_date - min_date).days
        assert span > 365, f"Date span is only {span} days"
        assert max_date <= pd.Timestamp.now() + pd.Timedelta(days=1)

    def test_isin_format_is_valid(self, real_loaded_data):
        """All ISINs should be 12 characters starting with CH."""
        _, latest = real_loaded_data
        for isin in latest["Isin"]:
            assert len(isin) == 12, f"ISIN {isin} is not 12 chars"
            assert isin.startswith("CH"), f"ISIN {isin} does not start with CH"

    def test_multiple_sectors_present(self, real_loaded_data):
        """Data should cover multiple market sectors."""
        _, latest = real_loaded_data
        sectors = latest["Sektor"].dropna().unique()
        assert len(sectors) >= 3, f"Only {len(sectors)} sectors found"

    def test_volume_and_trades_are_non_negative(self, real_loaded_data):
        """Volume and trade counts should never be negative."""
        _, latest = real_loaded_data
        assert (latest["volume_today_chf"] >= 0).all()
        assert (latest["trades_today"] >= 0).all()
        assert (latest["volume_today_units"] >= 0).all()


# ───────────────────────────────────────────────────────────
#  Metrics Computation Edge Cases (System-Level)
# ───────────────────────────────────────────────────────────

class TestMetricsEdgeCases:
    """
    Test case ID: SYS-005
    Title: Metrics handle edge-case trade data gracefully.
    """

    def test_single_trade_day(self):
        """A day with exactly one trade should produce valid metrics."""
        from backend.operations.metrics import compute_daily_metrics

        df = pl.DataFrame({
            "Isin":     ["CH0000000001"],
            "Datum":    ["2024-06-01"],
            "Zeit":     ["12:00:00"],
            "Kurs":     [100.0],
            "Volumen":  [10.0],
            "Off Book": [False],
        }).with_columns(pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d"))

        result = compute_daily_metrics(df)

        assert len(result) == 1
        assert result["trades_today"][0] == 1
        assert result["price_change_pct"][0] == pytest.approx(0.0)
        assert result["spread_log_hl"][0] == pytest.approx(0.0)

    def test_identical_prices_produce_zero_volatility(self):
        """Multiple trades at the same price → volatility_daily = 0."""
        from backend.operations.metrics import compute_daily_metrics

        df = pl.DataFrame({
            "Isin":     ["CH0000000001"] * 3,
            "Datum":    ["2024-06-01"] * 3,
            "Zeit":     ["09:00:00", "12:00:00", "15:00:00"],
            "Kurs":     [100.0, 100.0, 100.0],
            "Volumen":  [10.0, 20.0, 30.0],
            "Off Book": [False, False, False],
        }).with_columns(pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d"))

        result = compute_daily_metrics(df)
        assert result["volatility_daily"][0] == pytest.approx(0.0, abs=1e-10)
        assert result["price_change_pct"][0] == pytest.approx(0.0)

    def test_off_book_pct_calculation(self):
        """Off-book pct = (off-book trades / total trades) * 100."""
        from backend.operations.metrics import compute_daily_metrics

        df = pl.DataFrame({
            "Isin":     ["CH0000000001"] * 4,
            "Datum":    ["2024-06-01"] * 4,
            "Zeit":     ["09:00:00", "10:00:00", "11:00:00", "12:00:00"],
            "Kurs":     [100.0, 101.0, 102.0, 103.0],
            "Volumen":  [10.0, 10.0, 10.0, 10.0],
            "Off Book": [True, False, True, False],
        }).with_columns(pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d"))

        result = compute_daily_metrics(df)
        assert result["off_book_pct"][0] == pytest.approx(50.0)

    def test_large_price_gap_triggers_flag(self):
        """A >5% intraday price change should set price_gap = True."""
        from backend.operations.metrics import compute_daily_metrics

        records = []
        # 30 normal days first
        for d in range(1, 31):
            records.append({
                "Isin": "CH0000000001",
                "Datum": f"2024-01-{d:02d}" if d <= 28 else f"2024-02-{d - 28:02d}",
                "Zeit": "10:00:00",
                "Kurs": 100.0,
                "Volumen": 50.0,
                "Off Book": False,
            })
        # Day 31: 10% price gap (first=100, last=110)
        records.append({
            "Isin": "CH0000000001",
            "Datum": "2024-02-03",
            "Zeit": "09:00:00",
            "Kurs": 100.0,
            "Volumen": 50.0,
            "Off Book": False,
        })
        records.append({
            "Isin": "CH0000000001",
            "Datum": "2024-02-03",
            "Zeit": "15:00:00",
            "Kurs": 110.0,
            "Volumen": 50.0,
            "Off Book": False,
        })

        df = pl.DataFrame(records).with_columns(
            pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d")
        )
        result = compute_daily_metrics(df)
        gap_day = result.filter(pl.col("Datum") == pl.lit("2024-02-03").str.strptime(pl.Date, "%Y-%m-%d"))
        assert gap_day["price_gap"][0] is True
