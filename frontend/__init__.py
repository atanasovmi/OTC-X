"""
OTC-X Frontend Package
Modular Streamlit dashboard components
"""

# Re-export commonly used items for convenient importing
from .config import (
    BRAND_RED, BRAND_DARK, GREEN_POS, RED_NEG,
    SECTOR_PALETTE, ANOMALY_LABELS, ANOMALY_COLORS, SEVERITY_TIERS,
    PAGE_CONFIG
)
from .styling import inject_css, hex_to_rgba
from .utils import fmt_chf, fmt_num, fmt_pct, pct_cls, score_badge, flag_dot
from .data_client import load_data

__all__ = [
    # Config
    "BRAND_RED", "BRAND_DARK", "GREEN_POS", "RED_NEG",
    "SECTOR_PALETTE", "ANOMALY_LABELS", "ANOMALY_COLORS", "SEVERITY_TIERS",
    "PAGE_CONFIG",
    # Styling
    "inject_css", "hex_to_rgba",
    # Utils
    "fmt_chf", "fmt_num", "fmt_pct", "pct_cls", "score_badge", "flag_dot",
    # Data
    "load_data",
]
