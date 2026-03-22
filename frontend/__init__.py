"""
OTC-X Frontend Package
Modular Streamlit dashboard components
"""

# Re-export commonly used items for convenient importing
from .config import (
    BRAND_RED, BRAND_DARK, GREEN_POS, RED_NEG, BORDER_COL, MUTED, PLOTLY_TPL,
    SECTOR_PALETTE, ANOMALY_LABELS, ANOMALY_COLORS, SEVERITY_TIERS,
    PAGE_CONFIG
)
from .styling import inject_css, hex_to_rgba
from .utils import fmt_chf, fmt_num, fmt_pct, pct_cls, score_badge, flag_dot
from .data_client import load_data
from .charts import (
    chart_market_activity, chart_sector_treemap, chart_top_movers,
    chart_volume_by_sector, chart_scatter_volume_price, chart_amihud_by_sector,
    chart_volatility_trend, chart_correlation_heatmap, chart_anomaly_severity_treemap,
    chart_security_history, chart_3d_explorer
)
from .components import (
    render_header, render_kpis, render_market_table, render_native_dataframe
)

__all__ = [
    # Config
    "BRAND_RED", "BRAND_DARK", "GREEN_POS", "RED_NEG", "BORDER_COL", "MUTED", "PLOTLY_TPL",
    "SECTOR_PALETTE", "ANOMALY_LABELS", "ANOMALY_COLORS", "SEVERITY_TIERS",
    "PAGE_CONFIG",
    # Styling
    "inject_css", "hex_to_rgba",
    # Utils
    "fmt_chf", "fmt_num", "fmt_pct", "pct_cls", "score_badge", "flag_dot",
    # Data
    "load_data",
    # Charts
    "chart_market_activity", "chart_sector_treemap", "chart_top_movers",
    "chart_volume_by_sector", "chart_scatter_volume_price", "chart_amihud_by_sector",
    "chart_volatility_trend", "chart_correlation_heatmap", "chart_anomaly_severity_treemap",
    "chart_security_history", "chart_3d_explorer",
    # Components
    "render_header", "render_kpis", "render_market_table", "render_native_dataframe",
]
