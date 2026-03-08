"""
OTC-X Liquidity Intelligence Terminal
Production-ready Streamlit application for the Swiss OTC-X market.
"""

import polars as pl
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pyarrow  # noqa: F401 – required for Parquet reading
from pathlib import Path

# ─── Page Configuration ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="OTC-X | Liquidity Intelligence Terminal",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  /* ── Global Reset ── */
  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background: #060a12 !important;
    color: #c8d6e8 !important;
  }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: #0b1220; }
  ::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 2px; }

  /* ── Main container ── */
  .main .block-container {
    padding: 0.75rem 1.5rem 1rem 1.5rem !important;
    max-width: 100% !important;
  }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: rgba(11, 20, 38, 0.96) !important;
    border-right: 1px solid rgba(30, 80, 140, 0.35) !important;
  }
  [data-testid="stSidebar"] * { color: #a8bcd4 !important; }
  [data-testid="stSidebar"] .stMarkdown h2,
  [data-testid="stSidebar"] .stMarkdown h3 {
    color: #4da6ff !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  /* ── Terminal header bar ── */
  .terminal-header {
    background: linear-gradient(135deg, rgba(13,25,50,0.98) 0%, rgba(8,18,40,0.98) 100%);
    border: 1px solid rgba(30,100,200,0.3);
    border-radius: 6px;
    padding: 0.6rem 1.2rem;
    margin-bottom: 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    backdrop-filter: blur(12px);
  }
  .terminal-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.05rem;
    font-weight: 600;
    color: #4da6ff;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .terminal-sub {
    font-size: 0.68rem;
    color: #4a7aab;
    letter-spacing: 0.08em;
    font-family: 'JetBrains Mono', monospace;
  }
  .status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #00d4aa;
    box-shadow: 0 0 8px #00d4aa;
    flex-shrink: 0;
    animation: pulse-dot 2s infinite;
  }
  @keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  /* ── KPI / HUD cards ── */
  .kpi-card {
    background: rgba(13, 26, 52, 0.75);
    border: 1px solid rgba(30, 90, 160, 0.35);
    border-radius: 8px;
    padding: 0.65rem 0.9rem;
    backdrop-filter: blur(8px);
    transition: border-color 0.2s;
    height: 100%;
  }
  .kpi-card:hover { border-color: rgba(77, 166, 255, 0.5); }
  .kpi-label {
    font-size: 0.6rem;
    font-weight: 600;
    color: #4a7aab;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
    font-family: 'JetBrains Mono', monospace;
  }
  .kpi-value {
    font-size: 1.45rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    color: #e0ecff;
    line-height: 1;
  }
  .kpi-value-sm {
    font-size: 1.0rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    color: #e0ecff;
    line-height: 1;
  }
  .kpi-sub {
    font-size: 0.58rem;
    color: #4a7aab;
    margin-top: 0.2rem;
    font-family: 'JetBrains Mono', monospace;
  }
  .kpi-up   { color: #00d4aa !important; }
  .kpi-down { color: #ff4d6d !important; }
  .kpi-warn { color: #ffb347 !important; }
  .kpi-neutral { color: #7bafd4 !important; }

  /* ── Section titles ── */
  .section-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    font-weight: 600;
    color: #3a6a9e;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    border-left: 2px solid #1e5a9e;
    padding-left: 0.5rem;
    margin-bottom: 0.4rem;
  }

  /* ── Alert / anomaly badges ── */
  .badge {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem;
    font-weight: 600;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .badge-red  { background: rgba(255,77,109,0.15); color: #ff4d6d; border: 1px solid rgba(255,77,109,0.4); }
  .badge-amber{ background: rgba(255,179,71,0.12); color: #ffb347; border: 1px solid rgba(255,179,71,0.4); }
  .badge-teal { background: rgba(0,212,170,0.12);  color: #00d4aa; border: 1px solid rgba(0,212,170,0.4); }
  .badge-blue { background: rgba(77,166,255,0.12); color: #4da6ff; border: 1px solid rgba(77,166,255,0.4); }

  /* ── Dataframe table ── */
  [data-testid="stDataFrame"] {
    border: 1px solid rgba(30,80,140,0.4) !important;
    border-radius: 6px;
    overflow: hidden;
  }

  /* ── Plotly chart bg ── */
  .stPlotlyChart > div { border-radius: 8px; overflow: hidden; }

  /* ── Divider ── */
  hr { border-color: rgba(30,80,140,0.25) !important; margin: 0.4rem 0 !important; }

  /* ── Streamlit widgets in sidebar ── */
  [data-testid="stSidebar"] .stSlider > div > div > div { background: #1e4a7a !important; }
  [data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] {
    background: rgba(30,90,160,0.4) !important;
  }

  /* ── Hide Streamlit branding ── */
  #MainMenu, footer, header { visibility: hidden; }
  [data-testid="stToolbar"] { display: none; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ─── Constants ────────────────────────────────────────────────────────────────
_MAX_HUD_NAME_LEN = 28      # max chars for anomaly name in HUD card
_MAX_CHART_NAME_LEN = 22    # max chars for security names in comparison charts

# ─── Chart theme defaults ─────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(6,10,18,0)",
    plot_bgcolor="rgba(11,18,34,0.7)",
    font=dict(family="Inter, sans-serif", color="#8aaac8", size=11),
    margin=dict(l=10, r=10, t=30, b=10),
    coloraxis_colorbar=dict(
        tickfont=dict(color="#8aaac8", size=9),
        title_font=dict(color="#8aaac8"),
        thickness=10,
    ),
    legend=dict(
        bgcolor="rgba(11,18,34,0.8)",
        bordercolor="rgba(30,80,140,0.3)",
        borderwidth=1,
        font=dict(color="#8aaac8", size=9),
    ),
)

# ─── Data Loading ─────────────────────────────────────────────────────────────
DATA_PATH = Path(__file__).parent / "data" / "daily_metrics.parquet"


@st.cache_data(ttl=300)
def load_latest_state() -> pl.DataFrame:
    """Load parquet and filter to the latest Datum per ISIN."""
    raw = pl.read_parquet(DATA_PATH, use_pyarrow=True)

    # Keep only the most recent record per ISIN
    latest = (
        raw.sort("Datum", descending=True)
        .group_by("Isin")
        .first()
        .sort("anomaly_score", descending=True)
    )

    # Ensure display name falls back to ISIN if Name is null/blank
    latest = latest.with_columns(
        pl.when(
            pl.col("Name").is_null()
            | (pl.col("Name").fill_null("").str.strip_chars() == "")
        )
        .then(pl.col("Isin"))
        .otherwise(pl.col("Name"))
        .alias("display_name"),
        pl.when(
            pl.col("Sektor").is_null()
            | (pl.col("Sektor").fill_null("").str.strip_chars() == "")
        )
        .then(pl.lit("Unclassified"))
        .otherwise(pl.col("Sektor"))
        .alias("sektor_clean"),
    )
    return latest


df_all = load_latest_state()
sectors_all = sorted(df_all["sektor_clean"].unique().to_list())

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h2>◈ OTC-X TERMINAL</h2><p style='font-size:0.6rem;color:#2e5478;letter-spacing:0.1em;'>"
        "SWISS OTC LIQUIDITY INTELLIGENCE</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    st.markdown("<h3>🔍 GLOBAL SEARCH</h3>", unsafe_allow_html=True)
    search_term = st.text_input(
        "", placeholder="ISIN, Name, or Sector…", label_visibility="collapsed"
    )

    st.markdown("<h3>⚙ FILTERS</h3>", unsafe_allow_html=True)

    selected_sectors = st.multiselect(
        "Sector",
        options=sectors_all,
        default=[],
        placeholder="All sectors",
    )

    vol_min, vol_max = (
        float(df_all["volume_today_chf"].min() or 0),
        float(df_all["volume_today_chf"].max() or 1e9),
    )
    vol_filter = st.slider(
        "Volume (CHF) range",
        min_value=0.0,
        max_value=min(vol_max, 5_000_000.0),
        value=(0.0, min(vol_max, 5_000_000.0)),
        step=5_000.0,
        format="CHF %.0f",
    )

    anomaly_min = st.slider("Min Anomaly Score", 0, 3, 0, step=1)

    show_spikes_only = st.checkbox("Volume Spikes Only", value=False)
    show_activity_only = st.checkbox("Activity Spikes Only", value=False)
    show_gap_only = st.checkbox("Price Gaps Only", value=False)

    st.markdown("---")
    st.markdown("<h3>📊 DISPLAY OPTIONS</h3>", unsafe_allow_html=True)
    top_n = st.slider("Top-N for comparison chart", 5, 30, 15, step=5)
    cube_max_points = st.slider("3D Cube max points", 50, 500, 200, step=50)

# ─── Apply Filters ────────────────────────────────────────────────────────────
df = df_all.clone()

if search_term:
    s = search_term.lower()
    df = df.filter(
        pl.col("Isin").str.to_lowercase().str.contains(s)
        | pl.col("display_name").str.to_lowercase().str.contains(s)
        | pl.col("sektor_clean").str.to_lowercase().str.contains(s)
    )

if selected_sectors:
    df = df.filter(pl.col("sektor_clean").is_in(selected_sectors))

df = df.filter(
    (pl.col("volume_today_chf") >= vol_filter[0])
    & (pl.col("volume_today_chf") <= vol_filter[1])
)
df = df.filter(pl.col("anomaly_score") >= anomaly_min)

if show_spikes_only:
    df = df.filter(pl.col("volume_spike"))
if show_activity_only:
    df = df.filter(pl.col("activity_spike"))
if show_gap_only:
    df = df.filter(pl.col("price_gap"))

n_filtered = len(df)

# ─── Header Bar ───────────────────────────────────────────────────────────────
latest_date = df_all["Datum"].max()

st.markdown(
    f"""
    <div class="terminal-header">
      <div class="status-dot"></div>
      <span class="terminal-title">OTC-X Liquidity Intelligence Terminal</span>
      <span class="terminal-sub">│ SWISS OTC MARKET &nbsp;│&nbsp; AS OF {latest_date} &nbsp;│&nbsp; {n_filtered} SECURITIES IN VIEW</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── HUD ──────────────────────────────────────────────────────────────────────
total_vol = float(df["volume_today_chf"].sum() or 0)
total_trades = int(df["trades_today"].sum() or 0)
n_anomalies = int((df["anomaly_score"] >= 2).sum())
n_vol_spikes = int(df["volume_spike"].sum())
n_act_spikes = int(df["activity_spike"].sum())
n_price_gaps = int(df["price_gap"].sum())
avg_volatility = float(df["volatility_daily"].mean() or 0)
avg_amihud = float(df["amihud_daily"].mean() or 0)
pct_pos = int((df["price_change_pct"] > 0).sum()) if n_filtered > 0 else 0
pct_neg = int((df["price_change_pct"] < 0).sum()) if n_filtered > 0 else 0
top_anomaly = df.filter(pl.col("anomaly_score") == df["anomaly_score"].max()).head(1)
top_anomaly_name = (
    top_anomaly["display_name"].item() if len(top_anomaly) > 0 else "—"
)
top_anomaly_score = (
    int(top_anomaly["anomaly_score"].item()) if len(top_anomaly) > 0 else 0
)

hud_cols = st.columns([1.4, 1, 1, 1, 1, 1, 1, 1, 1.5])

def kpi(col, label, value, sub="", cls="kpi-value"):
    col.markdown(
        f"""<div class="kpi-card">
          <div class="kpi-label">{label}</div>
          <div class="{cls}">{value}</div>
          <div class="kpi-sub">{sub}</div>
        </div>""",
        unsafe_allow_html=True,
    )

kpi(hud_cols[0], "Market Volume", f"CHF {total_vol/1e6:.1f}M", f"{total_trades:,} trades today")
kpi(hud_cols[1], "Securities", f"{n_filtered:,}", f"of {len(df_all):,} universe")
kpi(hud_cols[2], "Anomaly Alerts",
    f'<span class="kpi-warn">{n_anomalies}</span>',
    f"score ≥ 2",
    cls="kpi-value")
kpi(hud_cols[3], "Vol Spikes",
    f'<span class="kpi-up">{n_vol_spikes}</span>',
    f"+ {n_act_spikes} activity",
    cls="kpi-value")
kpi(hud_cols[4], "Price Gaps",
    f'<span class="kpi-down">{n_price_gaps}</span>',
    "gap flags",
    cls="kpi-value")
kpi(hud_cols[5], "Avg Volatility", f"{avg_volatility:.4f}", "daily σ")
kpi(hud_cols[6], "Avg Amihud", f"{avg_amihud:.4f}", "illiquidity ratio")
kpi(hud_cols[7], "Advance/Decline",
    f'<span class="kpi-up">{pct_pos}</span> / <span class="kpi-down">{pct_neg}</span>',
    "▲ up / ▼ down",
    cls="kpi-value-sm")
kpi(hud_cols[8], "Top Anomaly",
    f'<span class="kpi-warn">[{top_anomaly_score}]</span>',
    top_anomaly_name[:_MAX_HUD_NAME_LEN] if top_anomaly_name else "—",
    cls="kpi-value-sm")

st.markdown("<br>", unsafe_allow_html=True)

# ─── Row 1: 3D Market Cube + Treemap ─────────────────────────────────────────
st.markdown('<div class="section-title">◈ 3D MARKET CUBE — RISK · ILLIQUIDITY · MOMENTUM</div>', unsafe_allow_html=True)
col_cube, col_tree = st.columns([1.55, 1], gap="small")

with col_cube:
    df_cube = df.sort("volume_today_chf", descending=True).head(cube_max_points)
    pdf = df_cube.to_pandas()
    pdf["anomaly_score"] = pdf["anomaly_score"].astype(int)
    pdf["flag_label"] = (
        pdf["volume_spike"].astype(str) + "/" +
        pdf["activity_spike"].astype(str) + "/" +
        pdf["price_gap"].astype(str)
    ).map({
        "True/True/True": "all-flags",
        "True/True/False": "vol+act",
        "True/False/True": "vol+gap",
        "False/True/True": "act+gap",
        "True/False/False": "vol-spike",
        "False/True/False": "act-spike",
        "False/False/True": "price-gap",
        "False/False/False": "clean",
    })

    fig_cube = px.scatter_3d(
        pdf,
        x="volatility_daily",
        y="amihud_daily",
        z="price_change_pct",
        color="anomaly_score",
        size="volume_today_chf",
        symbol="flag_label",
        hover_name="display_name",
        hover_data={
            "Isin": True,
            "sektor_clean": True,
            "trades_today": True,
            "volume_today_chf": ":.0f",
            "price_change_pct": ":.3f",
            "volatility_daily": ":.4f",
            "amihud_daily": ":.6f",
            "anomaly_score": True,
        },
        color_continuous_scale=[
            [0.0, "#1a3a6e"],
            [0.33, "#1e8fd5"],
            [0.66, "#ffb347"],
            [1.0, "#ff4d6d"],
        ],
        opacity=0.82,
        size_max=22,
        title="",
    )
    fig_cube.update_layout(
        **PLOTLY_LAYOUT,
        scene=dict(
            xaxis=dict(
                title="Volatility σ",
                backgroundcolor="rgba(8,16,32,0.8)",
                gridcolor="rgba(30,80,140,0.2)",
                color="#4a7aab",
            ),
            yaxis=dict(
                title="Amihud Illiquidity",
                backgroundcolor="rgba(8,16,32,0.8)",
                gridcolor="rgba(30,80,140,0.2)",
                color="#4a7aab",
            ),
            zaxis=dict(
                title="Price Change %",
                backgroundcolor="rgba(8,16,32,0.8)",
                gridcolor="rgba(30,80,140,0.2)",
                color="#4a7aab",
            ),
            bgcolor="rgba(6,10,18,0.9)",
        ),
        height=480,
    )
    st.plotly_chart(fig_cube, use_container_width=True)

with col_tree:
    st.markdown('<div class="section-title">◈ SECTOR INTELLIGENCE — VOLUME CHF</div>', unsafe_allow_html=True)
    df_tree = df.group_by("sektor_clean").agg([
        pl.sum("volume_today_chf").alias("vol_sum"),
        pl.mean("anomaly_score").alias("avg_anomaly"),
        pl.len().alias("count"),
    ]).sort("vol_sum", descending=True)
    pdf_tree = df_tree.to_pandas()
    pdf_tree["sektor_clean"] = pdf_tree["sektor_clean"].fillna("Unclassified")
    pdf_tree["avg_anomaly"] = pdf_tree["avg_anomaly"].fillna(0)

    fig_tree = px.treemap(
        pdf_tree,
        path=["sektor_clean"],
        values="vol_sum",
        color="avg_anomaly",
        hover_data={"count": True, "avg_anomaly": ":.2f"},
        color_continuous_scale=[
            [0.0, "#0d1a36"],
            [0.4, "#1e5a9e"],
            [0.7, "#c47a00"],
            [1.0, "#cc2240"],
        ],
        title="",
    )
    fig_tree.update_traces(
        textfont=dict(family="Inter, sans-serif", size=11, color="#ddeeff"),
        marker_line_color="rgba(6,10,18,0.8)",
        marker_line_width=1.5,
        texttemplate="<b>%{label}</b><br>%{value:,.0f} CHF<br>n=%{customdata[0]}",
    )
    fig_tree.update_layout(**{**PLOTLY_LAYOUT, "margin": dict(l=5, r=5, t=5, b=5)}, height=480)
    st.plotly_chart(fig_tree, use_container_width=True)

# ─── Row 2: Current vs 30d Median comparison ─────────────────────────────────
st.markdown('<div class="section-title">◈ CURRENT vs 30D MEDIAN — TOP SECURITIES BY VOLUME</div>', unsafe_allow_html=True)

col_bar1, col_bar2 = st.columns(2, gap="small")

with col_bar1:
    top_df = df.sort("volume_today_chf", descending=True).head(top_n).to_pandas()
    top_df["display_name"] = top_df["display_name"].str[:_MAX_CHART_NAME_LEN]

    fig_vol = go.Figure()
    fig_vol.add_trace(go.Bar(
        y=top_df["display_name"],
        x=top_df["volume_today_chf"],
        name="Today",
        orientation="h",
        marker_color="#1e8fd5",
        marker_line_width=0,
        opacity=0.9,
    ))
    fig_vol.add_trace(go.Bar(
        y=top_df["display_name"],
        x=top_df["volume_30d_median"],
        name="30d Median",
        orientation="h",
        marker_color="rgba(100,160,220,0.35)",
        marker_line_color="rgba(100,160,220,0.6)",
        marker_line_width=1,
        opacity=0.85,
    ))
    fig_vol.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Volume CHF — Today vs 30d Median", font=dict(size=11, color="#5a8ab4")),
        barmode="overlay",
        height=340,
        xaxis=dict(gridcolor="rgba(30,80,140,0.2)", color="#4a7aab", tickfont=dict(size=9)),
        yaxis=dict(gridcolor="rgba(30,80,140,0.2)", color="#8aaac8", tickfont=dict(size=9)),
    )
    st.plotly_chart(fig_vol, use_container_width=True)

with col_bar2:
    fig_trades = go.Figure()
    fig_trades.add_trace(go.Bar(
        y=top_df["display_name"],
        x=top_df["trades_today"].astype(float),
        name="Today",
        orientation="h",
        marker_color="#00d4aa",
        marker_line_width=0,
        opacity=0.9,
    ))
    fig_trades.add_trace(go.Bar(
        y=top_df["display_name"],
        x=top_df["trades_30d_median"],
        name="30d Median",
        orientation="h",
        marker_color="rgba(0,200,160,0.3)",
        marker_line_color="rgba(0,200,160,0.6)",
        marker_line_width=1,
        opacity=0.85,
    ))
    fig_trades.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Trades — Today vs 30d Median", font=dict(size=11, color="#3a9a80")),
        barmode="overlay",
        height=340,
        xaxis=dict(gridcolor="rgba(30,80,140,0.2)", color="#4a7aab", tickfont=dict(size=9)),
        yaxis=dict(gridcolor="rgba(30,80,140,0.2)", color="#8aaac8", tickfont=dict(size=9)),
    )
    st.plotly_chart(fig_trades, use_container_width=True)

# ─── Row 3: Volatility & Amihud comparison ───────────────────────────────────
col_v1, col_v2 = st.columns(2, gap="small")

with col_v1:
    fig_vola = go.Figure()
    fig_vola.add_trace(go.Scatter(
        x=top_df["display_name"],
        y=top_df["volatility_daily"],
        name="Today",
        mode="lines+markers",
        line=dict(color="#ff4d6d", width=1.5),
        marker=dict(size=5, color="#ff4d6d"),
    ))
    fig_vola.add_trace(go.Scatter(
        x=top_df["display_name"],
        y=top_df["volatility_30d_median"],
        name="30d Median",
        mode="lines+markers",
        line=dict(color="rgba(255,77,109,0.35)", width=1.5, dash="dot"),
        marker=dict(size=4, color="rgba(255,77,109,0.5)"),
    ))
    fig_vola.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Volatility σ — Today vs 30d Median", font=dict(size=11, color="#9a4060")),
        height=260,
        xaxis=dict(gridcolor="rgba(30,80,140,0.2)", color="#4a7aab", tickfont=dict(size=8), tickangle=35),
        yaxis=dict(gridcolor="rgba(30,80,140,0.2)", color="#8aaac8", tickfont=dict(size=9)),
    )
    st.plotly_chart(fig_vola, use_container_width=True)

with col_v2:
    fig_ami = go.Figure()
    fig_ami.add_trace(go.Scatter(
        x=top_df["display_name"],
        y=top_df["amihud_daily"],
        name="Today",
        mode="lines+markers",
        line=dict(color="#ffb347", width=1.5),
        marker=dict(size=5, color="#ffb347"),
    ))
    fig_ami.add_trace(go.Scatter(
        x=top_df["display_name"],
        y=top_df["amihud_30d_median"],
        name="30d Median",
        mode="lines+markers",
        line=dict(color="rgba(255,179,71,0.35)", width=1.5, dash="dot"),
        marker=dict(size=4, color="rgba(255,179,71,0.5)"),
    ))
    fig_ami.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Amihud Illiquidity — Today vs 30d Median", font=dict(size=11, color="#8a6020")),
        height=260,
        xaxis=dict(gridcolor="rgba(30,80,140,0.2)", color="#4a7aab", tickfont=dict(size=8), tickangle=35),
        yaxis=dict(gridcolor="rgba(30,80,140,0.2)", color="#8aaac8", tickfont=dict(size=9)),
    )
    st.plotly_chart(fig_ami, use_container_width=True)

# ─── Row 4: Anomaly score distribution + scatter price_change vs volume ───────
col_dist, col_scatter = st.columns(2, gap="small")

with col_dist:
    st.markdown('<div class="section-title">◈ ANOMALY SCORE DISTRIBUTION</div>', unsafe_allow_html=True)
    anomaly_counts = (
        df.group_by("anomaly_score")
        .agg(pl.len().alias("count"))
        .sort("anomaly_score")
        .to_pandas()
    )
    colors_anom = {0: "#1a3a6e", 1: "#1e8fd5", 2: "#ffb347", 3: "#ff4d6d"}
    fig_dist = px.bar(
        anomaly_counts,
        x="anomaly_score",
        y="count",
        color="anomaly_score",
        color_discrete_map=colors_anom,
        labels={"anomaly_score": "Score", "count": "Securities"},
    )
    fig_dist.update_layout(
        **PLOTLY_LAYOUT,
        height=240,
        showlegend=False,
        xaxis=dict(
            tickmode="array",
            tickvals=[0, 1, 2, 3],
            ticktext=["0 · Clean", "1 · Watch", "2 · Alert", "3 · Critical"],
            color="#4a7aab",
            tickfont=dict(size=9),
            gridcolor="rgba(30,80,140,0.2)",
        ),
        yaxis=dict(gridcolor="rgba(30,80,140,0.2)", color="#8aaac8", tickfont=dict(size=9)),
        bargap=0.35,
    )
    st.plotly_chart(fig_dist, use_container_width=True)

with col_scatter:
    st.markdown('<div class="section-title">◈ PRICE CHANGE % vs VOLUME CHF</div>', unsafe_allow_html=True)
    pdf_sc = df.to_pandas()
    pdf_sc["anomaly_score"] = pdf_sc["anomaly_score"].astype(int)
    fig_sc = px.scatter(
        pdf_sc,
        x="volume_today_chf",
        y="price_change_pct",
        color="anomaly_score",
        size="trades_today",
        hover_name="display_name",
        hover_data={"Isin": True, "sektor_clean": True, "volatility_daily": ":.4f"},
        color_continuous_scale=[
            [0, "#1a3a6e"], [0.33, "#1e8fd5"], [0.66, "#ffb347"], [1, "#ff4d6d"]
        ],
        opacity=0.75,
        size_max=16,
        log_x=True,
    )
    fig_sc.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.15)", line_width=1)
    fig_sc.update_layout(
        **PLOTLY_LAYOUT,
        height=240,
        xaxis=dict(
            title="Volume CHF (log)", gridcolor="rgba(30,80,140,0.2)",
            color="#4a7aab", tickfont=dict(size=9),
        ),
        yaxis=dict(
            title="Price Chg %", gridcolor="rgba(30,80,140,0.2)",
            color="#8aaac8", tickfont=dict(size=9),
        ),
    )
    st.plotly_chart(fig_sc, use_container_width=True)

# ─── Raw Data Feed ────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">◈ LIVE MARKET FEED — RAW DATA</div>', unsafe_allow_html=True)

display_cols = [
    "Isin", "display_name", "sektor_clean", "Datum",
    "trades_today", "volume_today_chf", "price_change_pct",
    "volatility_daily", "amihud_daily",
    "trades_30d_median", "volume_30d_median",
    "volatility_30d_median", "amihud_30d_median",
    "anomaly_score", "volume_spike", "activity_spike", "price_gap",
]

table_df = (
    df.select(display_cols)
    .sort("anomaly_score", descending=True)
    .rename({
        "display_name": "Name",
        "sektor_clean": "Sector",
        "trades_today": "Trades",
        "volume_today_chf": "Volume CHF",
        "price_change_pct": "Δ Price %",
        "volatility_daily": "Vol σ",
        "amihud_daily": "Amihud",
        "trades_30d_median": "Trades 30d",
        "volume_30d_median": "Vol 30d",
        "volatility_30d_median": "Vola 30d",
        "amihud_30d_median": "Amihud 30d",
        "anomaly_score": "⚠ Score",
        "volume_spike": "Vol↑",
        "activity_spike": "Act↑",
        "price_gap": "Gap",
    })
    .to_pandas()
)

# Conditional formatting helper
def color_anomaly(val):
    colors = {0: "#1a3a6e", 1: "#1e5a9e", 2: "#8a5a00", 3: "#6a0020"}
    bg = colors.get(int(val), "#1a3a6e")
    return f"background-color: {bg}; color: white; font-weight: 600; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; text-align: center;"

def color_price(val):
    try:
        v = float(val)
        if v > 0:
            return "color: #00d4aa; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;"
        elif v < 0:
            return "color: #ff4d6d; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;"
    except Exception:
        pass
    return "font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;"

def mono_fmt(val):
    return "font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #8aaac8;"

styled = (
    table_df.style
    .map(color_anomaly, subset=["⚠ Score"])
    .map(color_price, subset=["Δ Price %"])
    .map(mono_fmt, subset=["Volume CHF", "Vol σ", "Amihud", "Trades 30d", "Vol 30d", "Vola 30d", "Amihud 30d"])
    .format({
        "Volume CHF": "{:,.0f}",
        "Δ Price %": "{:+.3f}",
        "Vol σ": "{:.4f}",
        "Amihud": "{:.6f}",
        "Trades 30d": "{:.1f}",
        "Vol 30d": "{:,.0f}",
        "Vola 30d": "{:.4f}",
        "Amihud 30d": "{:.6f}",
        "⚠ Score": "{:d}",
    }, na_rep="—")
    .set_properties(**{
        "background-color": "rgba(8,16,32,0.5)",
        "color": "#8aaac8",
        "border": "1px solid rgba(30,80,140,0.2)",
        "font-size": "0.72rem",
    })
    .set_table_styles([
        {
            "selector": "thead th",
            "props": [
                ("background-color", "rgba(13,26,52,0.95)"),
                ("color", "#4da6ff"),
                ("font-family", "'JetBrains Mono', monospace"),
                ("font-size", "0.62rem"),
                ("letter-spacing", "0.08em"),
                ("text-transform", "uppercase"),
                ("border-bottom", "1px solid rgba(30,100,200,0.4)"),
                ("padding", "6px 8px"),
            ],
        },
        {
            "selector": "tr:hover td",
            "props": [("background-color", "rgba(30,80,140,0.2)")],
        },
    ])
)

st.dataframe(styled, use_container_width=True, height=460)

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style="text-align:center; padding: 0.6rem 0; margin-top: 0.5rem;
                font-family: 'JetBrains Mono', monospace; font-size: 0.58rem;
                color: #2a4a6e; letter-spacing: 0.1em; border-top: 1px solid rgba(30,80,140,0.2);">
      OTC-X LIQUIDITY INTELLIGENCE TERMINAL &nbsp;│&nbsp; SWISS OTC MARKET &nbsp;│&nbsp;
      DATA AS OF {latest_date} &nbsp;│&nbsp; {len(df_all):,} TOTAL RECORDS &nbsp;│&nbsp;
      POWERED BY POLARS · PLOTLY · STREAMLIT
    </div>
    """,
    unsafe_allow_html=True,
)
