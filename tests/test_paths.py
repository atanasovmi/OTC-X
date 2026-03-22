"""
Tests for path resolution across the restructured repository.
Ensures all modules can locate their data files correctly.
"""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestBackendPaths:
    """Verify backend operation modules resolve data paths to <root>/data/."""

    def test_soft_crawl_data_dir(self):
        src = ROOT / "backend" / "operations" / "soft_crawl.py"
        data_dir = src.resolve().parent.parent.parent / "data"
        assert data_dir == ROOT / "data"

    def test_fetcher_paths(self):
        src = ROOT / "backend" / "operations" / "fetcher.py"
        script_dir = src.resolve().parent
        assert script_dir.parent.parent / "data" / "securities.csv" == ROOT / "data" / "securities.csv"
        assert script_dir.parent.parent / "data" / "trades" == ROOT / "data" / "trades"
        assert script_dir.parent.parent / "logs" == ROOT / "logs"

    def test_build_master_paths(self):
        src = ROOT / "backend" / "operations" / "build_master_parquet.py"
        script_dir = src.resolve().parent
        assert script_dir.parent.parent / "data" / "trades" == ROOT / "data" / "trades"
        assert script_dir.parent.parent / "data" / "master_trades.parquet" == ROOT / "data" / "master_trades.parquet"

    def test_metrics_paths(self):
        src = ROOT / "backend" / "operations" / "metrics.py"
        script_dir = src.resolve().parent
        assert script_dir.parent.parent / "data" / "master_trades.parquet" == ROOT / "data" / "master_trades.parquet"
        assert script_dir.parent.parent / "data" / "securities_enriched.csv" == ROOT / "data" / "securities_enriched.csv"
        assert script_dir.parent.parent / "data" / "daily_metrics.parquet" == ROOT / "data" / "daily_metrics.parquet"


class TestFrontendPaths:
    """Verify frontend data_loader resolves to <root>/data/."""

    def test_data_loader_path(self):
        src = ROOT / "frontend" / "data_loader.py"
        data_path = src.resolve().parent.parent / "data" / "daily_metrics.parquet"
        assert data_path == ROOT / "data" / "daily_metrics.parquet"


class TestDataFilesExist:
    """Verify required data files are present."""

    def test_daily_metrics_exists(self):
        assert (ROOT / "data" / "daily_metrics.parquet").exists()

    def test_securities_csv_exists(self):
        assert (ROOT / "data" / "securities.csv").exists()

    def test_securities_enriched_exists(self):
        assert (ROOT / "data" / "securities_enriched.csv").exists()

    def test_master_trades_exists(self):
        assert (ROOT / "data" / "master_trades.parquet").exists()

    def test_trades_dir_exists(self):
        assert (ROOT / "data" / "trades").is_dir()


class TestDirectoryStructure:
    """Verify the new repository layout."""

    def test_backend_package(self):
        assert (ROOT / "backend" / "__init__.py").exists()
        assert (ROOT / "backend" / "pipeline.py").exists()

    def test_backend_operations_package(self):
        assert (ROOT / "backend" / "operations" / "__init__.py").exists()
        for mod in ["soft_crawl.py", "fetcher.py", "build_master_parquet.py", "metrics.py"]:
            assert (ROOT / "backend" / "operations" / mod).exists()

    def test_frontend_package(self):
        assert (ROOT / "frontend" / "__init__.py").exists()
        for mod in ["app.py", "config.py", "styles.py", "utils.py",
                     "data_loader.py", "charts.py", "components.py"]:
            assert (ROOT / "frontend" / mod).exists()

    def test_entry_points(self):
        assert (ROOT / "run_backend.py").exists()
        assert (ROOT / "run_frontend.py").exists()

    def test_streamlit_config(self):
        assert (ROOT / ".streamlit" / "config.toml").exists()
