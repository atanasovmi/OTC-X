"""Shared formatting helpers and display utilities.

Provides lightweight, NaN-safe formatters for currency (CHF), numbers,
percentages, CSS class selectors, colour conversion, and anomaly-score
badge rendering.  Every public function is designed to accept raw
pandas cell values (which may be ``NaN`` or non-numeric) and return a
safe HTML or plain-text string.
"""

import pandas as pd

from frontend.operations.config import ANOMALY_LABELS


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert a ``#RRGGBB`` hex colour string to a CSS ``rgba(...)`` value.

    Parameters
    ----------
    hex_color : str
        Six-digit hex colour string, e.g. ``"#B22222"``.
    alpha : float, optional
        Opacity component in the range ``[0.0, 1.0]`` (default ``1.0``).

    Returns
    -------
    str
        CSS-ready ``rgba(r, g, b, a)`` string.
    """
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i: i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def fmt_chf(v: object) -> str:
    """Format a numeric value as a Swiss-franc currency string.

    Applies adaptive formatting: values ≥ 1 M display as ``CHF 1.23M``,
    values ≥ 1 000 use apostrophe-separated thousands, and smaller values
    show two decimal places.

    Parameters
    ----------
    v : object
        Numeric value (or ``NaN`` / non-numeric).

    Returns
    -------
    str
        Formatted ``"CHF …"`` string, or ``"—"`` for missing / invalid data.
    """
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


def fmt_num(v: object, dec: int = 0, suffix: str = "") -> str:
    """Format a numeric value with adaptive thousands / millions scaling.

    Parameters
    ----------
    v : object
        Numeric value (or ``NaN`` / non-numeric).
    dec : int, optional
        Decimal places for values below 1 M (default ``0``).
    suffix : str, optional
        Literal suffix appended after the number (e.g. ``"%"``).

    Returns
    -------
    str
        Human-readable number string with apostrophe-separated thousands,
        or ``"—"`` for missing / invalid data.
    """
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


def fmt_pct(v: object, dec: int = 2) -> str:
    """Format a numeric value as a signed percentage string.

    Parameters
    ----------
    v : object
        Numeric value (or ``NaN`` / non-numeric).
    dec : int, optional
        Decimal places (default ``2``).

    Returns
    -------
    str
        Percentage string with explicit ``+`` / ``-`` sign, e.g.
        ``"+1.23%"`` or ``"-0.50%"``, or ``"—"`` for invalid data.
    """
    if pd.isna(v):
        return "—"
    try:
        sign = "+" if float(v) >= 0 else ""
        return f"{sign}{float(v):.{dec}f}%"
    except (ValueError, TypeError):
        return "—"


def pct_cls(v: object) -> str:
    """Return a CSS class name indicating positive or negative direction.

    Parameters
    ----------
    v : object
        Numeric value (or anything coercible to ``float``).

    Returns
    -------
    str
        ``"pos"`` if *v* ≥ 0, ``"neg"`` if *v* < 0, or ``""`` on error.
    """
    try:
        return "pos" if float(v) >= 0 else "neg"
    except Exception:
        return ""


def score_badge(score: int) -> str:
    """Return an HTML ``<span>`` badge for the given anomaly score.

    The badge label and CSS class are derived from the shared
    ``ANOMALY_LABELS`` mapping in ``config.py``.

    Parameters
    ----------
    score : int
        Composite anomaly score (typically 0–7).

    Returns
    -------
    str
        HTML ``<span class="bdg bdg-{tier}">Label</span>`` string.
    """
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
