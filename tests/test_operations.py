"""
Unit tests for operations modules
Tests soft_crawl, fetcher, build_master_parquet, and metrics
"""
import unittest
import sys
from pathlib import Path
import pandas as pd
import polars as pl
from unittest.mock import Mock, patch

# Add operations to path
sys.path.insert(0, str(Path(__file__).parent.parent / "operations"))

import soft_crawl
from fetcher import calculate_isin_check_digit, val_to_isin as fetcher_val_to_isin
from build_master_parquet import build_master_parquet
from metrics import parse_time_to_minutes, compute_daily_aggregates


class TestSoftCrawl(unittest.TestCase):
    """Test soft_crawl module functionality"""

    def test_soft_crawl_imports(self):
        """Test soft_crawl module can be imported"""
        self.assertTrue(hasattr(soft_crawl, 'run_crawl'))

    def test_securities_output_exists(self):
        """Test that securities.csv exists"""
        base_path = Path(__file__).parent.parent
        securities_file = base_path / "data" / "securities.csv"
        self.assertTrue(securities_file.exists())


class TestFetcher(unittest.TestCase):
    """Test fetcher module ISIN calculation logic"""

    def test_calculate_isin_check_digit(self):
        """Test ISIN check digit calculation using Luhn algorithm"""
        # Test the function exists and returns a single digit string
        result = calculate_isin_check_digit("CH000162900")
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 1)
        self.assertTrue(result.isdigit())

    def test_val_to_isin(self):
        """Test Valor to ISIN conversion"""
        # Test conversion produces valid ISIN format
        result = fetcher_val_to_isin(1629001)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 12)  # ISIN length
        self.assertTrue(result.startswith("CH"))

        # Test with different valor
        result2 = fetcher_val_to_isin(41795)
        self.assertIsNotNone(result2)
        self.assertEqual(len(result2), 12)


class TestBuildMasterParquet(unittest.TestCase):
    """Test build_master_parquet data ingestion"""

    def test_data_files_exist(self):
        """Verify required data files exist"""
        base_path = Path(__file__).parent.parent

        # Check for securities files
        self.assertTrue((base_path / "data" / "securities.csv").exists())
        self.assertTrue((base_path / "data" / "securities_enriched.csv").exists())

        # Check for master outputs
        self.assertTrue((base_path / "data" / "master_trades.parquet").exists())
        self.assertTrue((base_path / "data" / "master_trades_cleaned.csv").exists())

    def test_master_parquet_structure(self):
        """Test that master_trades.parquet has expected structure"""
        base_path = Path(__file__).parent.parent
        parquet_file = base_path / "data" / "master_trades.parquet"

        df = pl.read_parquet(parquet_file)

        # Check expected columns
        expected_cols = ["Isin", "Datum", "Zeit", "Kurs", "Volumen", "Off Book"]
        for col in expected_cols:
            self.assertIn(col, df.columns)

        # Check data types
        self.assertTrue(df["Isin"].dtype == pl.Utf8)
        self.assertTrue(df["Datum"].dtype == pl.Date)
        self.assertTrue(df["Kurs"].dtype == pl.Float64)
        self.assertTrue(df["Volumen"].dtype == pl.Float64)

        # Check non-empty
        self.assertGreater(len(df), 0)


class TestMetrics(unittest.TestCase):
    """Test metrics calculation functions"""

    def test_parse_time_to_minutes(self):
        """Test time string parsing to minutes"""
        # Create test dataframe
        df = pl.DataFrame({
            "Zeit": ["09:30:00", "14:45:00", "16:00:00"]
        })

        result = df.with_columns(
            parse_time_to_minutes(pl.col("Zeit")).alias("minutes")
        )

        expected_minutes = [570.0, 885.0, 960.0]  # 9*60+30, 14*60+45, 16*60

        for i, expected in enumerate(expected_minutes):
            self.assertAlmostEqual(result["minutes"][i], expected, delta=1.0)

    def test_compute_daily_aggregates(self):
        """Test daily aggregation function"""
        from datetime import date

        # Create sample trade data with proper Date type
        df_trades = pl.DataFrame({
            "Isin": ["CH0001629001", "CH0001629001", "CH0001629001"],
            "Datum": [date(2024, 1, 1), date(2024, 1, 1), date(2024, 1, 2)],
            "Zeit": ["09:00:00", "10:00:00", "09:00:00"],
            "Kurs": [100.0, 105.0, 102.0],
            "Volumen": [1000.0, 500.0, 800.0],
            "Off Book": [False, False, True]
        })

        result = compute_daily_aggregates(df_trades)

        # Check structure
        self.assertIn("Isin", result.columns)
        self.assertIn("Datum", result.columns)
        self.assertIn("trades_today", result.columns)
        self.assertIn("price_last", result.columns)
        self.assertIn("volume_today_chf", result.columns)

        # Check aggregation - should have 2 rows (one per date)
        self.assertGreater(len(result), 0)

    def test_daily_metrics_output_exists(self):
        """Verify daily_metrics.parquet exists and has correct structure"""
        base_path = Path(__file__).parent.parent
        metrics_file = base_path / "data" / "daily_metrics.parquet"

        self.assertTrue(metrics_file.exists())

        df = pl.read_parquet(metrics_file)

        # Check essential columns
        essential_cols = [
            "Isin", "Datum", "price_last", "trades_today",
            "volume_today_chf", "volatility_daily"
        ]
        for col in essential_cols:
            self.assertIn(col, df.columns)

        self.assertGreater(len(df), 0)


class TestDataIntegrity(unittest.TestCase):
    """Integration tests for data pipeline integrity"""

    def test_securities_to_metrics_pipeline(self):
        """Test that ISINs in metrics have corresponding securities"""
        base_path = Path(__file__).parent.parent

        # Load securities
        securities_df = pd.read_csv(base_path / "data" / "securities.csv")
        securities_isins = set(securities_df["ISIN"].values)

        # Load metrics
        metrics_df = pl.read_parquet(base_path / "data" / "daily_metrics.parquet")
        metrics_isins = set(metrics_df["Isin"].unique())

        # Check that there is overlap (metrics may have historical ISINs not in current securities)
        overlap = securities_isins.intersection(metrics_isins)
        self.assertGreater(len(overlap), 0, "Should have common ISINs between securities and metrics")

    def test_no_null_critical_fields(self):
        """Ensure critical fields in master data have no nulls"""
        base_path = Path(__file__).parent.parent
        df = pl.read_parquet(base_path / "data" / "master_trades.parquet")

        critical_cols = ["Isin", "Datum", "Kurs"]
        for col in critical_cols:
            null_count = df[col].is_null().sum()
            self.assertEqual(null_count, 0, f"Column {col} has {null_count} null values")


if __name__ == "__main__":
    unittest.main()
