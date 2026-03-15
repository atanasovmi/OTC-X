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
BORDER_COL   = "#CED4DA"
MUTED        = "#343A40"   # dark grey for strong contrast on white backgrounds
MUTED_SEC    = "#495057"   # secondary muted — still high-contrast
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

# Severity tier grouping for clickable anomaly categories
SEVERITY_TIERS = {
    "Clean":    [0],
    "Watch":    [1],
    "Alert":    [2],
    "Critical": [3, 4],
    "Severe":   [5, 6],
    "Extreme":  [7],
}


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert a #RRGGBB hex string to an rgba(...) CSS value."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i: i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


# ─────────────────────────────────────────────
#  CSS – Swiss Institutional Banking Theme
# ─────────────────────────────────────────────
def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #1A1A2E;
        }
        .stApp { background-color: #F5F6F8; }

        /* ── Header ── */
        .otcx-header {
            background: #FFFFFF;
            border-bottom: 3px solid #B22222;
            padding: 0.9rem 2rem;
            margin: -1rem -1rem 1.5rem -1rem;
            display: flex;
            align-items: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
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
            color: #343A40;
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
            border-bottom: 2px solid #B22222;
            padding-bottom: 0.45rem;
            margin-bottom: 0.8rem;
        }

        /* ── Metric Cards ── */
        .kpi-card {
            background: #FFFFFF;
            border: 1px solid #CED4DA;
            border-top: 3px solid #B22222;
            padding: 1.1rem 1.3rem;
            height: 100%;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }
        .kpi-label {
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #343A40;
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
        .kpi-sub { font-size: 0.72rem; color: #343A40; }
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
            color: #1A1A2E;
            border-bottom: 2px solid #CED4DA;
            padding: 0.55rem 0.7rem;
            text-align: right;
            white-space: nowrap;
            background: #F8F9FA;
        }
        .mkt-table th.left { text-align: left; }
        .mkt-table td {
            padding: 0.55rem 0.7rem;
            border-bottom: 1px solid #E9ECEF;
            text-align: right;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.8rem;
            white-space: nowrap;
            color: #1A1A2E;
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
        .mkt-table td.isin a {
            color: #B22222;
            text-decoration: none;
        }
        .mkt-table td.isin a:hover {
            text-decoration: underline;
            color: #8B1A1A;
        }
        .mkt-table td.name {
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            max-width: 180px;
            overflow: hidden;
            text-overflow: ellipsis;
            color: #1A1A2E;
        }
        .mkt-table td.sektor {
            font-size: 0.75rem;
            color: #343A40;
        }
        .mkt-table tr:hover { background: #F0F1F3; }
        .pos { color: #28A745 !important; }
        .neg { color: #DC3545 !important; }

        /* ── Badges ── */
        .bdg {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            font-size: 0.6rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            border-radius: 2px;
        }
        .bdg-clean    { background: #D4EDDA; color: #155724; }
        .bdg-watch    { background: #FFF3CD; color: #664D03; }
        .bdg-alert    { background: #FFE0CC; color: #6A3200; }
        .bdg-critical { background: #F8D7DA; color: #58151C; }
        .bdg-severe   { background: #E8C4D0; color: #4A0E1E; }
        .bdg-extreme  { background: #D4A0B0; color: #3A0010; }

        /* ── Risk Card (clickable) ── */
        .risk-card {
            background: #FFFFFF;
            border: 1px solid #CED4DA;
            border-top: 3px solid #CED4DA;
            padding: 1rem 1.2rem;
            cursor: pointer;
            transition: all 0.15s ease;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }
        .risk-card:hover { transform: translateY(-1px); box-shadow: 0 3px 8px rgba(0,0,0,0.08); }
        .risk-card.active { border-color: #B22222; border-top-width: 3px; }

        /* ── Tabs ── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0;
            background: #FFFFFF;
            border-bottom: 2px solid #CED4DA;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 0.7rem 1.4rem;
            font-size: 0.82rem;
            font-weight: 500;
            letter-spacing: 0.02em;
            color: #343A40;
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
        section[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #CED4DA; }

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

        /* ── Math formula ── */
        .math-note {
            font-size: 0.72rem;
            color: #343A40;
            font-style: italic;
            font-family: 'IBM Plex Mono', monospace;
            margin-bottom: 0.5rem;
        }

        /* ── Streamlit override: selectbox, text_input, number_input labels ── */
        .stSelectbox label, .stTextInput label, .stNumberInput label,
        .stMultiSelect label, .stSlider label, .stCheckbox label,
        .stRadio label {
            color: #1A1A2E !important;
        }
        .stSelectbox [data-baseweb="select"] span,
        .stMultiSelect [data-baseweb="select"] span {
            color: #1A1A2E !important;
        }
        div[data-testid="stMetricLabel"] p {
            color: #1A1A2E !important;
        }
        div[data-testid="stMetricValue"] div {
            color: #1A1A2E !important;
        }
        /* Checkbox label text — override Streamlit grey */
        .stCheckbox label p, .stCheckbox label span,
        .stCheckbox [data-testid="stMarkdownContainer"] p {
            color: #1A1A2E !important;
        }
        /* Selectbox / multiselect chosen value text */
        [data-baseweb="select"] .css-1dimb5e-singleValue,
        [data-baseweb="select"] [data-testid="stMarkdownContainer"],
        [data-baseweb="tag"] span {
            color: #1A1A2E !important;
        }

        /* ── Neutral Streamlit buttons — warm sand instead of bright red ── */
        .stButton > button {
            background-color: rgb(235, 226, 205) !important;
            color: #1A1A2E !important;
            border: 1px solid #C8BFA5 !important;
            font-weight: 600 !important;
            transition: all 0.15s ease !important;
        }
        .stButton > button:hover {
            background-color: rgb(220, 210, 185) !important;
            border-color: #B0A585 !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08) !important;
        }
        .stButton > button:focus {
            box-shadow: 0 0 0 2px rgba(178,34,34,0.18) !important;
        }
        /* Download button — keep distinct with brand accent */
        .stDownloadButton > button {
            background-color: #B22222 !important;
            color: #FFFFFF !important;
            border: 1px solid #8B1A1A !important;
            font-weight: 600 !important;
        }
        .stDownloadButton > button:hover {
            background-color: #8B1A1A !important;
        }

        /* ── Misc ── */
        #MainMenu, footer, header { visibility: hidden; }
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        p, span, li, div { color: inherit; }

        /* ── Anomaly detail table ── */
        .anomaly-detail-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem;
        }
        .anomaly-detail-table th {
            font-size: 0.62rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            color: #1A1A2E;
            border-bottom: 2px solid #CED4DA;
            padding: 0.5rem 0.6rem;
            text-align: right;
            background: #F8F9FA;
        }
        .anomaly-detail-table th.left { text-align: left; }
        .anomaly-detail-table td {
            padding: 0.5rem 0.6rem;
            border-bottom: 1px solid #E9ECEF;
            text-align: right;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            color: #1A1A2E;
        }
        .anomaly-detail-table td.left { text-align: left; font-family: 'Inter', sans-serif; }
        .anomaly-detail-table tr:hover { background: #F0F1F3; }

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
def _base_layout(**kwargs) -> dict:
    _axis_defaults = dict(
        tickfont=dict(color="#1A1A2E"),
        title_font=dict(color="#1A1A2E"),
    )
    base = dict(
        template=PLOTLY_TPL,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Inter", color="#1A1A2E"),
        margin=dict(l=4, r=4, t=16, b=4),
        xaxis=_axis_defaults.copy(),
        yaxis=_axis_defaults.copy(),
    )
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
                                                  font=dict(size=10, color="#1A1A2E"))))
    fig.update_xaxes(gridcolor="#E9ECEF", tickfont=dict(color="#1A1A2E"))
    fig.update_yaxes(title_text="Volume (CHF)", gridcolor="#E9ECEF",
                     secondary_y=False, tickformat=",.0f",
                     tickfont=dict(color="#1A1A2E"))
    fig.update_yaxes(title_text="Trades", showgrid=False, secondary_y=True,
                     tickfont=dict(color="#1A1A2E"))
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
                                  ticksuffix="%", gridcolor="#E9ECEF", zeroline=False,
                                  tickfont=dict(color="#1A1A2E")),
                       yaxis=dict(title=None, tickfont=dict(size=11, color="#1A1A2E")),
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
                       xaxis=dict(title=None, gridcolor="#E9ECEF", zeroline=False,
                                  tickfont=dict(color="#1A1A2E")),
                       yaxis=dict(title=None, tickfont=dict(size=11, color="#1A1A2E")),
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
                gridcolor="#E9ECEF",
                tickformat=",.0f",
            ),
            yaxis=dict(
                title="Price Change (%)",
                ticksuffix="%",
                gridcolor="#E9ECEF",
                zeroline=False,
            ),
            legend=dict(
                orientation="v",
                x=1.01,
                y=1,
                font=dict(size=10),
                title=dict(text="Sector", font=dict(size=10)),
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
            yaxis=dict(title="Amihud Illiquidity Ratio", gridcolor="#E9ECEF"),
            xaxis=dict(tickangle=-30, tickfont=dict(size=10)),
        )
    )
    return fig


def chart_volatility_trend(df_hist: pd.DataFrame, n: int = 5,
                           use_ewma: bool = False,
                           selected_sector: str | None = None) -> go.Figure:
    """Rolling volatility chart with optional EWMA smoothing and
    hover-to-isolate interaction.

    Parameters
    ----------
    use_ewma : If True, apply RiskMetrics EWMA (λ=0.94) instead of simple MA.
    selected_sector : If set, highlight only this sector and dim others.
    """
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

        if use_ewma:
            # RiskMetrics EWMA: s_t = λ * s_{t-1} + (1 - λ) * v_t, λ = 0.94
            grp["smoothed"] = grp["volatility_daily"].ewm(alpha=0.06, adjust=False).mean()
        else:
            grp["smoothed"] = grp["volatility_daily"].rolling(30, min_periods=1).mean()

        # Determine visibility: if a sector is selected, dim others
        is_highlighted = selected_sector is None or sector == selected_sector
        opacity = 1.0 if is_highlighted else 0.12
        width = 2.2 if (selected_sector and sector == selected_sector) else 1.5

        fig.add_trace(
            go.Scatter(
                x=grp["Datum"],
                y=grp["smoothed"],
                mode="lines",
                name=sector,
                line=dict(
                    color=palette[i % len(palette)],
                    width=width,
                ),
                opacity=opacity,
                hovertemplate="%{x|%d.%m.%Y}: %{y:.4f}<extra>%{fullData.name}</extra>",
            )
        )

    smoothing_label = "EWMA (λ=0.94)" if use_ewma else "30-Day SMA"
    fig.update_layout(
        **_base_layout(
            height=390,
            xaxis=dict(title=None, gridcolor="#E9ECEF"),
            yaxis=dict(title=f"Avg Daily Volatility σ ({smoothing_label})",
                       gridcolor="#E9ECEF",
                       title_font=dict(color="#1A1A2E")),
            legend=dict(orientation="h", y=-0.2, font=dict(size=10, color="#1A1A2E")),
        )
    )
    return fig


def chart_correlation_heatmap(df: pd.DataFrame, selected_cols: list[str] | None = None) -> go.Figure:
    """Full-width correlation matrix with configurable metrics."""
    all_cols = {
        "price_change_pct": "Δ Price",
        "volatility_daily": "Volatility σ",
        "amihud_daily": "Amihud λ",
        "volume_today_chf": "Volume",
        "trades_today": "Trades",
        "off_book_pct": "Off-Book %",
        "anomaly_score": "Anomaly",
        "spread_log_hl": "Spread ln(H/L)",
        "log_returns": "ln(r)",
    }
    if selected_cols is None:
        selected_cols = list(all_cols.keys())[:7]
    labels = [all_cols.get(c, c) for c in selected_cols]
    data = df[selected_cols].dropna()
    corr = data.corr()

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
            textfont=dict(size=11, family="IBM Plex Mono", color="#1A1A2E"),
            hoverongaps=False,
            colorbar=dict(title="ρ", thickness=12, len=0.8,
                          tickfont=dict(color="#1A1A2E"),
                          title_font=dict(color="#1A1A2E")),
        )
    )
    fig.update_layout(
        **_base_layout(
            height=480,
            xaxis=dict(tickfont=dict(size=11, color="#1A1A2E")),
            yaxis=dict(tickfont=dict(size=11, color="#1A1A2E"), autorange="reversed"),
        )
    )
    return fig


def chart_anomaly_severity_treemap(latest: pd.DataFrame) -> go.Figure:
    """Treemap showing securities grouped by anomaly severity tier —
    each box is sized by anomaly_score and colour-coded by severity."""
    df = latest[latest["anomaly_score"] >= 1].copy()
    if df.empty:
        return go.Figure()

    df["severity"] = df["anomaly_score"].map(ANOMALY_LABELS).fillna("Unknown")
    df["label"] = df["Name"].fillna(df["Isin"]).str[:28]
    df["score_size"] = df["anomaly_score"]  # already >= 1 from filter above

    severity_order = ["Watch", "Alert", "Critical", "Severe", "Extreme"]
    df["sev_order"] = df["severity"].map({s: i for i, s in enumerate(severity_order)}).fillna(99)
    df = df.sort_values(["sev_order", "anomaly_score"], ascending=[False, False])

    fig = px.treemap(
        df,
        path=["severity", "label"],
        values="score_size",
        color="anomaly_score",
        color_continuous_scale=[
            [0.0, "#FFC107"],
            [0.3, "#FD7E14"],
            [0.5, "#DC3545"],
            [0.8, "#7D1128"],
            [1.0, "#4A0010"],
        ],
        range_color=[1, 7],
        custom_data=["Isin", "Sektor", "anomaly_score", "volume_today_chf",
                      "price_change_pct", "volatility_daily"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b>",
        textfont=dict(family="Inter", size=10),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Sector: %{customdata[1]}<br>"
            "Score: %{customdata[2]}<br>"
            "Volume: CHF %{customdata[3]:,.0f}<br>"
            "Δ Price: %{customdata[4]:+.2f}%<br>"
            "Volatility: %{customdata[5]:.4f}<extra></extra>"
        ),
        marker_line_width=1.5,
        marker_line_color="white",
    )
    fig.update_layout(
        **_base_layout(
            height=380,
            coloraxis_colorbar=dict(title="Score", thickness=10,
                                     tickfont=dict(color="#1A1A2E"),
                                     title_font=dict(color="#1A1A2E")),
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
            legend=dict(orientation="h", y=1.05, font=dict(size=10)),
            xaxis2=dict(title=None, gridcolor="#E9ECEF"),
            yaxis=dict(title="Price (CHF)", gridcolor="#E9ECEF"),
            yaxis2=dict(title="Volume (CHF)", gridcolor="#E9ECEF"),
            bargap=0.08,
        )
    )
    return fig


def chart_3d_explorer(
    df: pd.DataFrame,
    x_col: str, y_col: str, z_col: str,
    color_col: str, size_col: str,
    use_log: bool = False,
    remove_outliers: bool = False,
) -> go.Figure:
    """Interactive 3D scatter plot with 5+ variable mapping.

    Parameters
    ----------
    df : filtered dataframe (latest snapshot)
    x_col, y_col, z_col : columns mapped to 3D axes
    color_col : column mapped to colour
    size_col : column mapped to marker size
    use_log : apply log₁₀ transformation to numeric axes
    remove_outliers : clip values beyond 1st–99th percentile
    """
    metric_labels = {
        "price_change_pct": "Δ Price %",
        "volatility_daily": "Volatility σ",
        "amihud_daily": "Amihud λ",
        "volume_today_chf": "Volume (CHF)",
        "trades_today": "Trades",
        "off_book_pct": "Off-Book %",
        "anomaly_score": "Anomaly Score",
        "spread_log_hl": "Spread ln(H/L)",
        "log_returns": "ln(r)",
        "price_last": "Last Price",
        "volume_today_units": "Volume (Units)",
        "trade_duration_min": "Trade Duration (min)",
    }
    plot_df = df.copy()
    plot_df["label"] = plot_df["Name"].fillna(plot_df["Isin"]).str[:28]
    numeric_cols = [x_col, y_col, z_col, color_col, size_col]
    numeric_cols = list(dict.fromkeys(numeric_cols))  # deduplicate

    for c in numeric_cols:
        plot_df[c] = pd.to_numeric(plot_df[c], errors="coerce")
    plot_df = plot_df.dropna(subset=numeric_cols)

    if remove_outliers and len(plot_df) > 10:
        for c in numeric_cols:
            lo, hi = plot_df[c].quantile([0.01, 0.99])
            plot_df = plot_df[plot_df[c].between(lo, hi)]

    if use_log:
        for c in [x_col, y_col, z_col]:
            # Shift to positive before log — handle zeros / negatives
            col_min = plot_df[c].min()
            shift = abs(col_min) + 1 if col_min <= 0 else 0
            plot_df[c] = np.log10(plot_df[c] + shift)

    if plot_df.empty:
        return go.Figure()

    # Normalise size to [6, 35]
    sz = plot_df[size_col]
    sz_min, sz_max = sz.min(), sz.max()
    if sz_max > sz_min:
        norm_size = 6 + 29 * (sz - sz_min) / (sz_max - sz_min)
    else:
        norm_size = pd.Series(12, index=sz.index)

    x_label = metric_labels.get(x_col, x_col)
    y_label = metric_labels.get(y_col, y_col)
    z_label = metric_labels.get(z_col, z_col)
    if use_log:
        x_label = f"log₁₀({x_label})"
        y_label = f"log₁₀({y_label})"
        z_label = f"log₁₀({z_label})"

    fig = go.Figure(
        go.Scatter3d(
            x=plot_df[x_col],
            y=plot_df[y_col],
            z=plot_df[z_col],
            mode="markers",
            marker=dict(
                size=norm_size,
                color=plot_df[color_col],
                colorscale="RdYlGn_r",
                colorbar=dict(
                    title=dict(text=metric_labels.get(color_col, color_col),
                               font=dict(color="#1A1A2E")),
                    thickness=14,
                    tickfont=dict(color="#1A1A2E"),
                ),
                opacity=0.85,
                line=dict(width=0.3, color="#FFFFFF"),
            ),
            text=plot_df["label"],
            customdata=np.stack([
                plot_df["Isin"],
                plot_df["Sektor"].fillna("—"),
                plot_df.get("anomaly_score", pd.Series(0, index=plot_df.index)),
            ], axis=-1),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "ISIN: %{customdata[0]}<br>"
                "Sector: %{customdata[1]}<br>"
                f"{x_label}: " + "%{x:.3f}<br>"
                f"{y_label}: " + "%{y:.3f}<br>"
                f"{z_label}: " + "%{z:.3f}<br>"
                "Anomaly: %{customdata[2]}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        scene=dict(
            xaxis=dict(title=x_label, backgroundcolor="#F5F6F8",
                        gridcolor="#CED4DA", showbackground=True,
                        title_font=dict(color="#1A1A2E"),
                        tickfont=dict(color="#1A1A2E")),
            yaxis=dict(title=y_label, backgroundcolor="#F5F6F8",
                        gridcolor="#CED4DA", showbackground=True,
                        title_font=dict(color="#1A1A2E"),
                        tickfont=dict(color="#1A1A2E")),
            zaxis=dict(title=z_label, backgroundcolor="#F5F6F8",
                        gridcolor="#CED4DA", showbackground=True,
                        title_font=dict(color="#1A1A2E"),
                        tickfont=dict(color="#1A1A2E")),
            camera=dict(eye=dict(x=1.6, y=1.6, z=0.9)),
        ),
        paper_bgcolor="white",
        font=dict(family="Inter", color="#1A1A2E"),
        margin=dict(l=0, r=0, t=20, b=0),
        height=620,
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
            <div class="otcx-logo">OTC<span>|X</span></div>
            <div class="otcx-tagline">Market Intelligence Platform</div>
          </div>
          <div style="margin-left:auto;display:flex;align-items:center;gap:2rem;">
            <span class="live-dot"><span class="dot"></span> Live</span>
            <span style="font-size:0.72rem;color:#343A40;">
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
        vol_units = r.get("volume_today_units", 0)
        vol_chf = r.get("volume_today_chf", 0)
        trades = int(r.get("trades_today", 0))
        vola = r.get("volatility_daily", 0)
        rows += (
            f"<tr>"
            f"<td class='isin'><a href='https://www.otc-x.ch/security/{r['Isin']}' "
            f"target='_blank' style='color:#B22222;text-decoration:none;'>"
            f"{r['Isin']}</a></td>"
            f"<td class='name left'>{str(r.get('Name',''))[:34]}</td>"
            f"<td class='sektor left'>"
            f"{str(r.get('Sektor',''))[:22]}</td>"
            f"<td>{date}</td>"
            f"<td>{fmt_chf(vol_chf)}</td>"
            f"<td>{fmt_num(vol_units)}</td>"
            f"<td>{trades}</td>"
            f"<td class='{pct_cls(pct)}'>{fmt_pct(pct)}</td>"
            f"<td>{vola:.4f}</td>"
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
        "<th>Volume (Units)</th>"
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
    # TAB 2 — Market Data (Raw Data Explorer)
    # ══════════════════════════════════════════
    with tab2:
        st.markdown(
            '<div class="sec-hdr">Data Explorer — Raw Market Data</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:0.78rem;color:#1A1A2E;margin-bottom:0.8rem;">'
            'Browse, filter, and download raw market data for offline analysis. '
            'Click any <strong style="color:#B22222;">ISIN</strong> to view the security on '
            '<a href="https://www.otc-x.ch" target="_blank" style="color:#B22222;">otc-x.ch</a>.'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Filter controls ──
        fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
        with fc1:
            search = st.text_input(
                "Search", placeholder="Name, ISIN or Sector…", label_visibility="collapsed"
            )
        with fc2:
            sectors = ["All Sectors"] + sorted(latest["Sektor"].dropna().unique().tolist())
            sel_sector = st.selectbox("Sector", sectors, label_visibility="collapsed")
        with fc3:
            sort_by = st.selectbox(
                "Sort by",
                ["Volume (CHF)", "Trades", "Price Change", "Anomaly Score",
                         "Volatility", "Amihud λ", "Name"],
                label_visibility="collapsed",
            )
        with fc4:
            rows_to_show = st.selectbox(
                "Rows",
                [25, 50, 100, 200, "All"],
                index=1,
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
        if sel_sector != "All Sectors":
            df_filt = df_filt[df_filt["Sektor"] == sel_sector]

        sort_map = {
            "Volume (CHF)": "volume_today_chf",
            "Trades": "trades_today",
            "Price Change": "price_change_pct",
            "Anomaly Score": "anomaly_score",
            "Volatility": "volatility_daily",
            "Amihud λ": "amihud_daily",
            "Name": "Name",
        }
        sort_col = sort_map[sort_by]
        sort_asc = sort_by == "Name"
        df_filt = df_filt.sort_values(sort_col, ascending=sort_asc)

        n_display = len(df_filt) if rows_to_show == "All" else min(int(rows_to_show), len(df_filt))

        # ── Summary bar ──
        sum_vol = df_filt["volume_today_chf"].sum()
        sum_trades = int(df_filt["trades_today"].sum())
        avg_vola = df_filt["volatility_daily"].mean() if not df_filt.empty else 0
        avg_amihud = df_filt["amihud_daily"].mean() if not df_filt.empty else 0

        sm1, sm2, sm3, sm4, sm5 = st.columns(5)
        summary_items = [
            ("Securities", str(len(df_filt))),
            ("Total Volume", fmt_chf(sum_vol)),
            ("Total Trades", f"{sum_trades:,}"),
            ("Avg σ", f"{avg_vola:.4f}"),
            ("Avg λ", f"{avg_amihud:.6f}"),
        ]
        for col, (lbl, val) in zip([sm1, sm2, sm3, sm4, sm5], summary_items):
            with col:
                st.markdown(
                    f'<div style="background:#FFFFFF;border:1px solid #CED4DA;'
                    f'padding:0.6rem 0.9rem;text-align:center;">'
                    f'<div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.1em;color:#343A40;">{lbl}</div>'
                    f'<div style="font-size:1.1rem;font-weight:700;color:#1A1A2E;'
                    f'font-family:IBM Plex Mono,monospace;">{val}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        # ── CSV Download ──
        csv_cols = ["Isin", "Name", "Sektor", "Datum", "price_last", "price_change_pct",
                    "volume_today_chf", "volume_today_units", "trades_today",
                    "volatility_daily", "amihud_daily", "anomaly_score",
                    "spread_log_hl", "log_returns", "off_book_pct"]
        csv_available = [c for c in csv_cols if c in df_filt.columns]
        csv_data = df_filt[csv_available].copy()
        if "Datum" in csv_data.columns:
            csv_data["Datum"] = csv_data["Datum"].dt.strftime("%Y-%m-%d")

        dl1, dl2 = st.columns([1, 4])
        with dl1:
            st.download_button(
                label="⬇ Download CSV",
                data=csv_data.to_csv(index=False).encode("utf-8"),
                file_name="otcx_market_data.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with dl2:
            st.markdown(
                f'<div style="font-size:0.72rem;color:#343A40;padding-top:0.6rem;">'
                f'Showing <strong>{n_display}</strong> of <strong>{len(df_filt)}</strong> '
                f'securities · {len(csv_available)} columns available for export'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── Data table ──
        render_market_table(df_filt, n=n_display)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Security Detail View ──
        st.markdown('<div class="sec-hdr">Security Detail View</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:0.72rem;color:#1A1A2E;margin-bottom:0.4rem;">'
            'Select a security to view its price history, volume profile, and key metrics.'
            '</div>',
            unsafe_allow_html=True,
        )

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

            # ── Security summary metrics with math notation ──
            sec_row = latest[latest["Isin"] == sel_isin]
            if not sec_row.empty:
                r = sec_row.iloc[0]
                st.markdown(
                    '<div class="sec-hdr">Key Metrics</div>',
                    unsafe_allow_html=True,
                )
                mc = st.columns(5)
                metric_items = [
                    ("Last Price", fmt_chf(r.get("price_last", 0)),
                     f"Range: {fmt_chf(r.get('price_min',0))} – {fmt_chf(r.get('price_max',0))}"),
                    ("Daily Volume", fmt_chf(r.get("volume_today_chf", 0)),
                     f"{fmt_num(r.get('volume_today_units',0))} units"),
                    ("Trades", str(int(r.get("trades_today", 0))),
                     f"30d median: {r.get('trades_30d_median',0):.0f}"),
                    ("Volatility σ", f"{r.get('volatility_daily',0):.4f}",
                     f"30d median: {r.get('volatility_30d_median',0):.4f}"),
                    ("Amihud λ", f"{r.get('amihud_daily',0):.6f}",
                     f"30d median: {r.get('amihud_30d_median',0):.6f}"),
                ]
                for col, (lbl, val, sub) in zip(mc, metric_items):
                    with col:
                        st.markdown(
                            f'<div class="kpi-card">'
                            f'<div class="kpi-label">{lbl}</div>'
                            f'<div class="kpi-value" style="font-size:1.2rem">{val}</div>'
                            f'<div class="kpi-sub">{sub}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                # Math notation explaining metrics
                st.markdown(
                    '<div class="math-note">'
                    'σ = std(P<sub>intraday</sub>) &nbsp;·&nbsp; '
                    'λ<sub>Amihud</sub> = |ln(P<sub>last</sub>/P<sub>first</sub>)| '
                    '/ V<sub>CHF</sub> × 10⁶ &nbsp;·&nbsp; '
                    'Spread ≈ ln(P<sub>high</sub>/P<sub>low</sub>)'
                    '</div>',
                    unsafe_allow_html=True,
                )

    # ══════════════════════════════════════════
    # TAB 3 — Analytics
    # ══════════════════════════════════════════
    with tab3:
        # ── Customisation controls ──
        st.markdown('<div class="sec-hdr">Analysis Controls</div>', unsafe_allow_html=True)
        ctrl1, ctrl2 = st.columns([1, 1])
        with ctrl1:
            hm_sectors = st.multiselect(
                "Filter by Sector",
                sorted(latest["Sektor"].dropna().unique().tolist()),
                default=[],
                help="Leave empty for all sectors",
                key="analytics_sector_filter",
            )
        with ctrl2:
            hm_metric_options = {
                "price_change_pct": "Δ Price %",
                "volatility_daily": "Volatility σ",
                "amihud_daily": "Amihud λ",
                "volume_today_chf": "Volume (CHF)",
                "trades_today": "Trades",
                "off_book_pct": "Off-Book %",
                "anomaly_score": "Anomaly Score",
                "spread_log_hl": "Spread ln(H/L)",
                "log_returns": "Log Returns ln(r)",
            }
            hm_selected = st.multiselect(
                "Heatmap Metrics",
                list(hm_metric_options.keys()),
                default=list(hm_metric_options.keys())[:7],
                format_func=lambda x: hm_metric_options[x],
                key="heatmap_metrics",
            )

        # Filter data
        analytics_df = latest.copy()
        if hm_sectors:
            analytics_df = analytics_df[analytics_df["Sektor"].isin(hm_sectors)]

        st.markdown(
            f'<div class="math-note">'
            f'ρ(X,Y) = cov(X,Y) / (σ<sub>X</sub> · σ<sub>Y</sub>) '
            f'&nbsp;|&nbsp; Showing {len(analytics_df)} securities'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Correlation Heatmap (full width) ──
        st.markdown(
            '<div class="sec-hdr">Metric Correlation Matrix</div>',
            unsafe_allow_html=True,
        )
        if len(hm_selected) >= 2:
            st.plotly_chart(
                chart_correlation_heatmap(analytics_df, hm_selected),
                use_container_width=True,
            )
        else:
            st.info("Select at least 2 metrics to display the correlation matrix.")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Volume vs Price + Amihud + Volatility ──
        col_sc, col_amh = st.columns(2)
        with col_sc:
            st.markdown(
                '<div class="sec-hdr">Volume vs. Price Change — Log Scale</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(chart_scatter_volume_price(analytics_df),
                            use_container_width=True)
        with col_amh:
            st.markdown(
                '<div class="sec-hdr">Amihud Illiquidity by Sector</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="math-note">'
                'λ<sub>Amihud</sub> = |r<sub>t</sub>| / V<sub>t</sub> × 10⁶'
                '</div>',
                unsafe_allow_html=True,
            )
            hist_filtered = df_hist.copy()
            if hm_sectors:
                hist_filtered = hist_filtered[hist_filtered["Sektor"].isin(hm_sectors)]
            st.plotly_chart(chart_amihud_by_sector(hist_filtered),
                            use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div class="sec-hdr">Rolling Volatility — Top Sectors</div>',
            unsafe_allow_html=True,
        )

        vol_c1, vol_c2 = st.columns([3, 1])
        with vol_c2:
            use_ewma = st.checkbox(
                "Use EWMA smoothing (λ = 0.94)",
                value=False,
                key="vol_ewma",
                help="Exponentially Weighted Moving Average with RiskMetrics decay factor λ=0.94: sₜ = 0.94·sₜ₋₁ + 0.06·vₜ",
            )
        with vol_c1:
            if use_ewma:
                st.markdown(
                    '<div class="math-note">'
                    's<sub>t</sub> = λ · s<sub>t-1</sub> + (1 − λ) · v<sub>t</sub>'
                    '&nbsp;&nbsp;with λ = 0.94 (RiskMetrics)'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="math-note">'
                    'σ̄<sub>30d</sub> = (1/30) Σ σ<sub>daily</sub>'
                    '</div>',
                    unsafe_allow_html=True,
                )

        # Sector click-to-isolate
        vol_hist_data = hist_filtered if hm_sectors else df_hist
        top_vol_sectors = (
            vol_hist_data.groupby("Sektor")["trades_today"]
            .sum()
            .nlargest(5)
            .index.tolist()
        )
        selected_vol_sector = st.session_state.get("vol_selected_sector", None)

        st.markdown(
            '<div style="font-size:0.72rem;color:#1A1A2E;margin-bottom:0.5rem;">'
            '👆 <strong>Click a sector below</strong> to isolate it. Click again to reset.'
            '</div>',
            unsafe_allow_html=True,
        )
        vol_btn_cols = st.columns(len(top_vol_sectors))
        for idx, sec_name in enumerate(top_vol_sectors):
            with vol_btn_cols[idx]:
                is_active = selected_vol_sector == sec_name
                btn_label = f"● {sec_name}" if is_active else sec_name
                if st.button(btn_label, key=f"vol_sec_{sec_name}",
                             use_container_width=True):
                    if selected_vol_sector == sec_name:
                        st.session_state["vol_selected_sector"] = None
                    else:
                        st.session_state["vol_selected_sector"] = sec_name
                    st.rerun()

        st.plotly_chart(
            chart_volatility_trend(
                vol_hist_data,
                use_ewma=use_ewma,
                selected_sector=st.session_state.get("vol_selected_sector", None),
            ),
            use_container_width=True,
        )

        # ── 3D Explorer Section ──
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div class="sec-hdr">3D Market Explorer — Interactive Visualization</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="math-note">'
            'Map 5 dimensions: X, Y, Z axes + colour + size. '
            'Rotate, zoom, and pan to explore multi-dimensional market structure.'
            '</div>',
            unsafe_allow_html=True,
        )

        dim_options = {
            "volume_today_chf": "Volume (CHF)",
            "price_change_pct": "Δ Price %",
            "volatility_daily": "Volatility σ",
            "amihud_daily": "Amihud λ",
            "trades_today": "Trades",
            "anomaly_score": "Anomaly Score",
            "spread_log_hl": "Spread ln(H/L)",
            "log_returns": "Log Returns ln(r)",
            "off_book_pct": "Off-Book %",
            "price_last": "Last Price",
            "volume_today_units": "Volume (Units)",
            "trade_duration_min": "Trade Duration (min)",
        }
        dim_keys = list(dim_options.keys())

        d3c1, d3c2, d3c3, d3c4, d3c5 = st.columns(5)
        with d3c1:
            x_sel = st.selectbox("X-Axis", dim_keys, index=0,
                                  format_func=lambda k: dim_options[k], key="3d_x")
        with d3c2:
            y_sel = st.selectbox("Y-Axis", dim_keys, index=1,
                                  format_func=lambda k: dim_options[k], key="3d_y")
        with d3c3:
            z_sel = st.selectbox("Z-Axis", dim_keys, index=2,
                                  format_func=lambda k: dim_options[k], key="3d_z")
        with d3c4:
            color_sel = st.selectbox("Colour", dim_keys, index=5,
                                      format_func=lambda k: dim_options[k], key="3d_c")
        with d3c5:
            size_sel = st.selectbox("Size", dim_keys, index=4,
                                     format_func=lambda k: dim_options[k], key="3d_s")

        opt1, opt2 = st.columns(2)
        with opt1:
            use_log = st.checkbox(
                "Apply log₁₀ transform (recommended for skewed distributions)",
                value=False,
                key="3d_log",
            )
        with opt2:
            rm_outliers = st.checkbox(
                "Remove outliers (clip to 1st–99th percentile)",
                value=True,
                key="3d_outliers",
            )

        st.plotly_chart(
            chart_3d_explorer(
                analytics_df, x_sel, y_sel, z_sel, color_sel, size_sel,
                use_log=use_log, remove_outliers=rm_outliers,
            ),
            use_container_width=True,
        )

    # ══════════════════════════════════════════
    # TAB 4 — Anomaly Monitor
    # ══════════════════════════════════════════
    with tab4:
        total = len(latest)
        clean = int((latest["anomaly_score"] == 0).sum())
        watch = int((latest["anomaly_score"] == 1).sum())
        alert_n = int((latest["anomaly_score"] == 2).sum())
        critical_n = int(latest["anomaly_score"].isin([3, 4]).sum())
        severe_n = int(latest["anomaly_score"].isin([5, 6]).sum())
        extreme_n = int((latest["anomaly_score"] >= 7).sum())

        # ── Clickable Risk Summary cards ──
        st.markdown('<div class="sec-hdr">Risk Summary — Click to Filter</div>',
                    unsafe_allow_html=True)

        risk_tiers = [
            ("Clean",    clean,    "#28A745", "#155724", [0]),
            ("Watch",    watch,    "#FFC107", "#664D03", [1]),
            ("Alert",    alert_n,  "#FD7E14", "#6A3200", [2]),
            ("Critical", critical_n, "#DC3545", "#58151C", [3, 4]),
            ("Severe",   severe_n, "#7D1128", "#4A0E1E", [5, 6]),
            ("Extreme",  extreme_n, "#4A0010", "#3A0010", [7]),
        ]

        rc = st.columns(len(risk_tiers))
        selected_tier = st.session_state.get("anomaly_tier", None)

        for col_idx, (lbl, val, border, txt_col, scores) in enumerate(risk_tiers):
            with rc[col_idx]:
                is_active = selected_tier == lbl
                active_style = f"border: 2px solid {border}; box-shadow: 0 0 8px {border}40;" if is_active else ""
                pct = val / total * 100 if total > 0 else 0
                st.markdown(
                    f'<div class="kpi-card" style="border-top-color:{border};{active_style}">'
                    f'<div class="kpi-label">{lbl}</div>'
                    f'<div class="kpi-value" style="color:{txt_col};font-size:1.6rem">{val}</div>'
                    f'<div class="kpi-sub">{pct:.1f}% of market</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button(f"Show {lbl}", key=f"risk_{lbl}", use_container_width=True):
                    if selected_tier == lbl:
                        st.session_state["anomaly_tier"] = None
                    else:
                        st.session_state["anomaly_tier"] = lbl
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Anomaly Severity Treemap (replaces old score distribution) ──
        st.markdown(
            '<div class="sec-hdr">Anomaly Severity Map — Interactive Breakdown</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="math-note">'
            'S<sub>anomaly</sub> = 3·𝟙(V &gt; 1.5·V̄₃₀) + 2·𝟙(N &gt; 1.5·N̄₃₀) + 2·𝟙(|ΔP| &gt; 5%)'
            '&nbsp;&nbsp;∈ {0, 2, 3, 4, 5, 7} &nbsp;·&nbsp; '
            'Weights: volume=3, activity=2, price_gap=2'
            '</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(chart_anomaly_severity_treemap(latest), use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Filtered alerts table ──
        selected_tier = st.session_state.get("anomaly_tier", None)
        if selected_tier and selected_tier in SEVERITY_TIERS:
            tier_scores = SEVERITY_TIERS[selected_tier]
            alerts = latest[latest["anomaly_score"].isin(tier_scores)].sort_values(
                "anomaly_score", ascending=False
            )
            hdr_text = f"{selected_tier} Alerts — {len(alerts)} Securities"
        else:
            alerts = latest[latest["anomaly_score"] >= 1].sort_values(
                "anomaly_score", ascending=False
            )
            hdr_text = f"All Active Alerts — {len(alerts)} Securities"

        st.markdown(f'<div class="sec-hdr">{hdr_text}</div>', unsafe_allow_html=True)

        if alerts.empty:
            st.success("✓  No anomalies detected in this category.")
        else:
            # Detailed anomaly table with trigger flags
            display = alerts.head(min(80, len(alerts)))
            arows = ""
            for _, r in display.iterrows():
                pct = r.get("price_change_pct", 0)
                score = int(r.get("anomaly_score", 0))
                date = r["Datum"].strftime("%d.%m.%Y") if pd.notna(r.get("Datum")) else "—"
                flags = []
                if r.get("volume_spike", False):
                    flags.append("Vol↑")
                if r.get("activity_spike", False):
                    flags.append("Act↑")
                if r.get("price_gap", False):
                    flags.append("Gap")
                flag_str = ", ".join(flags) if flags else "—"
                arows += (
                    f"<tr>"
                    f"<td class='isin'><a href='https://www.otc-x.ch/security/{r['Isin']}' "
                    f"target='_blank' style='color:#B22222;text-decoration:none;'>"
                    f"{r['Isin']}</a></td>"
                    f"<td class='left' style='font-family:Inter;font-weight:500;"
                    f"color:#1A1A2E;'>{str(r.get('Name',''))[:30]}</td>"
                    f"<td class='sektor left'>{str(r.get('Sektor',''))[:20]}</td>"
                    f"<td>{date}</td>"
                    f"<td>{fmt_chf(r.get('volume_today_chf', 0))}</td>"
                    f"<td>{int(r.get('trades_today', 0))}</td>"
                    f"<td class='{pct_cls(pct)}'>{fmt_pct(pct)}</td>"
                    f"<td>{r.get('volatility_daily', 0):.4f}</td>"
                    f"<td>{score_badge(score)}</td>"
                    f"<td style='font-size:0.72rem;color:#343A40;'>{flag_str}</td>"
                    f"</tr>"
                )
            ahtml = (
                "<div style='overflow-x:auto'>"
                "<table class='anomaly-detail-table'>"
                "<thead><tr>"
                "<th class='left'>ISIN</th>"
                "<th class='left'>Security</th>"
                "<th class='left'>Sector</th>"
                "<th>Date</th>"
                "<th>Volume (CHF)</th>"
                "<th>Trades</th>"
                "<th>Δ Price</th>"
                "<th>Volatility σ</th>"
                "<th>Severity</th>"
                "<th>Triggers</th>"
                "</tr></thead>"
                f"<tbody>{arows}</tbody>"
                "</table></div>"
            )
            st.markdown(ahtml, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
