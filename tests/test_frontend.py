"""
Integration tests for Streamlit frontend (modular architecture)
Tests data loading, formatting, frontend modules, and file structure
"""
import unittest
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import re


class TestFrontendStructure(unittest.TestCase):
    """Test frontend file structure and constants"""

    def test_app_py_exists(self):
        """Test that app.py exists"""
        app_path = Path(__file__).parent.parent / "app.py"
        self.assertTrue(app_path.exists())

    def test_app_py_has_streamlit_config(self):
        """Test that app.py has streamlit configuration"""
        app_path = Path(__file__).parent.parent / "app.py"
        content = app_path.read_text()

        self.assertIn("streamlit", content.lower())
        self.assertIn("st.set_page_config", content)

    def test_brand_constants_defined(self):
        """Test that brand constants are imported in app.py or defined in frontend"""
        # Check if constants are importable from frontend package
        frontend_config = Path(__file__).parent.parent / "frontend" / "config.py"
        self.assertTrue(frontend_config.exists(), "frontend/config.py must exist")

        config_content = frontend_config.read_text()
        self.assertIn("BRAND_RED", config_content)
        self.assertIn("BRAND_DARK", config_content)
        self.assertIn("GREEN_POS", config_content)
        self.assertIn("RED_NEG", config_content)

    def test_sector_palette_defined(self):
        """Test that sector palette is defined in frontend"""
        frontend_config = Path(__file__).parent.parent / "frontend" / "config.py"
        config_content = frontend_config.read_text()

        self.assertIn("SECTOR_PALETTE", config_content)
        self.assertIn("Banken", config_content)
        self.assertIn("Energie", config_content)

    def test_anomaly_mappings_defined(self):
        """Test that anomaly mappings are defined in frontend"""
        frontend_config = Path(__file__).parent.parent / "frontend" / "config.py"
        config_content = frontend_config.read_text()

        self.assertIn("ANOMALY_LABELS", config_content)
        self.assertIn("ANOMALY_COLORS", config_content)
        self.assertIn("SEVERITY_TIERS", config_content)


class TestDataLoadingLogic(unittest.TestCase):
    """Test that data loading logic is present"""

    def test_load_data_function_exists(self):
        """Test that load_data function is defined in frontend module"""
        data_client = Path(__file__).parent.parent / "frontend" / "data_client.py"
        self.assertTrue(data_client.exists(), "frontend/data_client.py must exist")

        content = data_client.read_text()
        self.assertIn("def load_data", content)
        self.assertIn("@st.cache_data", content)

    def test_data_path_references_correct_location(self):
        """Test that data path points to correct location"""
        data_client = Path(__file__).parent.parent / "frontend" / "data_client.py"
        content = data_client.read_text()

        # Check that it references data/daily_metrics.parquet
        self.assertIn("daily_metrics.parquet", content)


class TestChartFunctions(unittest.TestCase):
    """Test that chart generation functions exist"""

    def test_chart_functions_defined(self):
        """Test that chart generation functions are defined in frontend"""
        charts_module = Path(__file__).parent.parent / "frontend" / "charts.py"
        self.assertTrue(charts_module.exists(), "frontend/charts.py must exist")

        content = charts_module.read_text()

        # Check for various chart functions
        chart_patterns = [
            r"def.*chart.*\(",
            r"def.*_base_layout",
            r"plotly",
        ]

        for pattern in chart_patterns:
            matches = re.search(pattern, content, re.IGNORECASE)
            self.assertIsNotNone(matches, f"Pattern '{pattern}' not found in charts.py")


class TestFormattingFunctions(unittest.TestCase):
    """Test that formatting functions exist"""

    def test_formatting_functions_defined(self):
        """Test that formatting helper functions are defined in frontend"""
        utils_module = Path(__file__).parent.parent / "frontend" / "utils.py"
        self.assertTrue(utils_module.exists(), "frontend/utils.py must exist")

        content = utils_module.read_text()

        # Check for formatting functions
        self.assertIn("def fmt_chf", content)
        self.assertIn("def fmt_pct", content)
        self.assertIn("def score_badge", content)


class TestCSSInjection(unittest.TestCase):
    """Test that CSS styling is present"""

    def test_inject_css_function_exists(self):
        """Test that CSS injection function exists in frontend"""
        styling_module = Path(__file__).parent.parent / "frontend" / "styling.py"
        self.assertTrue(styling_module.exists(), "frontend/styling.py must exist")

        content = styling_module.read_text()
        self.assertIn("def inject_css", content)
        self.assertIn("<style>", content)

    def test_css_contains_brand_styling(self):
        """Test that CSS contains brand styling"""
        styling_module = Path(__file__).parent.parent / "frontend" / "styling.py"
        content = styling_module.read_text()

        # Check for key CSS classes
        self.assertIn("otcx-header", content)
        self.assertIn("kpi", content)


class TestPathResolution(unittest.TestCase):
    """Test that path resolution works correctly"""

    def test_path_uses_pathlib(self):
        """Test that modules use pathlib for path resolution"""
        data_client = Path(__file__).parent.parent / "frontend" / "data_client.py"
        content = data_client.read_text()

        self.assertIn("from pathlib import Path", content)
        self.assertIn("Path(__file__)", content)

    def test_data_files_accessible(self):
        """Test that data files can be accessed"""
        # Updated to check backend/data/ directory
        data_dir = Path(__file__).parent.parent / "backend" / "data"
        self.assertTrue(data_dir.exists())

        # Check for essential data files
        self.assertTrue((data_dir / "daily_metrics.parquet").exists())
        self.assertTrue((data_dir / "master_trades.parquet").exists())
        self.assertTrue((data_dir / "securities.csv").exists())


if __name__ == "__main__":
    unittest.main()

