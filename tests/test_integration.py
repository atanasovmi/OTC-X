"""Integration tests for the OTC-X platform.

Tests two or more modules working together — verifying that the
metrics pipeline stages chain correctly, the data loader interacts
properly with the parquet output, and the charting layer correctly
consumes loaded data.
"""
import pytest
import polars as pl
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent


# ───────────────────────────────────────────────────────────
#  Fixtures
# ───────────────────────────────────────────────────────────

@pytest.fixture()
def sample_trades() -> pl.DataFrame:
    """Minimal synthetic trade DataFrame matching build_master output schema."""
    return pl.DataFrame({
        "Isin":     ["CH0000000001"] * 5 + ["CH0000000002"] * 3,
        "Datum":    [
            # ISIN-1: two trading days
            "2024-01-15", "2024-01-15", "2024-01-15",
            "2024-01-16", "2024-01-16",
            # ISIN-2: one trading day
            "2024-01-15", "2024-01-15", "2024-01-15",
        ],
        "Zeit":     [
            "09:00:00", "10:30:00", "14:00:00",
            "09:15:00", "11:00:00",
            "09:00:00", "12:00:00", "15:00:00",
        ],
        "Kurs":     [100.0, 102.0, 105.0, 105.0, 110.0, 50.0, 55.0, 52.0],
        "Volumen":  [10.0, 20.0, 15.0, 25.0, 30.0, 100.0, 200.0, 150.0],
        "Off Book": [False, False, True, False, False, False, True, False],
    }).with_columns(pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d"))


@pytest.fixture()
def multi_day_trades() -> pl.DataFrame:
    """Trades spanning 35+ days for rolling baseline coverage."""
    rows = []
    for day_offset in range(40):
        date_str = f"2024-01-{(day_offset % 28) + 1:02d}" if day_offset < 28 else f"2024-02-{day_offset - 27:02d}"
        rows.append({
            "Isin": "CH0000000001",
            "Datum": date_str,
            "Zeit": "10:00:00",
            "Kurs": 100.0 + day_offset * 0.5,
            "Volumen": 50.0 + day_offset,
            "Off Book": False,
        })
    df = pl.DataFrame(rows)
    return df.with_columns(pl.col("Datum").str.strptime(pl.Date, "%Y-%m-%d"))


@pytest.fixture(scope="module")
def loaded_data():
    """Load real data once per module via the frontend data loader."""
    from frontend.operations.data_loader import load_data
    return load_data()


# ───────────────────────────────────────────────────────────
#  Metrics Pipeline Integration
# ───────────────────────────────────────────────────────────

class TestMetricsPipelineIntegration:
    """Test that all four metrics stages chain together correctly."""

    def test_aggregates_to_liquidity(self, sample_trades):
        """Arrange: raw trades. Act: aggregate then derive liquidity. Assert: columns added."""
        from backend.operations.metrics import compute_daily_aggregates, compute_liquidity_metrics

        # Arrange — already in fixture
        # Act
        daily = compute_daily_aggregates(sample_trades)
        result = compute_liquidity_metrics(daily)

        # Assert — liquidity columns exist and are numeric
        for col in ("price_change_pct", "log_returns", "spread_log_hl", "amihud_daily"):
            assert col in result.columns

        # Price change for ISIN-1 day 1: (105-100)/100*100 = 5%
        isin1_d1 = result.filter(
            (pl.col("Isin") == "CH0000000001") & (pl.col("Datum") == pl.lit("2024-01-15").str.strptime(pl.Date, "%Y-%m-%d"))
        )
        assert len(isin1_d1) == 1
        assert isin1_d1["price_change_pct"][0] == pytest.approx(5.0, abs=0.1)

    def test_liquidity_to_rolling(self, sample_trades):
        """Test rolling baseline computation after liquidity step."""
        from backend.operations.metrics import (
            compute_daily_aggregates, compute_liquidity_metrics, compute_rolling_baselines,
        )

        daily = compute_daily_aggregates(sample_trades)
        metrics = compute_liquidity_metrics(daily)
        result = compute_rolling_baselines(metrics)

        # Assert rolling columns created
        for col in ("trades_30d_median", "volume_30d_median", "volatility_30d_median", "amihud_30d_median"):
            assert col in result.columns
        # With only 1-2 days, rolling median == the value itself (min_samples=1)
        assert result["trades_30d_median"].null_count() == 0

    def test_rolling_to_anomaly(self, sample_trades):
        """Test anomaly flag computation on top of rolling baselines."""
        from backend.operations.metrics import (
            compute_daily_aggregates, compute_liquidity_metrics,
            compute_rolling_baselines, compute_anomaly_flags,
        )

        daily = compute_daily_aggregates(sample_trades)
        metrics = compute_liquidity_metrics(daily)
        rolling = compute_rolling_baselines(metrics)
        result = compute_anomaly_flags(rolling)

        # Assert anomaly columns
        assert "volume_spike" in result.columns
        assert "activity_spike" in result.columns
        assert "price_gap" in result.columns
        assert "anomaly_score" in result.columns

        # Score range: 0-7
        scores = result["anomaly_score"].to_list()
        assert all(0 <= s <= 7 for s in scores)

    def test_full_compute_daily_metrics(self, sample_trades):
        """Test the unified orchestrator function end-to-end."""
        from backend.operations.metrics import compute_daily_metrics

        result = compute_daily_metrics(sample_trades)

        # Two ISINs × their respective trading days
        assert len(result) >= 3  # ISIN-1 has 2 days, ISIN-2 has 1 day
        assert result["Isin"].n_unique() == 2

        # All expected columns present
        expected_cols = {
            "Isin", "Datum", "trades_today", "volume_today_units",
            "volume_today_chf", "price_min", "price_max", "price_first",
            "price_last", "price_change_pct", "log_returns",
            "volatility_daily", "amihud_daily", "spread_log_hl",
            "trade_duration_min", "off_book_pct",
            "trades_30d_median", "volume_30d_median",
            "volatility_30d_median", "amihud_30d_median",
            "volume_spike", "activity_spike", "price_gap", "anomaly_score",
        }
        assert expected_cols.issubset(set(result.columns))


class TestMetricsRollingWithSufficientHistory:
    """Test rolling baselines with enough data points (>30 days)."""

    def test_rolling_window_fills_after_30_days(self, multi_day_trades):
        """Arrange: 40-day single-ISIN trades. Act: full pipeline. Assert: medians stabilise."""
        from backend.operations.metrics import compute_daily_metrics

        result = compute_daily_metrics(multi_day_trades)
        result_sorted = result.sort("Datum")

        # After day 30, the rolling median should not be null
        medians = result_sorted["volume_30d_median"].to_list()
        assert all(m is not None for m in medians)

    def test_anomaly_detection_uses_rolling_context(self, multi_day_trades):
        """Volume spike depends on 30-day median — verify it with uniform data."""
        from backend.operations.metrics import compute_daily_metrics

        result = compute_daily_metrics(multi_day_trades)
        # With slowly growing volume, most days should NOT trigger volume_spike
        spike_count = result["volume_spike"].sum()
        total_count = len(result)
        # At most a small fraction should spike (volume grows slowly)
        assert spike_count < total_count * 0.5


# ───────────────────────────────────────────────────────────
#  Data Loader ↔ Parquet Integration
# ───────────────────────────────────────────────────────────

class TestDataLoaderParquetIntegration:
    """Test that data_loader correctly reads and transforms the parquet file."""

    def test_datum_is_datetime(self, loaded_data):
        """Arrange: load real data. Act: check types. Assert: Datum is datetime64."""
        df_hist, latest = loaded_data
        assert pd.api.types.is_datetime64_any_dtype(df_hist["Datum"])
        assert pd.api.types.is_datetime64_any_dtype(latest["Datum"])

    def test_latest_has_fewer_rows_than_hist(self, loaded_data):
        """Latest should be one row per ISIN, much less than full history."""
        df_hist, latest = loaded_data
        assert len(latest) < len(df_hist)

    def test_off_book_pct_patched_with_mean(self, loaded_data):
        """Off-book pct in latest should reflect historical mean, not single-day value."""
        df_hist, latest = loaded_data
        # Historical mean should differ from zero for at least some ISINs
        hist_means = df_hist.groupby("Isin")["off_book_pct"].mean()
        # Verify latest off_book_pct aligns with the historical mean
        sample_isin = latest["Isin"].iloc[0]
        expected = hist_means.get(sample_isin, 0.0)
        actual = latest.loc[latest["Isin"] == sample_isin, "off_book_pct"].iloc[0]
        assert actual == pytest.approx(expected, abs=0.01)

    def test_numeric_columns_are_float(self, loaded_data):
        """Key metric columns should be numeric types."""
        _, latest = loaded_data
        numeric_cols = [
            "volume_today_chf", "price_change_pct", "volatility_daily",
            "amihud_daily", "spread_log_hl",
        ]
        for col in numeric_cols:
            if col in latest.columns:
                assert pd.api.types.is_numeric_dtype(latest[col]), f"{col} is not numeric"

    def test_anomaly_score_range(self, loaded_data):
        """Anomaly scores must be in [0, 7]."""
        _, latest = loaded_data
        assert latest["anomaly_score"].min() >= 0
        assert latest["anomaly_score"].max() <= 7


# ───────────────────────────────────────────────────────────
#  Charts ↔ Data Loader Integration
# ───────────────────────────────────────────────────────────

class TestChartsDataIntegration:
    """Verify chart functions produce valid Plotly figures from loaded data."""

    def test_volume_by_sector_chart_has_data(self, loaded_data):
        """Arrange: real data. Act: generate chart. Assert: figure has traces."""
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_volume_by_sector

        _, latest = loaded_data
        fig = chart_volume_by_sector(latest)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_scatter_volume_price_uses_sectors(self, loaded_data):
        """Chart should contain per-sector colour traces."""
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_scatter_volume_price

        _, latest = loaded_data
        fig = chart_scatter_volume_price(latest)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_amihud_by_sector_chart(self, loaded_data):
        """Amihud box-plot should render without errors."""
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_amihud_by_sector

        _, latest = loaded_data
        fig = chart_amihud_by_sector(latest)
        assert isinstance(fig, go.Figure)

    def test_volatility_trend_chart(self, loaded_data):
        """Rolling volatility needs historical panel data."""
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_volatility_trend

        df_hist, _ = loaded_data
        fig = chart_volatility_trend(df_hist)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_security_history_returns_subplots(self, loaded_data):
        """Per-security chart should have price + volume sub-panels."""
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_security_history

        df_hist, latest = loaded_data
        isin = latest["Isin"].iloc[0]
        fig = chart_security_history(df_hist, isin)
        assert isinstance(fig, go.Figure)
        # Should have at least 2 traces (price line + volume bars)
        assert len(fig.data) >= 2


# ───────────────────────────────────────────────────────────
#  ISIN Calculation ↔ Fetcher Integration
# ───────────────────────────────────────────────────────────

class TestISINFetcherIntegration:
    """Test ISIN generation flows into download logic correctly."""

    @pytest.mark.parametrize("valor,expected_prefix", [
        ("1629001", "CH0016290"),
        ("100", "CH0000001"),
        ("999999999", "CH9999999"),
    ])
    def test_val_to_isin_produces_valid_format(self, valor, expected_prefix):
        """Arrange: Valor string. Act: convert. Assert: proper CH-prefix + 12 chars."""
        from backend.operations.fetcher import val_to_isin
        isin = val_to_isin(valor)
        assert isin is not None
        assert len(isin) == 12
        assert isin.startswith(expected_prefix)

    def test_download_trades_success_with_mock(self, tmp_path):
        """Integration: val_to_isin → download_trades with mocked HTTP."""
        from backend.operations.fetcher import val_to_isin, download_trades

        isin = val_to_isin("1629001")
        assert isin is not None

        # Mock the session and OUTPUT_DIR
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"Isin,Datum,Zeit,Kurs,Volumen,Off Book\nCH001,01.01.2024,09:00:00,100.0,10,\n"
        mock_session.get.return_value = mock_response

        with patch("backend.operations.fetcher.OUTPUT_DIR", tmp_path):
            result = download_trades(isin, mock_session)

        assert result == "success"
        # File should have been written
        files = list(tmp_path.glob("*.csv"))
        assert len(files) == 1

    def test_download_trades_404_returns_not_found(self, tmp_path):
        """Arrange: mock 404 response. Act: download. Assert: returns 'not_found'."""
        from backend.operations.fetcher import download_trades

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response

        with patch("backend.operations.fetcher.OUTPUT_DIR", tmp_path):
            result = download_trades("CH0000000001", mock_session)

        assert result == "not_found"

    def test_download_trades_rate_limit_retry(self, tmp_path):
        """Arrange: first call returns 429, retry returns 200. Assert: success."""
        from backend.operations.fetcher import download_trades

        mock_session = MagicMock()

        response_429 = MagicMock()
        response_429.status_code = 429

        response_200 = MagicMock()
        response_200.status_code = 200
        response_200.content = b"header\ndata\n"

        mock_session.get.side_effect = [response_429, response_200]

        with patch("backend.operations.fetcher.OUTPUT_DIR", tmp_path):
            result = download_trades("CH0000000001", mock_session)

        assert result == "success"
        assert mock_session.get.call_count == 2


# ───────────────────────────────────────────────────────────
#  Config ↔ Utils Integration
# ───────────────────────────────────────────────────────────

class TestConfigUtilsIntegration:
    """Test that config constants are correctly consumed by utility functions."""

    def test_score_badge_covers_all_anomaly_labels(self):
        """Every score in ANOMALY_LABELS should produce a valid badge."""
        from frontend.operations.config import ANOMALY_LABELS
        from frontend.operations.utils import score_badge

        for score, label in ANOMALY_LABELS.items():
            badge = score_badge(score)
            assert label in badge
            assert "bdg" in badge

    def test_severity_tiers_map_to_valid_labels(self):
        """Each tier's scores should map to existing ANOMALY_LABELS entries."""
        from frontend.operations.config import SEVERITY_TIERS, ANOMALY_LABELS

        for tier_name, scores in SEVERITY_TIERS.items():
            for s in scores:
                assert s in ANOMALY_LABELS, f"Score {s} in tier {tier_name} has no label"
