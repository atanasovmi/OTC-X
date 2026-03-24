"""
Tests for backend module imports and basic functionality.
"""
import pytest


class TestBackendImports:
    """Verify all backend modules can be imported."""

    def test_import_pipeline(self):
        from backend.pipeline import main
        assert callable(main)

    def test_import_soft_crawl(self):
        from backend.operations.soft_crawl import run_crawl
        assert callable(run_crawl)

    def test_import_fetcher(self):
        from backend.operations.fetcher import main as run_fetcher
        from backend.operations.fetcher import val_to_isin, calculate_isin_check_digit
        assert callable(run_fetcher)
        assert callable(val_to_isin)

    def test_import_build_master(self):
        from backend.operations.build_master_parquet import build_master_parquet
        assert callable(build_master_parquet)

    def test_import_metrics(self):
        from backend.operations.metrics import main as run_metrics
        from backend.operations.metrics import compute_daily_metrics
        assert callable(run_metrics)
        assert callable(compute_daily_metrics)


class TestISINCalculation:
    """Test ISIN check digit calculation from the fetcher module."""

    def test_known_isin(self):
        from backend.operations.fetcher import val_to_isin
        # Swiss ISIN for Valor 1629001: CH0016290019
        result = val_to_isin("1629001")
        assert result is not None
        assert result.startswith("CH")
        assert len(result) == 12

    def test_invalid_valor(self):
        from backend.operations.fetcher import val_to_isin
        assert val_to_isin("abc") is None
        assert val_to_isin(None) is None

    def test_float_valor(self):
        from backend.operations.fetcher import val_to_isin
        result = val_to_isin("1629001.0")
        assert result is not None
        assert result.startswith("CH")


class TestMetricsPipeline:
    """Test metrics computation functions with sample data."""

    def test_parse_time_to_minutes(self):
        import polars as pl
        from backend.operations.metrics import parse_time_to_minutes

        df = pl.DataFrame({"Zeit": ["09:30:00", "12:00:00", "15:45:00"]})
        result = df.select(parse_time_to_minutes(pl.col("Zeit")).alias("minutes"))
        mins = result["minutes"].to_list()
        assert mins[0] == pytest.approx(570.0)  # 9*60 + 30
        assert mins[1] == pytest.approx(720.0)  # 12*60
        assert mins[2] == pytest.approx(945.0)  # 15*60 + 45
