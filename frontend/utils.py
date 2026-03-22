import pandas as pd

from frontend.config import ANOMALY_LABELS


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert a #RRGGBB hex string to an rgba(...) CSS value."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i: i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def fmt_chf(v) -> str:
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
    if pd.isna(v):
        return "—"
    try:
        sign = "+" if float(v) >= 0 else ""
        return f"{sign}{float(v):.{dec}f}%"
    except (ValueError, TypeError):
        return "—"


def pct_cls(v) -> str:
    try:
        return "pos" if float(v) >= 0 else "neg"
    except Exception:
        return ""


def score_badge(score: int) -> str:
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
