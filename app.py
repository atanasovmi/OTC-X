"""
OTC-X Market Intelligence Dashboard
Professional Swiss OTC market analytics platform
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path

# ─────────────────────────────────────────────
#  Page Configuration
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="OTC-X Market Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
#  Brand Constants
# ─────────────────────────────────────────────
BRAND_RED    = "#B22222"
BRAND_DARK   = "#1A1A2E"
GREEN_POS    = "#28A745"
RED_NEG      = "#DC3545"
BORDER_COL   = "#DEE2E6"
MUTED        = "#495057"   # darkened from #6C757D for readability on white
PLOTLY_TPL   = "plotly_white"

SECTOR_PALETTE = {
    "Banken":                         "#B22222",
    "Energie":                        "#F28B00",
    "Immobilien":                     "#2E86AB",
    "Industrie":                      "#5C6BC0",
    "Bergbahnen":                     "#43A047",
    "Beteiligungsgesellschaften":     "#AB47BC",
    "Nahrungsmittel und Getraenke":   "#00ACC1",
    "Tourismus,Freizeit,Sonstiges":   "#FF7043",
    "Transport,Verkehr,Logistik":     "#8D6E63",
    "Medien":                         "#78909C",
}

# Shared anomaly score labels and colours (used in badge helper and distribution chart)
ANOMALY_LABELS: dict[int, str] = {
    0: "Clean", 1: "Watch", 2: "Alert", 3: "Critical",
    4: "Critical", 5: "Severe", 6: "Severe", 7: "Extreme",
}
ANOMALY_COLORS: dict[int, str] = {
    0: "#28A745", 1: "#FFC107", 2: "#FD7E14",
    3: "#DC3545", 4: "#DC3545", 5: "#7D1128",
    6: "#7D1128", 7: "#4A0010",
}
TIER_SCORES: dict[str, list[int]] = {
    "clean":    [0],
    "alert":    [1, 2],
    "critical": [3, 4],
    "severe":   [5, 6],
    "extreme":  [7, 8, 9, 10],
}


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert a #RRGGBB hex string to an rgba(...) CSS value."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i: i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


# ─────────────────────────────────────────────
#  CSS – Professional Banking Theme
# ─────────────────────────────────────────────
def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #212529;
        }
        .stApp { background-color: #F8F9FA; }

        /* ── Header ── */
        .otcx-header {
            background: #FFFFFF;
            border-bottom: 3px solid #B22222;
            padding: 0.9rem 2rem;
            margin: -1rem -1rem 1.5rem -1rem;
            display: flex;
            align-items: center;
        }
        .otcx-logo {
            font-size: 1.8rem;
            font-weight: 700;
            color: #1A1A2E;
            letter-spacing: -0.04em;
            line-height: 1;
        }
        .otcx-logo span { color: #B22222; }
        .otcx-tagline {
            font-size: 0.65rem;
            color: #495057;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-top: 0.15rem;
        }

        /* ── Section Headers ── */
        .sec-hdr {
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: #1A1A2E;
            border-bottom: 1px solid #DEE2E6;
            padding-bottom: 0.45rem;
            margin-bottom: 0.8rem;
        }

        /* ── Metric Cards ── */
        .kpi-card {
            background: #FFFFFF;
            border: 1px solid #DEE2E6;
            border-top: 3px solid #B22222;
            padding: 1.1rem 1.3rem;
            height: 100%;
        }
        .kpi-label {
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #495057;
            margin-bottom: 0.35rem;
        }
        .kpi-value {
            font-size: 1.65rem;
            font-weight: 700;
            color: #1A1A2E;
            line-height: 1;
            margin-bottom: 0.2rem;
            font-family: 'IBM Plex Mono', monospace;
        }
        .kpi-sub { font-size: 0.72rem; color: #495057; }
        .c-pos { color: #28A745; font-weight: 600; }
        .c-neg { color: #DC3545; font-weight: 600; }

        /* ── Market Table ── */
        .mkt-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
        }
        .mkt-table th {
            font-size: 0.62rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            color: #495057;
            border-bottom: 2px solid #DEE2E6;
            padding: 0.55rem 0.7rem;
            text-align: right;
            white-space: nowrap;
        }
        .mkt-table th.left { text-align: left; }
        .mkt-table td {
            padding: 0.55rem 0.7rem;
            border-bottom: 1px solid #F1F3F5;
            text-align: right;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.8rem;
            white-space: nowrap;
        }
        .mkt-table td.left {
            text-align: left;
            font-family: 'Inter', sans-serif;
        }
        .mkt-table td.isin {
            color: #B22222;
            font-weight: 500;
            font-family: 'IBM Plex Mono', monospace;
        }
        .mkt-table td.name {
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            max-width: 180px;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .mkt-table tr:hover { background: #F8F9FA; }
        .pos { color: #28A745 !important; }
        .neg { color: #DC3545 !important; }

        /* ── Badges ── */
        .bdg {
            display: inline-block;
            padding: 0.12rem 0.45rem;
            font-size: 0.6rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            border-radius: 2px;
        }
        .bdg-clean    { background: #D4EDDA; color: #155724; }
        .bdg-watch    { background: #FFF3CD; color: #856404; }
        .bdg-alert    { background: #FFE0CC; color: #7D3C00; }
        .bdg-critical { background: #F8D7DA; color: #721C24; }

        /* ── Severity Filter Toggle Group ── */
        /* Collapse gaps between the five Show toggle columns */
        .stHorizontalBlock:has(.st-key-show_clean) {
            gap: 0 !important;
        }
        .st-key-show_clean,
        .st-key-show_alert,
        .st-key-show_critical,
        .st-key-show_severe,
        .st-key-show_extreme {
            padding: 0 !important;
        }
        .st-key-show_clean .stCheckbox,
        .st-key-show_alert .stCheckbox,
        .st-key-show_critical .stCheckbox,
        .st-key-show_severe .stCheckbox,
        .st-key-show_extreme .stCheckbox {
            margin: 0 !important;
        }
        /* Make checkbox labels look like connected toggle buttons */
        .st-key-show_clean [data-baseweb="checkbox"],
        .st-key-show_alert [data-baseweb="checkbox"],
        .st-key-show_critical [data-baseweb="checkbox"],
        .st-key-show_severe [data-baseweb="checkbox"],
        .st-key-show_extreme [data-baseweb="checkbox"] {
            background: rgb(235, 226, 205);
            border: 1px solid #DEE2E6;
            border-right: none;
            padding: 0.45rem 0.9rem;
            margin: 0;
            cursor: pointer;
            transition: background 0.15s, color 0.15s;
        }
        .st-key-show_clean [data-baseweb="checkbox"] {
            border-radius: 6px 0 0 6px;
        }
        .st-key-show_extreme [data-baseweb="checkbox"] {
            border-radius: 0 6px 6px 0;
            border-right: 1px solid #DEE2E6;
        }
        /* Label text styling */
        .st-key-show_clean [data-baseweb="checkbox"] p,
        .st-key-show_alert [data-baseweb="checkbox"] p,
        .st-key-show_critical [data-baseweb="checkbox"] p,
        .st-key-show_severe [data-baseweb="checkbox"] p,
        .st-key-show_extreme [data-baseweb="checkbox"] p {
            font-size: 0.72rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.04em;
            color: #1A1A2E !important;
            white-space: nowrap;
        }
        /* Active (checked) state — coloured background per tier */
        .st-key-show_clean [data-baseweb="checkbox"][aria-checked="true"]    { background: #28A745; border-color: #28A745; }
        .st-key-show_alert [data-baseweb="checkbox"][aria-checked="true"]    { background: #FD7E14; border-color: #FD7E14; }
        .st-key-show_critical [data-baseweb="checkbox"][aria-checked="true"] { background: #DC3545; border-color: #DC3545; }
        .st-key-show_severe [data-baseweb="checkbox"][aria-checked="true"]   { background: #7D1128; border-color: #7D1128; }
        .st-key-show_extreme [data-baseweb="checkbox"][aria-checked="true"]  { background: #4A0010; border-color: #4A0010; }
        .st-key-show_clean [data-baseweb="checkbox"][aria-checked="true"] p,
        .st-key-show_alert [data-baseweb="checkbox"][aria-checked="true"] p,
        .st-key-show_critical [data-baseweb="checkbox"][aria-checked="true"] p,
        .st-key-show_severe [data-baseweb="checkbox"][aria-checked="true"] p,
        .st-key-show_extreme [data-baseweb="checkbox"][aria-checked="true"] p {
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }
        /* Hide the default checkbox square */
        .st-key-show_clean [data-baseweb="checkbox"] > span:first-child,
        .st-key-show_alert [data-baseweb="checkbox"] > span:first-child,
        .st-key-show_critical [data-baseweb="checkbox"] > span:first-child,
        .st-key-show_severe [data-baseweb="checkbox"] > span:first-child,
        .st-key-show_extreme [data-baseweb="checkbox"] > span:first-child {
            display: none;
        }

        /* ── Tabs ── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0;
            background: #FFFFFF;
            border-bottom: 2px solid #DEE2E6;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 0.7rem 1.4rem;
            font-size: 0.82rem;
            font-weight: 500;
            letter-spacing: 0.02em;
            color: #495057;
            border-radius: 0;
            background: transparent;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
        }
        .stTabs [aria-selected="true"] {
            color: #B22222 !important;
            border-bottom: 2px solid #B22222 !important;
            background: transparent !important;
        }

        /* ── Sidebar ── */
        section[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #DEE2E6; }

        /* ── Live dot ── */
        .live-dot {
            display: inline-flex; align-items: center; gap: 0.4rem;
            font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.1em; color: #28A745;
        }
        .dot {
            width: 6px; height: 6px; border-radius: 50%;
            background: #28A745; animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.35; }
        }

        /* ── Misc ── */
        #MainMenu, footer, header { visibility: hidden; }
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }

        /* ── Dropdown / Selectbox overrides ── */
        /* Dropdown popup/menu background → warm beige */
        [data-baseweb="popover"] {
            background-color: rgb(235, 226, 205) !important;
            border: 1px solid #DEE2E6 !important;
        }
        [data-baseweb="menu"] {
            background-color: rgb(235, 226, 205) !important;
        }
        [data-baseweb="menu"] li:hover,
        [data-baseweb="menu"] li[aria-selected="true"] {
            background-color: rgba(178, 34, 34, 0.08) !important;
        }

        /* Dropdown arrow → black so it's visible on beige/light bg */
        [data-baseweb="select"] svg {
            fill: #1A1A2E !important;
            color: #1A1A2E !important;
        }

        /* Selectbox control background → beige to match dropdown */
        [data-baseweb="select"] > div {
            background-color: rgb(235, 226, 205) !important;
            border-color: #DEE2E6 !important;
            color: #1A1A2E !important;
        }
        [data-baseweb="select"] input {
            color: #1A1A2E !important;
        }
        /* Text input field background */
        .stTextInput > div > div {
            background-color: rgb(235, 226, 205) !important;
            border-color: #DEE2E6 !important;
            color: #1A1A2E !important;
        }
        .stTextInput input {
            color: #1A1A2E !important;
        }
        .stTextInput input::placeholder {
            color: #495057 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
#  Utility — Number Formatting
# ─────────────────────────────────────────────
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
    if score == 0:
        return '<span class="bdg bdg-clean">Clean</span>'
    if score == 1:
        return '<span class="bdg bdg-watch">Watch</span>'
    if score == 2:
        return '<span class="bdg bdg-alert">Alert</span>'
    return '<span class="bdg bdg-critical">Critical</span>'


# ─────────────────────────────────────────────
#  Data Loading
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    path = Path(__file__).parent / "data" / "daily_metrics.parquet"
    if not path.exists():
        return pd.DataFrame(), pd.DataFrame()

    df = pd.read_parquet(path)
    df["Datum"] = pd.to_datetime(df["Datum"])

    latest = df.sort_values("Datum").groupby("Isin", as_index=False).last()
    return df, latest


# ─────────────────────────────────────────────
#  Chart Factory
# ─────────────────────────────────────────────
def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* so nested dicts are merged,
    not replaced.  Returns a new dict; originals are untouched."""
    merged = base.copy()
    for k, v in override.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def _base_layout(**kwargs) -> dict:
    _axis_defaults = dict(
        tickfont=dict(color="#212529"),
        title_font=dict(color="#212529"),
    )
    base = dict(
        template=PLOTLY_TPL,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Inter", color="#212529"),
        margin=dict(l=4, r=4, t=16, b=4),
        xaxis=_axis_defaults.copy(),
        yaxis=_axis_defaults.copy(),
    )
    # Deep-merge so that caller-supplied xaxis / yaxis dicts are merged with
    # the dark-text defaults instead of replacing them.
    for axis_key in ("xaxis", "yaxis", "xaxis2", "yaxis2"):
        if axis_key in kwargs:
            kwargs[axis_key] = _deep_merge(_axis_defaults, kwargs[axis_key])
    base.update(kwargs)
    return base


def chart_market_activity(df_hist: pd.DataFrame) -> go.Figure:
    daily = (
        df_hist.groupby("Datum")
        .agg(vol=("volume_today_chf", "sum"), trades=("trades_today", "sum"))
        .reset_index()
        .sort_values("Datum")
        .tail(90)
    )
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=daily["Datum"],
            y=daily["vol"],
            name="Volume (CHF)",
            marker_color="rgba(178,34,34,0.72)",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=daily["Datum"],
            y=daily["trades"],
            name="Trades",
            mode="lines",
            line=dict(color=BRAND_DARK, width=1.5),
        ),
        secondary_y=True,
    )
    fig.update_layout(**_base_layout(height=280, bargap=0.12,
                                      legend=dict(orientation="h", y=1.08,
                                                  font=dict(size=10, color="#212529"))))
    fig.update_xaxes(gridcolor="#F1F3F5", tickfont=dict(color="#212529"))
    fig.update_yaxes(title_text="Volume (CHF)", gridcolor="#F1F3F5",
                     secondary_y=False, tickformat=",.0f",
                     tickfont=dict(color="#212529"))
    fig.update_yaxes(title_text="Trades", showgrid=False, secondary_y=True,
                     tickfont=dict(color="#212529"))
    return fig


def chart_sector_treemap(latest: pd.DataFrame) -> go.Figure:
    g = (
        latest.groupby("Sektor", as_index=False)
        .agg(
            vol=("volume_today_chf", "sum"),
            n=("Isin", "count"),
            avg_chg=("price_change_pct", "mean"),
        )
        .sort_values("vol", ascending=False)
    )
    fig = px.treemap(
        g,
        path=["Sektor"],
        values="vol",
        color="avg_chg",
        color_continuous_scale=["#DC3545", "#F8F9FA", "#28A745"],
        color_continuous_midpoint=0,
        custom_data=["n", "avg_chg", "vol"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[2]:,.0f} CHF<br>%{customdata[0]} sec.",
        textfont=dict(family="Inter", size=11),
        marker_line_width=2,
        marker_line_color="white",
    )
    fig.update_layout(
        **_base_layout(height=280,
                       coloraxis_colorbar=dict(title="Avg Δ%", thickness=10))
    )
    return fig


def chart_top_movers(latest: pd.DataFrame, n: int = 14) -> go.Figure:
    df = latest[latest["price_change_pct"] != 0].copy()
    if df.empty:
        return go.Figure()
    top_g = df.nlargest(n // 2, "price_change_pct")
    top_l = df.nsmallest(n // 2, "price_change_pct")
    df = pd.concat([top_g, top_l]).sort_values("price_change_pct")
    colors = [GREEN_POS if v >= 0 else RED_NEG for v in df["price_change_pct"]]
    labels = df["Name"].fillna(df["Isin"]).str[:32]
    fig = go.Figure(
        go.Bar(
            x=df["price_change_pct"],
            y=labels,
            orientation="h",
            marker_color=colors,
            marker_opacity=0.88,
            text=[fmt_pct(v) for v in df["price_change_pct"]],
            textposition="outside",
            textfont=dict(family="IBM Plex Mono", size=10),
        )
    )
    fig.add_vline(x=0, line_color=BORDER_COL, line_width=1)
    fig.update_layout(
        **_base_layout(height=420,
                       margin=dict(l=10, r=70, t=16, b=4),
                       xaxis=dict(title="Price Change (%)", tickformat="+.1f",
                                  ticksuffix="%", gridcolor="#F1F3F5", zeroline=False,
                                  tickfont=dict(color="#212529")),
                       yaxis=dict(title=None, tickfont=dict(size=11, color="#212529")),
                       showlegend=False)
    )
    return fig


def chart_volume_by_sector(latest: pd.DataFrame) -> go.Figure:
    s = (
        latest.groupby("Sektor")["volume_today_chf"]
        .sum()
        .sort_values()
    )
    fig = go.Figure(
        go.Bar(
            x=s.values,
            y=s.index,
            orientation="h",
            marker_color=BRAND_RED,
            marker_opacity=0.82,
            text=[fmt_chf(v) for v in s.values],
            textposition="outside",
            textfont=dict(family="IBM Plex Mono", size=10),
        )
    )
    fig.update_layout(
        **_base_layout(height=320, margin=dict(l=4, r=90, t=16, b=4),
                       xaxis=dict(title=None, gridcolor="#F1F3F5", zeroline=False),
                       yaxis=dict(title=None, tickfont=dict(size=11)),
                       showlegend=False)
    )
    return fig


def chart_scatter_volume_price(latest: pd.DataFrame) -> go.Figure:
    """Volume vs Price-Change scatter — log-scaled X, per-sector colour.

    Outliers clipped to 1st–99th percentile to avoid crowding.
    Zero-volume rows excluded from log axis.
    """
    df = latest[latest["volume_today_chf"] > 0].copy()
    if df.empty:
        return go.Figure()

    # Clip extreme outliers
    lo_v, hi_v = df["volume_today_chf"].quantile([0.01, 0.99])
    lo_p, hi_p = df["price_change_pct"].quantile([0.005, 0.995])
    df = df[
        df["volume_today_chf"].between(lo_v, hi_v)
        & df["price_change_pct"].between(lo_p, hi_p)
    ].copy()

    df["label"] = df["Name"].fillna(df["Isin"])
    df["sector"] = df["Sektor"].fillna("Other")

    fig = go.Figure()
    for sector, grp in df.groupby("sector"):
        fig.add_trace(
            go.Scatter(
                x=grp["volume_today_chf"],
                y=grp["price_change_pct"],
                mode="markers",
                name=sector,
                marker=dict(
                    size=8,
                    color=SECTOR_PALETTE.get(sector, MUTED),
                    opacity=0.78,
                    line=dict(width=0.5, color="white"),
                ),
                text=grp["label"],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Volume: CHF %{x:,.0f}<br>"
                    "Price Δ: %{y:+.2f}%<extra></extra>"
                ),
            )
        )

    fig.add_hline(y=0, line_color=BORDER_COL, line_dash="dot", line_width=1)
    fig.update_layout(
        **_base_layout(
            height=390,
            xaxis=dict(
                title="Daily Volume (CHF) — log scale",
                type="log",
                gridcolor="#F1F3F5",
                tickformat=",.0f",
            ),
            yaxis=dict(
                title="Price Change (%)",
                ticksuffix="%",
                gridcolor="#F1F3F5",
                zeroline=False,
            ),
            legend=dict(
                orientation="v",
                x=1.01,
                y=1,
                font=dict(size=10, color="#212529"),
                title=dict(text="Sector", font=dict(size=10, color="#212529")),
            ),
        )
    )
    return fig


def chart_amihud_by_sector(df_hist: pd.DataFrame) -> go.Figure:
    """Box-plot of Amihud illiquidity per sector (95th pct cutoff)."""
    df = df_hist[df_hist["amihud_daily"] > 0].copy()
    cap = df["amihud_daily"].quantile(0.95)
    df = df[df["amihud_daily"] <= cap]

    order = (
        df.groupby("Sektor")["amihud_daily"]
        .median()
        .sort_values()
        .index.tolist()
    )

    fig = go.Figure()
    for sector in order:
        vals = df[df["Sektor"] == sector]["amihud_daily"]
        sector_color = SECTOR_PALETTE.get(sector, MUTED)
        fig.add_trace(
            go.Box(
                y=vals,
                name=sector,
                marker_color=sector_color,
                line_color=sector_color,
                fillcolor=_hex_to_rgba(sector_color, 0.12),
                boxmean="sd",
                showlegend=False,
            )
        )
    fig.update_layout(
        **_base_layout(
            height=390,
            margin=dict(l=4, r=4, t=16, b=70),
            yaxis=dict(title="Amihud Illiquidity Ratio", gridcolor="#F1F3F5"),
            xaxis=dict(tickangle=-30, tickfont=dict(size=10)),
        )
    )
    return fig


def chart_volatility_trend(df_hist: pd.DataFrame, n: int = 5) -> go.Figure:
    top_sectors = (
        df_hist.groupby("Sektor")["trades_today"]
        .sum()
        .nlargest(n)
        .index.tolist()
    )
    df = df_hist[df_hist["Sektor"].isin(top_sectors)].copy()
    agg = df.groupby(["Datum", "Sektor"])["volatility_daily"].mean().reset_index()
    agg = agg.sort_values("Datum")

    palette = px.colors.qualitative.D3

    fig = go.Figure()
    for i, sector in enumerate(top_sectors):
        grp = agg[agg["Sektor"] == sector].copy()
        grp["roll"] = grp["volatility_daily"].rolling(30, min_periods=1).mean()
        fig.add_trace(
            go.Scatter(
                x=grp["Datum"],
                y=grp["roll"],
                mode="lines",
                name=sector,
                line=dict(color=palette[i % len(palette)], width=1.5),
                hovertemplate="%{x|%d.%m.%Y}: %{y:.4f}<extra>%{fullData.name}</extra>",
            )
        )
    fig.update_layout(
        **_base_layout(
            height=390,
            xaxis=dict(title=None, gridcolor="#F1F3F5"),
            yaxis=dict(title="Avg Daily Volatility σ", gridcolor="#F1F3F5"),
            legend=dict(orientation="h", y=-0.2, font=dict(size=10, color="#212529")),
        )
    )
    return fig


def chart_correlation_heatmap(latest: pd.DataFrame) -> go.Figure:
    cols = [
        "price_change_pct", "volatility_daily", "amihud_daily",
        "volume_today_chf", "trades_today", "off_book_pct", "anomaly_score",
    ]
    labels = ["Δ Price", "Volatility", "Amihud", "Volume", "Trades", "Off-Book%", "Anomaly"]
    df = latest[cols].dropna()
    corr = df.corr()

    # Lower-triangle only
    mask = np.triu(np.ones(corr.shape, dtype=bool), k=1)
    corr_m = corr.mask(mask)

    z = corr_m.values
    text = [
        [f"{v:.2f}" if not np.isnan(v) else "" for v in row]
        for row in z
    ]

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=labels,
            y=labels,
            colorscale=[
                [0.0, "#2166ac"],
                [0.5, "#f7f7f7"],
                [1.0, "#b2182b"],
            ],
            zmin=-1,
            zmax=1,
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=11, family="IBM Plex Mono"),
            hoverongaps=False,
            colorbar=dict(title="r", thickness=12, len=0.8),
        )
    )
    fig.update_layout(
        **_base_layout(
            height=340,
            xaxis=dict(tickfont=dict(size=11)),
            yaxis=dict(tickfont=dict(size=11), autorange="reversed"),
        )
    )
    return fig


def chart_anomaly_distribution(latest: pd.DataFrame) -> go.Figure:
    vc = latest["anomaly_score"].value_counts().sort_index()
    fig = go.Figure(
        go.Bar(
            x=[ANOMALY_LABELS.get(int(s), str(s)) for s in vc.index],
            y=vc.values,
            marker_color=[ANOMALY_COLORS.get(int(s), MUTED) for s in vc.index],
            text=vc.values,
            textposition="outside",
            textfont=dict(family="IBM Plex Mono", size=11),
        )
    )
    fig.update_layout(
        **_base_layout(
            height=280,
            xaxis=dict(title=None, gridcolor="#F1F3F5"),
            yaxis=dict(title="Securities", gridcolor="#F1F3F5"),
            showlegend=False,
        )
    )
    return fig


def chart_security_history(df_hist: pd.DataFrame, isin: str) -> go.Figure:
    sec = df_hist[df_hist["Isin"] == isin].sort_values("Datum")
    if sec.empty:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.04,
    )

    # Price + volatility band
    upper = sec["price_last"] + sec["volatility_30d_median"]
    lower = sec["price_last"] - sec["volatility_30d_median"]
    fig.add_trace(
        go.Scatter(
            x=pd.concat([sec["Datum"], sec["Datum"][::-1]]),
            y=pd.concat([upper, lower[::-1]]),
            fill="toself",
            fillcolor="rgba(178,34,34,0.07)",
            line=dict(color="rgba(0,0,0,0)"),
            name="±30d σ band",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=sec["Datum"],
            y=sec["price_last"],
            mode="lines",
            name="Last Price",
            line=dict(color=BRAND_RED, width=1.5),
        ),
        row=1, col=1,
    )

    # Volume bars
    fig.add_trace(
        go.Bar(
            x=sec["Datum"],
            y=sec["volume_today_chf"],
            name="Volume (CHF)",
            marker_color="rgba(26,26,46,0.65)",
        ),
        row=2, col=1,
    )

    fig.update_layout(
        **_base_layout(
            height=460,
            legend=dict(orientation="h", y=1.05, font=dict(size=10, color="#212529")),
            xaxis2=dict(title=None, gridcolor="#F1F3F5"),
            yaxis=dict(title="Price (CHF)", gridcolor="#F1F3F5"),
            yaxis2=dict(title="Volume (CHF)", gridcolor="#F1F3F5"),
            bargap=0.08,
        )
    )
    return fig


# ─────────────────────────────────────────────
#  Render Helpers
# ─────────────────────────────────────────────
def render_header(latest_date: str) -> None:
    st.markdown(
        f"""
        <div class="otcx-header">
          <div>
            <div class="otcx-logo">OTC|<span>X</span></div>
            <div class="otcx-tagline">Market Intelligence Platform</div>
          </div>
          <div style="margin-left:auto;display:flex;align-items:center;gap:2rem;">
            <span class="live-dot"><span class="dot"></span> Live</span>
            <span style="font-size:0.72rem;color:#495057;">
              Last data: <strong>{latest_date}</strong>
            </span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(latest: pd.DataFrame) -> None:
    total_vol   = latest["volume_today_chf"].sum()
    total_trades = int(latest["trades_today"].sum())
    active       = int((latest["trades_today"] > 0).sum())
    total_sec    = len(latest)
    vol_spikes   = int(latest["volume_spike"].sum())
    act_spikes   = int(latest["activity_spike"].sum())
    critical     = int((latest["anomaly_score"] >= 3).sum())
    alert        = int((latest["anomaly_score"] == 2).sum())
    watch        = int((latest["anomaly_score"] == 1).sum())
    df_chg       = latest[latest["price_change_pct"] != 0]
    avg_chg      = df_chg["price_change_pct"].mean() if not df_chg.empty else 0.0
    advancing    = int((latest["price_change_pct"] > 0).sum())
    declining    = int((latest["price_change_pct"] < 0).sum())

    c = st.columns(6)
    data = [
        ("Market Volume", fmt_chf(total_vol),
         f"{total_trades:,} trades today"),
        ("Active Securities", str(active),
         f"of {total_sec} listed"),
        ("Avg Price Change",
         f"{'+' if avg_chg >= 0 else ''}{avg_chg:.2f}%",
         f'<span class="c-pos">▲{advancing}</span>&nbsp;adv · '
         f'<span class="c-neg">▼{declining}</span>&nbsp;dec'),
        ("Volume Spikes", str(vol_spikes),
         f"{act_spikes} activity spikes"),
        ("Anomaly Alerts", str(critical + alert),
         f'<span class="bdg bdg-critical">{critical} Critical</span>&nbsp;'
         f'<span class="bdg bdg-alert">{alert} Alert</span>'),
        ("Watch List", str(watch),
         f'<span class="bdg bdg-watch">{watch} Watch</span>'),
    ]
    for col, (label, value, sub) in zip(c, data):
        with col:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value}</div>'
                f'<div class="kpi-sub">{sub}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_market_table(df: pd.DataFrame, n: int = 50) -> None:
    display = df.head(n)
    rows = ""
    for _, r in display.iterrows():
        pct   = r.get("price_change_pct", 0)
        score = int(r.get("anomaly_score", 0))
        date  = r["Datum"].strftime("%d.%m.%Y") if pd.notna(r.get("Datum")) else "—"
        rows += (
            f"<tr>"
            f"<td class='isin'>{r['Isin']}</td>"
            f"<td class='name left'>{str(r.get('Name',''))[:34]}</td>"
            f"<td class='left' style='font-size:0.75rem;color:{MUTED}'>"
            f"{str(r.get('Sektor',''))[:22]}</td>"
            f"<td>{date}</td>"
            f"<td>{fmt_chf(r.get('volume_today_chf', 0))}</td>"
            f"<td>{int(r.get('trades_today', 0))}</td>"
            f"<td class='{pct_cls(pct)}'>{fmt_pct(pct)}</td>"
            f"<td>{r.get('volatility_daily', 0):.4f}</td>"
            f"<td>{score_badge(score)}</td>"
            f"</tr>"
        )
    html = (
        "<div style='overflow-x:auto'>"
        "<table class='mkt-table'>"
        "<thead><tr>"
        "<th class='left'>ISIN</th>"
        "<th class='left'>Security</th>"
        "<th class='left'>Sector</th>"
        "<th>Date</th>"
        "<th>Volume (CHF)</th>"
        "<th>Trades</th>"
        "<th>Δ Price</th>"
        "<th>Volatility σ</th>"
        "<th>Status</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  Main Application
# ─────────────────────────────────────────────
def main() -> None:
    inject_css()

    df_hist, latest = load_data()

    if df_hist.empty:
        st.error("No data available. Run `python main.py` to populate the data pipeline.")
        st.stop()

    latest_date = df_hist["Datum"].max().strftime("%d.%m.%Y")
    render_header(latest_date)

    tab1, tab2, tab3, tab4 = st.tabs([
        "  Overview  ",
        "  Market Data  ",
        "  Analytics  ",
        "  Anomaly Monitor  ",
    ])

    # ══════════════════════════════════════════
    # TAB 1 — Overview
    # ══════════════════════════════════════════
    with tab1:
        render_kpis(latest)
        st.markdown("<br>", unsafe_allow_html=True)

        col_act, col_tree = st.columns([3, 2])
        with col_act:
            st.markdown('<div class="sec-hdr">Market Activity — Last 90 Days</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_market_activity(df_hist), use_container_width=True)
        with col_tree:
            st.markdown('<div class="sec-hdr">Sector Allocation by Volume</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_sector_treemap(latest), use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        col_mov, col_vol = st.columns(2)
        with col_mov:
            st.markdown('<div class="sec-hdr">Top Movers — Price Change %</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_top_movers(latest), use_container_width=True)
        with col_vol:
            st.markdown('<div class="sec-hdr">Volume by Sector (CHF)</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_volume_by_sector(latest), use_container_width=True)

    # ══════════════════════════════════════════
    # TAB 2 — Market Data
    # ══════════════════════════════════════════
    with tab2:
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        with fc1:
            search = st.text_input(
                "Search", placeholder="Name, ISIN or Sector…", label_visibility="collapsed"
            )
        with fc2:
            sectors = ["All"] + sorted(latest["Sektor"].dropna().unique().tolist())
            sel_sector = st.selectbox("Sector", sectors, label_visibility="collapsed")
        with fc3:
            sort_by = st.selectbox(
                "Sort", ["Volume (CHF)", "Trades", "Price Change", "Anomaly Score"],
                label_visibility="collapsed",
            )

        df_filt = latest.copy()
        if search:
            q = search.lower()
            df_filt = df_filt[
                df_filt["Isin"].str.lower().str.contains(q, na=False)
                | df_filt["Name"].str.lower().str.contains(q, na=False)
                | df_filt["Sektor"].str.lower().str.contains(q, na=False)
            ]
        if sel_sector != "All":
            df_filt = df_filt[df_filt["Sektor"] == sel_sector]

        sort_col = {
            "Volume (CHF)": "volume_today_chf",
            "Trades": "trades_today",
            "Price Change": "price_change_pct",
            "Anomaly Score": "anomaly_score",
        }[sort_by]
        df_filt = df_filt.sort_values(sort_col, ascending=False)

        st.markdown(
            f'<div class="sec-hdr">Market Feed — {len(df_filt)} Securities</div>',
            unsafe_allow_html=True,
        )
        render_market_table(df_filt, n=min(100, len(df_filt)))

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr">Security Detail View</div>',
                    unsafe_allow_html=True)

        active_isins = df_filt[df_filt["trades_today"] > 0]["Isin"].tolist()
        if active_isins:
            def _isin_label(x: str) -> str:
                row = latest[latest["Isin"] == x]
                if row.empty:
                    return x
                name = row["Name"].values[0]
                if name and pd.notna(name):
                    return f"{x} — {name}"
                return x

            sel_isin = st.selectbox(
                "Select security",
                active_isins,
                format_func=_isin_label,
                label_visibility="collapsed",
            )
            st.plotly_chart(chart_security_history(df_hist, sel_isin),
                            use_container_width=True)

    # ══════════════════════════════════════════
    # TAB 3 — Analytics
    # ══════════════════════════════════════════
    with tab3:
        col_sc, col_corr = st.columns([3, 2])
        with col_sc:
            st.markdown(
                '<div class="sec-hdr">Volume vs. Price Change — Log Scale</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(chart_scatter_volume_price(latest), use_container_width=True)
        with col_corr:
            st.markdown('<div class="sec-hdr">Metric Correlation Matrix</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_correlation_heatmap(latest), use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        col_amh, col_vt = st.columns(2)
        with col_amh:
            st.markdown(
                '<div class="sec-hdr">Amihud Illiquidity Distribution by Sector</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(chart_amihud_by_sector(df_hist), use_container_width=True)
        with col_vt:
            st.markdown(
                '<div class="sec-hdr">Rolling Volatility — Top Sectors (30-Day MA)</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(chart_volatility_trend(df_hist), use_container_width=True)

    # ══════════════════════════════════════════
    # TAB 4 — Anomaly Monitor
    # ══════════════════════════════════════════
    with tab4:
        col_dist, col_risk = st.columns([2, 3])

        with col_dist:
            st.markdown('<div class="sec-hdr">Score Distribution</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_anomaly_distribution(latest), use_container_width=True)

        with col_risk:
            total  = len(latest)
            clean   = int(latest["anomaly_score"].isin(TIER_SCORES["clean"]).sum())
            alert   = int(latest["anomaly_score"].isin(TIER_SCORES["alert"]).sum())
            crit    = int(latest["anomaly_score"].isin(TIER_SCORES["critical"]).sum())
            severe  = int(latest["anomaly_score"].isin(TIER_SCORES["severe"]).sum())
            extreme = int(latest["anomaly_score"].isin(TIER_SCORES["extreme"]).sum())
            st.markdown('<div class="sec-hdr">Risk Summary</div>',
                        unsafe_allow_html=True)
            rc = st.columns(5)
            for col, (lbl, val, border, txt) in zip(rc, [
                ("Clean",    clean,   "#28A745", "#28A745"),
                ("Alert",    alert,   "#FD7E14", "#FD7E14"),
                ("Critical", crit,    "#DC3545", "#DC3545"),
                ("Severe",   severe,  "#7D1128", "#7D1128"),
                ("Extreme",  extreme, "#4A0010", "#4A0010"),
            ]):
                with col:
                    st.markdown(
                        f'<div class="kpi-card" style="border-top-color:{border}">'
                        f'<div class="kpi-label">{lbl}</div>'
                        f'<div class="kpi-value" style="color:{txt};font-size:1.6rem">{val}</div>'
                        f'<div class="kpi-sub">{val/total*100:.1f}% of market</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr">Alerts</div>', unsafe_allow_html=True)

        # ── Severity filter toggle group ──
        _tiers = [
            ("clean",    "Show Clean"),
            ("alert",    "Show Alert"),
            ("critical", "Show Critical"),
            ("severe",   "Show Severe"),
            ("extreme",  "Show Extreme"),
        ]
        # Initialise session state for each tier (all except Clean on by default)
        for key, _ in _tiers:
            if f"show_{key}" not in st.session_state:
                st.session_state[f"show_{key}"] = key != "clean"

        filter_cols = st.columns(len(_tiers))
        for col, (key, label) in zip(filter_cols, _tiers):
            with col:
                st.checkbox(label, key=f"show_{key}")

        # Build mask from active tiers
        active_scores: list[int] = []
        for key, _ in _tiers:
            if st.session_state.get(f"show_{key}", False):
                active_scores.extend(TIER_SCORES[key])

        if not active_scores:
            st.info("Select at least one severity tier above to display alerts.")
        else:
            alerts = latest[latest["anomaly_score"].isin(active_scores)].sort_values(
                "anomaly_score", ascending=False
            )
            if alerts.empty:
                st.success("✓  No anomalies detected for the selected tiers.")
            else:
                render_market_table(alerts, n=min(60, len(alerts)))


if __name__ == "__main__":
    main()
