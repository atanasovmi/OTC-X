"""
OTC-X Frontend Utilities
Formatting functions and helper utilities for the dashboard
"""

import pandas as pd
from .config import ANOMALY_LABELS


def fmt_chf(v) -> str:
    """Format value as Swiss Francs with thousands separator."""
    if pd.isna(v):
        return "—"
    try:
        v = float(v)
        if abs(v) >= 1_000_000:
            return f"CHF {v / 1_000_000:.2f}M"
        if abs(v) >= 1_000:
            return f"CHF {v:,.0f}".replace(",", "'")
        return f"CHF {v:,.2f}"
    except (ValueError, TypeError):
        return "—"


def fmt_num(v, dec: int = 0, suffix: str = "") -> str:
    """Format number with thousands separator and optional suffix."""
    if pd.isna(v):
        return "—"
    try:
        v = float(v)
        if abs(v) >= 1_000_000:
            return f"{v / 1_000_000:.1f}M{suffix}"
        if abs(v) >= 1_000:
            return f"{v:,.{dec}f}{suffix}".replace(",", "'")
        return f"{v:.{dec}f}{suffix}"
    except (ValueError, TypeError):
        return "—"


def fmt_pct(v, dec: int = 2) -> str:
    """Format value as percentage with sign."""
    if pd.isna(v):
        return "—"
    try:
        sign = "+" if float(v) >= 0 else ""
        return f"{sign}{float(v):.{dec}f}%"
    except (ValueError, TypeError):
        return "—"


def pct_cls(v) -> str:
    """Return CSS class ('pos' or 'neg') based on value sign."""
    try:
        return "pos" if float(v) >= 0 else "neg"
    except Exception:
        return ""


def score_badge(score: int) -> str:
    """Generate HTML badge for anomaly score."""
    label = ANOMALY_LABELS.get(int(score), "Critical")
    if score == 0:
        css_class = "bdg-clean"
    elif score == 1:
        css_class = "bdg-watch"
    elif score == 2:
        css_class = "bdg-alert"
    elif score in (3, 4):
        css_class = "bdg-critical"
    elif score in (5, 6):
        css_class = "bdg-severe"
    else:
        css_class = "bdg-extreme"
    return f'<span class="bdg {css_class}">{label}</span>'


def flag_dot(active: bool) -> str:
    """Return a coloured dot for boolean flag columns."""
    if active:
        return "<span style='color:#B22222;font-size:0.9rem;'>●</span>"
    return "<span style='color:#CED4DA;font-size:0.9rem;'>·</span>"
