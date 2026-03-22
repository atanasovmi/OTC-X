"""
OTC-X UI Components Module
Reusable Streamlit UI rendering components

NOTE: This module is a transitional stub. Complete extraction documented in COMPLETION_ROADMAP.md
      All render functions will be moved here to complete Phase 3 modularization.
"""

import streamlit as st
import pandas as pd
from .config import SEVERITY_TIERS, ANOMALY_LABELS
from .utils import fmt_chf, fmt_num, fmt_pct, pct_cls, score_badge, flag_dot


# TODO: Extract rendering components from app.py
# The following functions need to be moved here (see COMPLETION_ROADMAP.md):
#
# - render_header(latest_date: str) -> None
#     * Renders OTC-X logo, tagline, and live data indicator
#     * Location: app.py line 1287-1305
#
# - render_kpis(latest: pd.DataFrame) -> None
#     * Renders Risk Summary KPI cards with tier colors
#     * 5 cards: Clean, Alert, Critical, Severe, Extreme
#     * Location: app.py line 1307-1347
#
# - render_market_table(df: pd.DataFrame, n: int = 50) -> None
#     * Renders compact market overview table
#     * Custom HTML with mkt-table CSS class
#     * Location: app.py line 1349-1396
#
# - render_native_dataframe(df: pd.DataFrame, n: int = 50) -> None
#     * Renders full market data table with all 26 columns
#     * Custom formatters for ISIN links, CHF, percentages, scores, flags
#     * Location: app.py line 1405-1530
#
# Total: ~350 lines to extract from app.py lines 1287-1530
