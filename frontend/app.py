"""OTC-X Market Intelligence Dashboard — main Streamlit application.

Assembles the four-tab interface (Overview, Market Data, Analytics,
Anomaly Monitor) by composing chart factories, UI components, and the
cached data-loading layer.  This module is the Streamlit entry-point
and must be executed via ``streamlit run frontend/app.py``.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so package imports work
# regardless of whether Streamlit runs this file directly.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st
import pandas as pd
import numpy as np
from html import escape as _esc

from frontend.operations.config import SEVERITY_TIERS
from frontend.operations.styles import inject_css
from frontend.operations.utils import fmt_chf, fmt_num, fmt_pct, pct_cls, score_badge
from frontend.operations.data_loader import load_data
from frontend.operations.charts import (
    chart_market_activity,
    chart_sector_treemap,
    chart_top_movers,
    chart_trades_by_sector,
    chart_scatter_volume_price,
    chart_amihud_by_sector,
    chart_volatility_trend,
    chart_correlation_heatmap,
    chart_anomaly_severity_treemap,
    chart_security_history,
    chart_3d_explorer,
)
from frontend.operations.components import (
    render_header,
    render_kpis,
    render_market_table,
    render_native_dataframe,
)

# Page Configuration
# `page_icon` is intentionally omitted — emoji favicons read as
# unprofessional in a banking context. Streamlit falls back to its
# default neutral favicon, which is fine for now. A branded SVG/PNG
# favicon could be added later via `page_icon="path/to/file.svg"`.
st.set_page_config(
    page_title="OTC-X Market Intelligence — Swiss OTC Liquidity Radar",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main() -> None:
    """Compose and render the full OTC-X dashboard.

    Loads cached data, injects CSS, and builds all four tabs:

    1. **Overview** — KPI cards, market activity, sector treemap, top
       movers, and volume-by-sector bar.
    2. **Market Data** — searchable / sortable data explorer with CSV
       export and per-security detail view.
    3. **Analytics** — correlation heatmap, volume-vs-price scatter,
       Amihud box-plots, rolling volatility, and 3-D explorer.
    4. **Anomaly Monitor** — risk-summary cards, severity treemap, and
       filtered alerts table.

    This function is the single entry-point called at module level.
    """
    inject_css()

    df_hist, latest = load_data()

    if df_hist.empty:
        st.error("No data available. Run `python -m backend.pipeline` to populate the data pipeline.")
        st.stop()

    latest_market_date = df_hist["Datum"].max()
    # Strict "today" slice: rows from the most recent trading day across
    # all ISINs. Used by KPI cards.
    today = df_hist[df_hist["Datum"] == latest_market_date]

    # ── YTD slice (Jan 1 of current year → today) ─────────────────────
    # Powers Top Movers, Sector Treemap, and Trades by Sector.
    # `ytd_panel` is the full multi-row panel (one row per security per
    # trading day in YTD); `ytd_per_isin` is one row per ISIN with
    # `price_change_pct` overridden by YTD return and `volume_today_chf`
    # overridden by YTD CHF sum — chart-compatible drop-in for `latest`.
    year_start = pd.Timestamp(latest_market_date.year, 1, 1)
    ytd_panel = df_hist[df_hist["Datum"] >= year_start]

    if not ytd_panel.empty:
        ytd_sorted = ytd_panel.sort_values("Datum")
        first_per_isin = ytd_sorted.groupby("Isin", as_index=False).first()
        last_per_isin = ytd_sorted.groupby("Isin", as_index=False).last()
        base_price = first_per_isin.set_index("Isin")["price_first"]
        final_price = last_per_isin.set_index("Isin")["price_last"]
        ytd_perf = pd.Series(0.0, index=base_price.index)
        valid = base_price > 0
        ytd_perf[valid] = (final_price[valid] / base_price[valid] - 1) * 100
        per_isin_ytd_vol = ytd_panel.groupby("Isin")["volume_today_chf"].sum()
        ytd_per_isin = last_per_isin.copy()
        ytd_per_isin["price_change_pct"] = ytd_per_isin["Isin"].map(ytd_perf)
        ytd_per_isin["volume_today_chf"] = ytd_per_isin["Isin"].map(per_isin_ytd_vol)
    else:
        ytd_per_isin = pd.DataFrame(columns=df_hist.columns)

    # ── 30-trading-day rolling window for Tab 4 anomaly views ─────────
    # `risk_view` = latest flagged row per ISIN within the last 30
    # trading days. Captures open active risk without dragging in
    # decade-old stale flags.
    unique_dates = sorted(df_hist["Datum"].unique())
    window_dates = unique_dates[-30:] if len(unique_dates) >= 30 else unique_dates
    min_window_date = window_dates[0] if window_dates else latest_market_date
    window_30d = df_hist[df_hist["Datum"] >= min_window_date]
    flagged_in_window = window_30d[window_30d["anomaly_score"] >= 1]
    if not flagged_in_window.empty:
        risk_view = (
            flagged_in_window
            .sort_values("Datum")
            .groupby("Isin", as_index=False)
            .last()
        )
    else:
        risk_view = pd.DataFrame(columns=df_hist.columns)

    latest_date = latest_market_date.strftime("%d.%m.%Y")
    render_header(latest_date)

    tab1, tab2, tab3, tab4 = st.tabs([
        "  Overview  ",
        "  Market Data  ",
        "  Analytics  ",
        "  Anomaly Monitor  ",
    ])
    # Shared compact sort-label markup and responsive column layouts
    market_filter_cols = [2, 1, 1, 0.9]
    # market_filter_cols: [search, sector, sort field, row count]

    # ══════════════════════════════════════════
    # TAB 1 — Overview
    # ══════════════════════════════════════════
    with tab1:
        # "Active Securities" KPI uses a 30-calendar-day breadth measure
        # so a thin OTC day doesn't make the market look dead.
        active_30d_count = (
            df_hist[df_hist["Datum"] >= latest_market_date - pd.Timedelta(days=30)]
            ["Isin"].nunique()
        )
        render_kpis(today, total_securities=len(latest),
                    active_30d_count=active_30d_count)
        st.markdown("<br>", unsafe_allow_html=True)

        col_act, col_tree = st.columns([3, 2])
        with col_act:
            st.markdown('<div class="sec-hdr">Market Activity — Last 90 Days</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_market_activity(df_hist), width="stretch", theme=None)
        with col_tree:
            st.markdown('<div class="sec-hdr">Sector Allocation — YTD</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_sector_treemap(ytd_per_isin), width="stretch", theme=None)

        st.markdown("<br>", unsafe_allow_html=True)
        col_mov, col_vol = st.columns(2)
        with col_mov:
            st.markdown('<div class="sec-hdr">Top Movers — Performance YTD</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_top_movers(ytd_per_isin), width="stretch", theme=None)
        with col_vol:
            st.markdown('<div class="sec-hdr">Trades by Sector — YTD</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_trades_by_sector(ytd_panel), width="stretch", theme=None)

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
            'Browse, filter and download the full historical metrics panel — '
            '<strong>one row per security per trading day</strong>. '
            'Use the date range filter to scope your export. '
            'Click any <strong style="color:#B22222;">ISIN</strong> to view the security on '
            '<a href="https://www.otc-x.ch" target="_blank" style="color:#B22222;">otc-x.ch</a>.'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Date-range filter ──
        panel_max = df_hist["Datum"].max()
        panel_min = df_hist["Datum"].min()
        date_presets = ["Last 30 days", "Last 90 days", "Last 12 months",
                        "Last 5 years", "All time", "Custom..."]
        fd1, fd2 = st.columns([1, 2])
        with fd1:
            date_preset = st.selectbox(
                "Date range", date_presets, index=2,  # default: Last 12 months
                label_visibility="collapsed",
                key="market_data_date_preset",
            )

        if date_preset == "Last 30 days":
            date_from = panel_max - pd.Timedelta(days=30)
            date_to = panel_max
        elif date_preset == "Last 90 days":
            date_from = panel_max - pd.Timedelta(days=90)
            date_to = panel_max
        elif date_preset == "Last 12 months":
            date_from = panel_max - pd.DateOffset(months=12)
            date_to = panel_max
        elif date_preset == "Last 5 years":
            date_from = panel_max - pd.DateOffset(years=5)
            date_to = panel_max
        elif date_preset == "All time":
            date_from = panel_min
            date_to = panel_max
        else:  # Custom...
            with fd2:
                default_from = (panel_max - pd.DateOffset(months=12)).to_pydatetime().date()
                default_to = panel_max.to_pydatetime().date()
                custom_range = st.date_input(
                    "Custom range",
                    value=(default_from, default_to),
                    min_value=panel_min.to_pydatetime().date(),
                    max_value=panel_max.to_pydatetime().date(),
                    label_visibility="collapsed",
                    key="market_data_custom_range",
                )
                if isinstance(custom_range, tuple) and len(custom_range) == 2:
                    date_from = pd.Timestamp(custom_range[0])
                    date_to = pd.Timestamp(custom_range[1])
                else:
                    # User mid-selection — fall back to default
                    date_from = pd.Timestamp(default_from)
                    date_to = pd.Timestamp(default_to)

        if date_preset != "Custom...":
            with fd2:
                st.markdown(
                    f'<div style="font-size:0.72rem;color:#1A1A2E;padding-top:0.6rem;">'
                    f'Range: <strong>{date_from.date()}</strong> → <strong>{date_to.date()}</strong>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ── Filter controls ──
        fc1, fc2, fc3, fc4 = st.columns(market_filter_cols)
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
                ["Date", "Volume (CHF)", "Trades", "Price Change", "Anomaly Score",
                 "Volatility", "Amihud λ", "Name"],
                label_visibility="collapsed",
            )
        with fc4:
            rows_to_show = st.selectbox(
                "Rows",
                [25, 50, 100, 200, "Max 2,000"],
                index=1,
                label_visibility="collapsed",
            )

        # Source is the full historical panel, scoped by date range.
        df_filt = df_hist[
            (df_hist["Datum"] >= date_from) & (df_hist["Datum"] <= date_to)
        ].copy()
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
            "Date": "Datum",
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
        df_filt = df_filt.sort_values(sort_col, ascending=sort_asc, na_position="last")

        # Render cap: hard limit on what the HTML table displays. The CSV
        # download is unaffected — it always exports the full filtered set.
        RENDER_CAP = 2000
        if rows_to_show == "Max 2,000":
            n_display = min(RENDER_CAP, len(df_filt))
        else:
            n_display = min(int(rows_to_show), len(df_filt))

        # ── Summary bar ──
        n_securities = df_filt["Isin"].nunique() if not df_filt.empty else 0
        n_observations = len(df_filt)
        sum_vol = df_filt["volume_today_chf"].sum() if not df_filt.empty else 0
        sum_trades = int(df_filt["trades_today"].sum()) if not df_filt.empty else 0
        # σ and λ tiles report the *median of per-ISIN means* — robust to
        # the long right tail of high-priced securities. A simple panel
        # mean inflates wildly because a CHF 5000 stock with a CHF 50
        # intraday range contributes σ=50 to every row it appears on,
        # drowning out the typical sub-CHF-2 movement seen on most
        # securities.
        if not df_filt.empty:
            _per_isin_vol = df_filt.groupby("Isin")["volatility_daily"].mean()
            _per_isin_amh = df_filt.groupby("Isin")["amihud_daily"].mean()
            med_vola   = float(_per_isin_vol.median()) if not _per_isin_vol.empty else 0.0
            med_amihud = float(_per_isin_amh.median()) if not _per_isin_amh.empty else 0.0
        else:
            med_vola = med_amihud = 0.0

        # Greek letters need a text-transform:none span override because
        # the tile label applies CSS uppercase, which would convert
        # σ → Σ (sum sign) and λ → Λ (triangle) — wrong glyphs.
        _sigma = '<span style="text-transform:none;">σ</span>'
        _lam   = '<span style="text-transform:none;">λ</span>'

        sm1, sm2, sm3, sm4, sm5 = st.columns(5)
        summary_items = [
            ("Securities", str(n_securities)),
            ("Total Volume", fmt_chf(sum_vol)),
            ("Total Trades", f"{sum_trades:,}"),
            (f"Median {_sigma}", f"{med_vola:.4f}"),
            (f"Median {_lam}", f"{med_amihud:.6f}"),
        ]
        for col, (lbl, val) in zip([sm1, sm2, sm3, sm4, sm5], summary_items):
            with col:
                st.markdown(
                    f'<div style="background:#FFFFFF;border:1px solid #CED4DA;'
                    f'padding:0.6rem 0.9rem;text-align:center;">'
                    f'<div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.1em;color:#1A1A2E;">{lbl}</div>'
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

        csv_filename = (
            f"otcx_market_data_{date_from.strftime('%Y%m%d')}_"
            f"{date_to.strftime('%Y%m%d')}.csv"
        )

        dl1, dl2 = st.columns([1, 4])
        with dl1:
            st.download_button(
                label="⬇ Download CSV",
                data=csv_data.to_csv(index=False).encode("utf-8"),
                file_name=csv_filename,
                mime="text/csv",
                width="stretch",
            )
        with dl2:
            render_note = (
                ""
                if n_observations <= n_display
                else (
                    f' · <em>Table capped at {n_display:,} rows for performance; '
                    f'CSV contains the full filtered set ({n_observations:,} rows).</em>'
                )
            )
            st.markdown(
                f'<div style="font-size:0.72rem;color:#1A1A2E;padding-top:0.6rem;">'
                f'Showing <strong>{n_display:,}</strong> of '
                f'<strong>{n_observations:,}</strong> observations across '
                f'<strong>{n_securities}</strong> securities · '
                f'{len(csv_available)} columns available for export'
                f'{render_note}'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── Data table ──
        render_native_dataframe(df_filt, n=n_display)

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

        # df_filt now has many rows per ISIN — dedupe for the dropdown.
        active_isins = sorted(df_filt["Isin"].unique().tolist())
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
                            width="stretch", theme=None)

            # ── Security summary metrics with math notation ──
            sec_row = latest[latest["Isin"] == sel_isin]
            if not sec_row.empty:
                r = sec_row.iloc[0]
                st.markdown(
                    '<div class="sec-hdr">Key Metrics</div>',
                    unsafe_allow_html=True,
                )
                mc = st.columns(5)
                # Greek letters wrapped to escape the kpi-label CSS uppercase
                _sigma_kpi = '<span style="text-transform:none;">σ</span>'
                _lam_kpi   = '<span style="text-transform:none;">λ</span>'
                metric_items = [
                    ("Last Price", fmt_chf(r.get("price_last", 0)),
                     f"Range: {fmt_chf(r.get('price_min',0))} – {fmt_chf(r.get('price_max',0))}"),
                    ("Daily Volume", fmt_chf(r.get("volume_today_chf", 0)),
                     f"{fmt_num(r.get('volume_today_units',0))} units"),
                    ("Trades", str(int(r.get("trades_today", 0))),
                     f"30d median: {r.get('trades_30d_median',0):.0f}"),
                    (f"Volatility {_sigma_kpi}", f"{r.get('volatility_daily',0):.4f}",
                     f"30d median: {r.get('volatility_30d_median',0):.4f}"),
                    (f"Amihud {_lam_kpi}", f"{r.get('amihud_daily',0):.6f}",
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
        else:
            st.info("No securities match the current filter. Widen the date range or clear search/sector filters.")

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
                help="Off-Book % uses historical averages per ISIN because off-book trades are extremely rare — fewer than 1% of trading days show any variation.",
            )

        # Filter data
        analytics_df = latest.copy()
        if hm_sectors:
            analytics_df = analytics_df[analytics_df["Sektor"].isin(hm_sectors)]

        # ── Correlation Heatmap (full width) ──
        st.markdown(
            f'<div class="math-note">'
            f'ρ(X,Y) = cov(X,Y) / (σ<sub>X</sub> · σ<sub>Y</sub>) '
            f'&nbsp;|&nbsp; Showing {len(analytics_df)} securities'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sec-hdr">Metric Correlation Matrix</div>',
            unsafe_allow_html=True,
        )
        if len(hm_selected) >= 2:
            st.plotly_chart(
                chart_correlation_heatmap(analytics_df, hm_selected),
                width="stretch", theme=None,
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
                            width="stretch", theme=None)
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
                            width="stretch", theme=None)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div class="sec-hdr">Rolling Volatility — Top Sectors</div>',
            unsafe_allow_html=True,
        )

        vol_c1, vol_c2 = st.columns([3, 1])
        with vol_c2:
            show_raw_sma = st.checkbox(
                "Show raw volatility (30d SMA)",
                value=False,
                key="vol_show_raw_sma",
                help="When enabled, display raw 30-day SMA volatility instead of the EWMA-smoothed series.",
            )
        with vol_c1:
            if show_raw_sma:
                st.markdown(
                    '<div class="math-note">'
                    'σ̄<sub>30d</sub> = (1/30) Σ σ<sub>daily</sub>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="math-note">'
                    'Macro-Smoothed: SMA(90) → EWM(120) → EWM(60)'
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
            '<strong>Tip:</strong> Click a sector below to isolate it. Click again to reset.'
            '</div>',
            unsafe_allow_html=True,
        )
        vol_btn_cols = st.columns(len(top_vol_sectors))
        for idx, sec_name in enumerate(top_vol_sectors):
            with vol_btn_cols[idx]:
                is_active = selected_vol_sector == sec_name
                btn_label = f"● {sec_name}" if is_active else sec_name
                if st.button(btn_label, key=f"vol_sec_{sec_name}",
                             width="stretch"):
                    if selected_vol_sector == sec_name:
                        st.session_state["vol_selected_sector"] = None
                    else:
                        st.session_state["vol_selected_sector"] = sec_name
                    st.rerun()

        st.plotly_chart(
            chart_volatility_trend(
                vol_hist_data,
                show_raw_sma=show_raw_sma,
                selected_sector=st.session_state.get("vol_selected_sector", None),
            ),
            width="stretch", theme=None,
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 3D Explorer Section ──
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
            width="stretch", theme=None,
        )

    # ══════════════════════════════════════════
    # TAB 4 — Anomaly Monitor
    # ══════════════════════════════════════════
    with tab4:
        # 30-day rolling window: flagged securities are taken from
        # `risk_view`; Clean count is everything in the universe that did
        # not generate a flag in that window.
        total = len(latest)
        flagged_count = len(risk_view)
        clean = total - flagged_count
        if not risk_view.empty:
            alert_n = int(risk_view["anomaly_score"].isin([1, 2]).sum())
            critical_n = int(risk_view["anomaly_score"].isin([3, 4]).sum())
            severe_n = int(risk_view["anomaly_score"].isin([5, 6]).sum())
            extreme_n = int((risk_view["anomaly_score"] >= 7).sum())
        else:
            alert_n = critical_n = severe_n = extreme_n = 0

        # ── Clickable Risk Summary cards ──
        st.markdown('<div class="sec-hdr">Risk Summary — Last 30 Trading Days · Click to Filter</div>',
                    unsafe_allow_html=True)

        risk_tiers = [
            ("Clean",    clean,    "#1B6B2E", "clean",    [0]),
            ("Alert",    alert_n,  "#FD7E14", "alert",    [1, 2]),
            ("Critical", critical_n, "#DC3545", "critical", [3, 4]),
            ("Severe",   severe_n, "#7D1128", "severe",   [5, 6]),
            ("Extreme",  extreme_n, "#4A0010", "extreme",  [7]),
        ]

        rc = st.columns(len(risk_tiers))
        selected_tier = st.session_state.get("anomaly_tier", None)

        for col_idx, (lbl, val, border, tier_cls, scores) in enumerate(risk_tiers):
            with rc[col_idx]:
                is_active = selected_tier == lbl
                active_style = f"border: 2px solid {border}; box-shadow: 0 0 8px {border}40;" if is_active else ""
                pct = val / total * 100 if total > 0 else 0
                st.markdown(
                    f'<div class="kpi-card" style="border-top-color:{border};{active_style}">'
                    f'<div class="kpi-label">{lbl}</div>'
                    f'<div class="kpi-value kpi-tier-{tier_cls}" style="font-size:1.6rem">{val}</div>'
                    f'<div class="kpi-sub">{pct:.1f}% of market</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button(f"Show {lbl}", key=f"risk_{lbl}", width="stretch"):
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
        st.plotly_chart(chart_anomaly_severity_treemap(risk_view), width="stretch", theme=None)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Filtered alerts table ──
        selected_tier = st.session_state.get("anomaly_tier", None)
        if selected_tier == "Clean":
            # Clean = ISINs not flagged in the 30d window. Show their
            # latest-known state from `latest` (mixed date OK — these
            # rows are not the subject of alerting).
            flagged_isins = set(risk_view["Isin"]) if not risk_view.empty else set()
            alerts = latest[~latest["Isin"].isin(flagged_isins)].copy()
            hdr_text = f"Clean Securities — {len(alerts)} Securities (no flags in last 30 days)"
        elif selected_tier and selected_tier in SEVERITY_TIERS:
            tier_scores = SEVERITY_TIERS[selected_tier]
            alerts = (
                risk_view[risk_view["anomaly_score"].isin(tier_scores)].copy()
                if not risk_view.empty
                else pd.DataFrame()
            )
            hdr_text = f"{selected_tier} Alerts — {len(alerts)} Securities"
        else:
            alerts = risk_view.copy() if not risk_view.empty else pd.DataFrame()
            hdr_text = f"Active Alerts (Last 30 Days) — {len(alerts)} Securities"

        st.markdown(f'<div class="sec-hdr">{hdr_text}</div>', unsafe_allow_html=True)

        if alerts.empty:
            st.success("✓  No anomalies detected in this category.")
        else:
            alert_sort_map = {
                "Severity": "anomaly_score",
                "Volume (CHF)": "volume_today_chf",
                "Trades": "trades_today",
                "Price Change": "price_change_pct",
                "Volatility": "volatility_daily",
                "Date": "Datum",
            }
            alerts = alerts.sort_values("anomaly_score", ascending=False)

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
                safe_isin = _esc(str(r['Isin']))
                safe_name = _esc(str(r.get('Name', ''))[:30])
                safe_sektor = _esc(str(r.get('Sektor', ''))[:20])
                arows += (
                    f"<tr>"
                    f"<td class='isin'><a href='https://www.otc-x.ch/security/{safe_isin}' "
                    f"target='_blank' style='color:#B22222;text-decoration:none;'>"
                    f"{safe_isin}</a></td>"
                    f"<td class='left' style='font-family:Inter;font-weight:500;"
                    f"color:#1A1A2E;'>{safe_name}</td>"
                    f"<td class='sektor left'>{safe_sektor}</td>"
                    f"<td>{date}</td>"
                    f"<td>{fmt_chf(r.get('volume_today_chf', 0))}</td>"
                    f"<td>{int(r.get('trades_today', 0))}</td>"
                    f"<td class='{pct_cls(pct)}'>{fmt_pct(pct)}</td>"
                    f"<td>{r.get('volatility_daily', 0):.4f}</td>"
                    f"<td>{score_badge(score)}</td>"
                    f"<td style='font-size:0.72rem;color:#1A1A2E;'>{flag_str}</td>"
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
                "<th>Volatility <span style='text-transform:none;'>σ</span></th>"
                "<th>Severity</th>"
                "<th>Triggers</th>"
                "</tr></thead>"
                f"<tbody>{arows}</tbody>"
                "</table></div>"
            )
            st.markdown(ahtml, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
