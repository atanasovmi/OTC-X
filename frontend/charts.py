import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from frontend.config import (
    BRAND_RED, BRAND_DARK, GREEN_POS, RED_NEG, BORDER_COL,
    MUTED, PLOTLY_TPL, SECTOR_PALETTE, SEVERITY_TIERS,
)
from frontend.utils import _hex_to_rgba, fmt_chf, fmt_pct


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
                     tickfont=dict(color="#1A1A2E"),
                     title_font=dict(color="#1A1A2E"))
    fig.update_yaxes(title_text="Trades", showgrid=False, secondary_y=True,
                     tickfont=dict(color="#1A1A2E"),
                     title_font=dict(color="#1A1A2E"))
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
                font=dict(size=10, color="#1A1A2E"),
                title=dict(text="Sector", font=dict(size=10, color="#1A1A2E")),
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
                           show_raw_sma: bool = False,
                           selected_sector: str | None = None) -> go.Figure:
    """Rolling volatility chart with optional EWMA smoothing and
    hover-to-isolate interaction.

    Parameters
    ----------
    show_raw_sma : If True, show raw 30-day SMA instead of EWMA-smoothed series.
    selected_sector : If set, highlight only this sector and dim others.
    """
    top_sectors = (
        df_hist.groupby("Sektor")["trades_today"]
        .sum()
        .nlargest(n)
        .index.tolist()
    )
    df = df_hist[df_hist["Sektor"].isin(top_sectors)].copy()
    agg = (
        df.groupby(["Datum", "Sektor"], as_index=False)
        .agg(volatility_daily=("volatility_daily", "mean"))
    )
    agg = agg.sort_values("Datum")

    palette = px.colors.qualitative.D3

    fig = go.Figure()
    for i, sector in enumerate(top_sectors):
        grp = agg[agg["Sektor"] == sector].copy()

        if show_raw_sma:
            grp["smoothed"] = grp["volatility_daily"].rolling(30, min_periods=1).mean()
        else:
            # Triple-smoothing for macro-trend-only curves:
            # 1) 90-day rolling mean removes daily/weekly noise
            # 2) EWM(span=120) flattens to broad structural trends
            # 3) Second EWM(span=60) removes residual wobble
            sma = grp["volatility_daily"].rolling(90, min_periods=1).mean()
            ew1 = sma.ewm(span=120, adjust=False).mean()
            grp["smoothed"] = ew1.ewm(span=60, adjust=False).mean()

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

    smoothing_label = "30-Day SMA" if show_raw_sma else "Macro-Smoothed"
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

    # Map scores to the same tier names used by the KPI cards
    score_to_tier: dict[int, str] = {}
    for tier, scores in SEVERITY_TIERS.items():
        if tier == "Clean":
            continue
        for s in scores:
            score_to_tier[s] = tier
    df["severity"] = df["anomaly_score"].map(score_to_tier).fillna("Unknown")
    df["label"] = df["Name"].fillna(df["Isin"]).str[:28]
    df["score_size"] = df["anomaly_score"]  # already >= 1 from filter above

    severity_order = ["Alert", "Critical", "Severe", "Extreme"]
    df["sev_order"] = df["severity"].map({s: i for i, s in enumerate(severity_order)}).fillna(99)
    df = df.sort_values(["sev_order", "anomaly_score"], ascending=[False, False])

    # Discrete colours matching the KPI big-number text colours
    # "(?)": Plotly's internal key for the root node in hierarchical treemaps
    tier_colors = {
        "(?)":      "#F5F6F8",
        "Alert":    "#7D3C00",
        "Critical": "#721C24",
        "Severe":   "#7D1128",
        "Extreme":  "#4A0010",
    }

    fig = px.treemap(
        df,
        path=["severity", "label"],
        values="score_size",
        color="severity",
        color_discrete_map=tier_colors,
        custom_data=["Isin", "Sektor", "anomaly_score", "volume_today_chf",
                      "price_change_pct", "volatility_daily"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b>",
        textfont=dict(family="Inter", size=10, color="white"),
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
        **_base_layout(height=380),
        showlegend=False,
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

    # Price + rolling 30-day σ band (std of closing prices, not intraday vol)
    rolling_std = sec["price_last"].rolling(
        30, min_periods=5,  # require ≥5 observations for a meaningful std
    ).std().fillna(0)
    upper = sec["price_last"] + rolling_std
    lower = sec["price_last"] - rolling_std
    fig.add_trace(
        go.Scatter(
            x=pd.concat([sec["Datum"], sec["Datum"][::-1]]),
            y=pd.concat([upper, lower[::-1]]),
            fill="toself",
            fillcolor="rgba(178,34,34,0.10)",
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
            legend=dict(orientation="h", y=1.05, font=dict(size=10, color="#1A1A2E")),
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
