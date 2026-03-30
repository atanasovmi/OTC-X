"""
Tests for path resolution across the restructured repository.
Ensures all modules can locate their data files correctly.
"""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestBackendPaths:
    """Verify backend operation modules resolve data paths to backend/data/."""

    def test_soft_crawl_data_dir(self):
        src = ROOT / "backend" / "operations" / "soft_crawl.py"
        data_dir = src.resolve().parent.parent / "data"
        assert data_dir == ROOT / "backend" / "data"

    def test_fetcher_paths(self):
        src = ROOT / "backend" / "operations" / "fetcher.py"
        script_dir = src.resolve().parent
        assert script_dir.parent / "data" / "securities.csv" == ROOT / "backend" / "data" / "securities.csv"
        assert script_dir.parent / "data" / "trades" == ROOT / "backend" / "data" / "trades"
        assert script_dir.parent / "logs" == ROOT / "backend" / "logs"

    def test_build_master_paths(self):
        src = ROOT / "backend" / "operations" / "build_master_parquet.py"
        script_dir = src.resolve().parent
        assert script_dir.parent / "data" / "trades" == ROOT / "backend" / "data" / "trades"
        assert script_dir.parent / "data" / "master_trades.parquet" == ROOT / "backend" / "data" / "master_trades.parquet"

    def test_metrics_paths(self):
        src = ROOT / "backend" / "operations" / "metrics.py"
        script_dir = src.resolve().parent
        assert script_dir.parent / "data" / "master_trades.parquet" == ROOT / "backend" / "data" / "master_trades.parquet"
        assert script_dir.parent / "data" / "securities.csv" == ROOT / "backend" / "data" / "securities.csv"
        assert script_dir.parent / "data" / "daily_metrics.parquet" == ROOT / "backend" / "data" / "daily_metrics.parquet"


class TestFrontendPaths:
    """Verify frontend data_loader resolves to backend/data/."""

    def test_data_loader_path(self):
        src = ROOT / "frontend" / "operations" / "data_loader.py"
        data_path = src.resolve().parent.parent.parent / "backend" / "data" / "daily_metrics.parquet"
        assert data_path == ROOT / "backend" / "data" / "daily_metrics.parquet"


class TestDataFilesExist:
    """Verify required data files are present."""

    def test_daily_metrics_exists(self):
        assert (ROOT / "backend" / "data" / "daily_metrics.parquet").exists()

    def test_securities_csv_exists(self):
        assert (ROOT / "backend" / "data" / "securities.csv").exists()

    def test_securities_csv_canonical_exists(self):
        assert (ROOT / "backend" / "data" / "securities.csv").exists()

    def test_master_trades_exists(self):
        assert (ROOT / "backend" / "data" / "master_trades.parquet").exists()

    def test_trades_dir_exists(self):
        assert (ROOT / "backend" / "data" / "trades").is_dir()


class TestDirectoryStructure:
    """Verify the repository layout."""

    def test_backend_package(self):
        assert (ROOT / "backend" / "__init__.py").exists()
        assert (ROOT / "backend" / "pipeline.py").exists()

    def test_backend_operations_package(self):
        assert (ROOT / "backend" / "operations" / "__init__.py").exists()
        for mod in ["soft_crawl.py", "fetcher.py", "build_master_parquet.py", "metrics.py"]:
            assert (ROOT / "backend" / "operations" / mod).exists()

    def test_frontend_package(self):
        assert (ROOT / "frontend" / "__init__.py").exists()
        assert (ROOT / "frontend" / "app.py").exists()

    def test_frontend_operations_package(self):
        assert (ROOT / "frontend" / "operations" / "__init__.py").exists()
        for mod in ["config.py", "styles.py", "utils.py",
                     "data_loader.py", "charts.py", "components.py"]:
            assert (ROOT / "frontend" / "operations" / mod).exists()

    def test_streamlit_config(self):
        assert (ROOT / ".streamlit" / "config.toml").exists()
