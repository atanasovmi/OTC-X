"""
OTC-X Market Intelligence Dashboard
Professional Swiss OTC market analytics platform
"""

import streamlit as st
import pandas as pd
import numpy as np

from frontend.config import SEVERITY_TIERS
from frontend.styles import inject_css
from frontend.utils import fmt_chf, fmt_num, fmt_pct, pct_cls, score_badge
from frontend.data_loader import load_data
from frontend.charts import (
    chart_market_activity,
    chart_sector_treemap,
    chart_top_movers,
    chart_volume_by_sector,
    chart_scatter_volume_price,
    chart_amihud_by_sector,
    chart_volatility_trend,
    chart_correlation_heatmap,
    chart_anomaly_severity_treemap,
    chart_security_history,
    chart_3d_explorer,
)
from frontend.components import (
    render_header,
    render_kpis,
    render_market_table,
    render_native_dataframe,
)

# Page Configuration
st.set_page_config(
    page_title="OTC-X Market Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


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
    # Shared compact sort-label markup and responsive column layouts
    market_filter_cols = [2, 1, 1, 0.9]
    # market_filter_cols: [search, sector, sort field, row count]

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
            st.plotly_chart(chart_market_activity(df_hist), use_container_width=True, theme=None)
        with col_tree:
            st.markdown('<div class="sec-hdr">Sector Allocation by Volume</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_sector_treemap(latest), use_container_width=True, theme=None)

        st.markdown("<br>", unsafe_allow_html=True)
        col_mov, col_vol = st.columns(2)
        with col_mov:
            st.markdown('<div class="sec-hdr">Top Movers — Price Change %</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_top_movers(latest), use_container_width=True, theme=None)
        with col_vol:
            st.markdown('<div class="sec-hdr">Volume by Sector (CHF)</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(chart_volume_by_sector(latest), use_container_width=True, theme=None)

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
            'Browse, filter and download raw data straight from the metrics engine for offline analysis. '
            'Click any <strong style="color:#B22222;">ISIN</strong> to view the security on '
            '<a href="https://www.otc-x.ch" target="_blank" style="color:#B22222;">otc-x.ch</a>.'
            '</div>',
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
                f'<div style="font-size:0.72rem;color:#1A1A2E;padding-top:0.6rem;">'
                f'Showing <strong>{n_display}</strong> of <strong>{len(df_filt)}</strong> '
                f'securities · {len(csv_available)} columns available for export'
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
                            use_container_width=True, theme=None)

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
                use_container_width=True, theme=None,
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
                            use_container_width=True, theme=None)
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
                            use_container_width=True, theme=None)

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
                             use_container_width=True):
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
            use_container_width=True, theme=None,
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
            use_container_width=True, theme=None,
        )

    # ══════════════════════════════════════════
    # TAB 4 — Anomaly Monitor
    # ══════════════════════════════════════════
    with tab4:
        total = len(latest)
        clean = int((latest["anomaly_score"] == 0).sum())
        alert_n = int((latest["anomaly_score"].isin([1, 2])).sum())
        critical_n = int(latest["anomaly_score"].isin([3, 4]).sum())
        severe_n = int(latest["anomaly_score"].isin([5, 6]).sum())
        extreme_n = int((latest["anomaly_score"] >= 7).sum())

        # ── Clickable Risk Summary cards ──
        st.markdown('<div class="sec-hdr">Risk Summary — Click to Filter</div>',
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
        st.plotly_chart(chart_anomaly_severity_treemap(latest), use_container_width=True, theme=None)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Filtered alerts table ──
        selected_tier = st.session_state.get("anomaly_tier", None)
        if selected_tier and selected_tier in SEVERITY_TIERS:
            tier_scores = SEVERITY_TIERS[selected_tier]
            alerts = latest[latest["anomaly_score"].isin(tier_scores)].copy()
            hdr_text = f"{selected_tier} Alerts — {len(alerts)} Securities"
        else:
            alerts = latest[latest["anomaly_score"] >= 1].copy()
            hdr_text = f"All Active Alerts — {len(alerts)} Securities"

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
