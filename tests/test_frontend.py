"""
Tests for frontend module imports, utilities, and data loading.
"""
import pytest
import pandas as pd


class TestFrontendImports:
    """Verify all frontend modules can be imported."""

    def test_import_config(self):
        from frontend.operations.config import (
            BRAND_RED, BRAND_DARK, GREEN_POS, RED_NEG, BORDER_COL,
            MUTED, MUTED_SEC, PLOTLY_TPL, SECTOR_PALETTE,
            ANOMALY_LABELS, ANOMALY_COLORS, SEVERITY_TIERS,
        )
        assert BRAND_RED == "#B22222"
        assert len(SECTOR_PALETTE) == 10
        assert len(ANOMALY_LABELS) == 8
        assert len(SEVERITY_TIERS) == 5

    def test_import_styles(self):
        from frontend.operations.styles import inject_css
        assert callable(inject_css)

    def test_import_utils(self):
        from frontend.operations.utils import fmt_chf, fmt_num, fmt_pct, pct_cls, score_badge, _hex_to_rgba
        assert callable(fmt_chf)

    def test_import_data_loader(self):
        from frontend.operations.data_loader import load_data
        assert callable(load_data)

    def test_import_charts(self):
        from frontend.operations.charts import (
            chart_market_activity, chart_sector_treemap, chart_top_movers,
            chart_trades_by_sector, chart_scatter_volume_price,
            chart_amihud_by_sector, chart_volatility_trend,
            chart_correlation_heatmap, chart_anomaly_severity_treemap,
            chart_security_history, chart_3d_explorer,
        )
        assert callable(chart_market_activity)
        assert callable(chart_3d_explorer)

    def test_import_components(self):
        from frontend.operations.components import (
            render_header, render_kpis, render_market_table,
            render_native_dataframe, _flag_dot,
        )
        assert callable(render_header)


class TestFormatUtils:
    """Test number formatting functions for correctness."""

    def test_fmt_chf_millions(self):
        from frontend.operations.utils import fmt_chf
        assert fmt_chf(1_500_000) == "CHF 1.50M"

    def test_fmt_chf_thousands(self):
        from frontend.operations.utils import fmt_chf
        result = fmt_chf(12_345)
        assert "12" in result
        assert "CHF" in result

    def test_fmt_chf_small(self):
        from frontend.operations.utils import fmt_chf
        assert fmt_chf(42.5) == "CHF 42.50"

    def test_fmt_chf_nan(self):
        from frontend.operations.utils import fmt_chf
        assert fmt_chf(float("nan")) == "—"

    def test_fmt_num_millions(self):
        from frontend.operations.utils import fmt_num
        assert "M" in fmt_num(2_500_000)

    def test_fmt_num_thousands(self):
        from frontend.operations.utils import fmt_num
        result = fmt_num(5_000, dec=0)
        assert "5" in result

    def test_fmt_pct_positive(self):
        from frontend.operations.utils import fmt_pct
        assert fmt_pct(3.14) == "+3.14%"

    def test_fmt_pct_negative(self):
        from frontend.operations.utils import fmt_pct
        assert fmt_pct(-2.5) == "-2.50%"

    def test_fmt_pct_nan(self):
        from frontend.operations.utils import fmt_pct
        assert fmt_pct(float("nan")) == "—"

    def test_pct_cls_positive(self):
        from frontend.operations.utils import pct_cls
        assert pct_cls(1.0) == "pos"

    def test_pct_cls_negative(self):
        from frontend.operations.utils import pct_cls
        assert pct_cls(-1.0) == "neg"

    def test_score_badge_clean(self):
        from frontend.operations.utils import score_badge
        badge = score_badge(0)
        assert "bdg-clean" in badge
        assert "Clean" in badge

    def test_score_badge_extreme(self):
        from frontend.operations.utils import score_badge
        badge = score_badge(7)
        assert "bdg-extreme" in badge
        assert "Extreme" in badge

    def test_hex_to_rgba(self):
        from frontend.operations.utils import _hex_to_rgba
        assert _hex_to_rgba("#B22222", 0.5) == "rgba(178,34,34,0.5)"


class TestSeverityTiers:
    """Verify severity tier mappings are consistent."""

    def test_tiers_cover_all_scores(self):
        from frontend.operations.config import SEVERITY_TIERS
        all_scores = set()
        for scores in SEVERITY_TIERS.values():
            all_scores.update(scores)
        assert all_scores == {0, 1, 2, 3, 4, 5, 6, 7}

    def test_anomaly_labels_keys(self):
        from frontend.operations.config import ANOMALY_LABELS
        assert set(ANOMALY_LABELS.keys()) == {0, 1, 2, 3, 4, 5, 6, 7}


class TestDataLoading:
    """Test data loading with actual parquet files."""

    def test_load_data_returns_tuple(self):
        from frontend.operations.data_loader import load_data
        result = load_data()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_load_data_returns_dataframes(self):
        from frontend.operations.data_loader import load_data
        df_hist, latest = load_data()
        assert isinstance(df_hist, pd.DataFrame)
        assert isinstance(latest, pd.DataFrame)

    def test_load_data_not_empty(self):
        from frontend.operations.data_loader import load_data
        df_hist, latest = load_data()
        assert not df_hist.empty
        assert not latest.empty

    def test_load_data_has_required_columns(self):
        from frontend.operations.data_loader import load_data
        df_hist, latest = load_data()
        required = ["Isin", "Datum", "trades_today", "volume_today_chf",
                     "price_change_pct", "anomaly_score"]
        for col in required:
            assert col in df_hist.columns, f"Missing column: {col}"
            assert col in latest.columns, f"Missing column in latest: {col}"

    def test_latest_is_one_row_per_isin(self):
        from frontend.operations.data_loader import load_data
        _, latest = load_data()
        assert latest["Isin"].is_unique


class TestChartGeneration:
    """Smoke tests for chart functions — verify they return Plotly figures."""

    @pytest.fixture(scope="class")
    def data(self):
        from frontend.operations.data_loader import load_data
        return load_data()

    def test_chart_market_activity(self, data):
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_market_activity
        fig = chart_market_activity(data[0])
        assert isinstance(fig, go.Figure)

    def test_chart_sector_treemap(self, data):
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_sector_treemap
        fig = chart_sector_treemap(data[1])
        assert isinstance(fig, go.Figure)

    def test_chart_top_movers(self, data):
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_top_movers
        fig = chart_top_movers(data[1])
        assert isinstance(fig, go.Figure)

    def test_chart_correlation_heatmap(self, data):
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_correlation_heatmap
        fig = chart_correlation_heatmap(data[1])
        assert isinstance(fig, go.Figure)

    def test_chart_anomaly_severity_treemap(self, data):
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_anomaly_severity_treemap
        fig = chart_anomaly_severity_treemap(data[1])
        assert isinstance(fig, go.Figure)

    def test_chart_security_history(self, data):
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_security_history
        isin = data[1]["Isin"].iloc[0]
        fig = chart_security_history(data[0], isin)
        assert isinstance(fig, go.Figure)

    def test_chart_3d_explorer(self, data):
        import plotly.graph_objects as go
        from frontend.operations.charts import chart_3d_explorer
        fig = chart_3d_explorer(
            data[1],
            x_col="volume_today_chf",
            y_col="price_change_pct",
            z_col="volatility_daily",
            color_col="anomaly_score",
            size_col="trades_today",
        )
        assert isinstance(fig, go.Figure)
