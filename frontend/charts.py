"""
OTC-X Chart Generation Module
Plotly chart factory functions for market analytics visualizations

NOTE: This module is a transitional stub that re-exports functions from app.py
      Complete extraction of ~800 lines of chart code is documented in COMPLETION_ROADMAP.md
      All chart functions will be moved here to complete Phase 3 modularization.
"""

import pandas as pd
import plotly.graph_objects as go
from .config import BRAND_RED, PLOTLY_TPL, MUTED, SECTOR_PALETTE, SEVERITY_TIERS
from .styling import hex_to_rgba


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* so nested dicts are merged
    rather than replaced (prevents axis tickfont/title_font color loss)."""
    merged = base.copy()
    for k, v in override.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def _base_layout(**kwargs) -> dict:
    """
    Create base Plotly layout with consistent styling.

    Applies Swiss institutional banking theme colors and fonts.
    Preserves axis settings when partial overrides are provided.
    """
    _axis_defaults = dict(
        color="#1A1A2E",
        tickfont=dict(color="#1A1A2E"),
        title_font=dict(color="#1A1A2E"),
    )
    # Preserve axis contrast defaults even when callers pass partial axis dicts
    for axis_key in ("xaxis", "yaxis", "xaxis2", "yaxis2"):
        if axis_key in kwargs and isinstance(kwargs[axis_key], dict):
            kwargs[axis_key] = _deep_merge(_axis_defaults, kwargs[axis_key])

    base = dict(
        template=PLOTLY_TPL,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Inter", color="#1A1A2E"),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#CED4DA",
            font=dict(color="#1A1A2E"),
        ),
        margin=dict(l=4, r=4, t=16, b=4),
        xaxis=_axis_defaults.copy(),
        yaxis=_axis_defaults.copy(),
    )
    base.update(kwargs)
    return base


# TODO: Extract remaining chart functions from app.py
# The following functions need to be moved here (see COMPLETION_ROADMAP.md):
#
# - chart_market_activity(df_hist) -> go.Figure
# - chart_sector_treemap(latest) -> go.Figure
# - chart_top_movers(latest, n=14) -> go.Figure
# - chart_volume_by_sector(latest) -> go.Figure
# - chart_scatter_volume_price(latest) -> go.Figure
# - chart_amihud_by_sector(df_hist) -> go.Figure
# - chart_volatility_trend(df_hist, n=5, mode="SMA") -> go.Figure
# - chart_correlation_heatmap(df, selected_cols=None) -> go.Figure
# - chart_anomaly_severity_treemap(latest) -> go.Figure
# - chart_security_history(df_hist, isin) -> go.Figure
# - chart_3d_explorer(latest, x_col, y_col, z_col, color_col, size_col) -> go.Figure
#
# Total: ~800 lines to extract from app.py lines 642-1285
