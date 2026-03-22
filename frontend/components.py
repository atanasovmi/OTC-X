"""
OTC-X UI Components Module
Streamlit rendering functions for dashboard components
"""

import streamlit as st
import pandas as pd
from html import escape as _esc
from .utils import fmt_chf, fmt_num, fmt_pct, pct_cls, score_badge, flag_dot


def render_header(latest_date: str) -> None:
    """Render the OTC-X dashboard header with logo and status indicator."""
    st.markdown(
        f"""
        <div class="otcx-header">
          <div>
            <div class="otcx-logo">OTC<span>|X</span></div>
            <div class="otcx-tagline">Market Intelligence Platform</div>
          </div>
          <div style="margin-left:auto;display:flex;align-items:center;gap:2rem;">
            <span class="live-dot"><span class="dot"></span> Live</span>
            <span style="font-size:0.72rem;color:#1A1A2E;">
              Last data: <strong>{latest_date}</strong>
            </span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(latest: pd.DataFrame) -> None:
    """Render 5-column KPI card row summarizing market snapshot."""
    total_vol   = latest["volume_today_chf"].sum()
    total_trades = int(latest["trades_today"].sum())
    active       = int((latest["trades_today"] > 0).sum())
    total_sec    = len(latest)
    vol_spikes   = int(latest["volume_spike"].sum())
    act_spikes   = int(latest["activity_spike"].sum())
    critical     = int((latest["anomaly_score"] >= 3).sum())
    alert_low    = int((latest["anomaly_score"].isin([1, 2])).sum())
    df_chg       = latest[latest["price_change_pct"] != 0]
    avg_chg      = df_chg["price_change_pct"].mean() if not df_chg.empty else 0.0
    advancing    = int((latest["price_change_pct"] > 0).sum())
    declining    = int((latest["price_change_pct"] < 0).sum())

    c = st.columns(5)
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
        ("Anomaly Alerts", str(critical + alert_low),
         f'<span class="bdg bdg-critical">{critical} Critical</span>&nbsp;'
         f'<span class="bdg bdg-alert">{alert_low} Alert</span>'),
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
    """Render a compact HTML table with key market metrics for top N securities."""
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


def render_native_dataframe(df: pd.DataFrame, n: int = 50) -> None:
    """Render a full-width custom HTML table for the Market Data tab.

    Produces a styled table matching the existing ``.mkt-table`` aesthetic
    with all parquet columns, proper formatting, and meaningful colour
    accents (ISIN links, price-change colouring, score badges, flag dots).

    Parameters
    ----------
    df : pd.DataFrame
        Filtered market-data snapshot.
    n : int, optional
        Maximum number of rows to display (default 50).
    """
    display = df.head(n)

    # ── Column spec: (parquet_col, header_label, align, formatter) ──
    # Formatter receives the cell value and row; returns HTML string.
    def _f_isin(v: str, _r: pd.Series) -> str:
        safe = _esc(str(v))
        return (f"<a href='https://www.otc-x.ch/security/{safe}' "
                f"target='_blank'>{safe}</a>")

    def _f_name(v: str, _r: pd.Series) -> str:
        return _esc(str(v)[:34]) if pd.notna(v) else "—"

    def _f_sektor(v: str, _r: pd.Series) -> str:
        return _esc(str(v)[:22]) if pd.notna(v) else "—"

    def _f_date(v, _r: pd.Series) -> str:
        return v.strftime("%d.%m.%Y") if pd.notna(v) else "—"

    def _f_chf(v, _r: pd.Series) -> str:
        return fmt_chf(v)

    def _f_pct(v, _r: pd.Series) -> str:
        cls = pct_cls(v)
        return f"<span class='{cls}'>{fmt_pct(v)}</span>"

    def _f_int(v, _r: pd.Series) -> str:
        return fmt_num(v, dec=0) if pd.notna(v) else "—"

    def _f_d2(v, _r: pd.Series) -> str:
        return f"{float(v):.2f}" if pd.notna(v) else "—"

    def _f_d4(v, _r: pd.Series) -> str:
        return f"{float(v):.4f}" if pd.notna(v) else "—"

    def _f_d6(v, _r: pd.Series) -> str:
        return f"{float(v):.6f}" if pd.notna(v) else "—"

    def _f_d1(v, _r: pd.Series) -> str:
        return f"{float(v):.1f}" if pd.notna(v) else "—"

    def _f_pct_plain(v, _r: pd.Series) -> str:
        return f"{float(v):.2f}%" if pd.notna(v) else "—"

    def _f_badge(v, _r: pd.Series) -> str:
        return score_badge(int(v)) if pd.notna(v) else "—"

    def _f_flag(v, _r: pd.Series) -> str:
        return flag_dot(bool(v))

    def _f_vol_num(v, _r: pd.Series) -> str:
        return fmt_num(v, dec=0) if pd.notna(v) else "—"

    cols: list[tuple[str, str, str, str, object]] = [
        # (key, header, th_class, td_class, formatter)
        ("Isin",                "ISIN",             "left", "isin",  _f_isin),
        ("Name",                "Security",         "left", "name left", _f_name),
        ("Sektor",              "Sector",           "left", "sektor left", _f_sektor),
        ("Datum",               "Date",             "",     "",      _f_date),
        ("price_last",          "Last",             "",     "",      _f_chf),
        ("price_change_pct",    "Δ%",               "",     "",      _f_pct),
        ("volume_today_chf",    "Vol (CHF)",        "",     "",      _f_chf),
        ("volume_today_units",  "Vol (Units)",      "",     "",      _f_vol_num),
        ("trades_today",        "Trades",           "",     "",      _f_int),
        ("price_first",         "First",            "",     "",      _f_chf),
        ("price_min",           "Min",              "",     "",      _f_chf),
        ("price_max",           "Max",              "",     "",      _f_chf),
        ("volatility_daily",    "σ Daily",          "",     "",      _f_d4),
        ("volatility_30d_median", "σ 30d",          "",     "",      _f_d4),
        ("amihud_daily",        "λ Daily",          "",     "",      _f_d6),
        ("amihud_30d_median",   "λ 30d",            "",     "",      _f_d6),
        ("spread_log_hl",       "Spread",           "",     "",      _f_d4),
        ("log_returns",         "Log Ret",          "",     "",      _f_d4),
        ("off_book_pct",        "Off-Book",         "",     "",      _f_pct_plain),
        ("trades_30d_median",   "Trd 30d",          "",     "",      _f_d1),
        ("volume_30d_median",   "Vol 30d",          "",     "",      _f_vol_num),
        ("trade_duration_min",  "Dur (min)",        "",     "",      _f_d1),
        ("volume_spike",        "Vol↑",             "",     "flag",  _f_flag),
        ("activity_spike",      "Act↑",             "",     "flag",  _f_flag),
        ("price_gap",           "Gap",              "",     "flag",  _f_flag),
        ("anomaly_score",       "Status",           "",     "",      _f_badge),
    ]

    # Filter to columns actually present
    cols = [c for c in cols if c[0] in display.columns]

    # ── Header ──
    ths = "".join(
        f"<th class='{c[2]}'>{c[1]}</th>" if c[2] else f"<th>{c[1]}</th>"
        for c in cols
    )

    # ── Rows ──
    rows_html = ""
    for _, r in display.iterrows():
        tds = ""
        for key, _hdr, _thcls, tdcls, formatter in cols:
            val = r.get(key)
            cell = formatter(val, r)
            tds += f"<td class='{tdcls}'>{cell}</td>" if tdcls else f"<td>{cell}</td>"
        rows_html += f"<tr>{tds}</tr>"

    html = (
        "<div style='overflow-x:auto;'>"
        "<table class='mkt-table'>"
        f"<thead><tr>{ths}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)
