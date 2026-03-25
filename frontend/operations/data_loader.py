"""Cached data-loading layer for the OTC-X dashboard.

Reads the daily-metrics Parquet file produced by the backend pipeline,
materialises a *latest-snapshot* DataFrame (one row per ISIN), and
patches rare off-book percentages with historical means so the
cross-sectional signal is preserved even on zero-variance days.

Results are cached for one hour via ``st.cache_data`` to avoid
redundant disk I/O during interactive Streamlit reruns.
"""

import streamlit as st
import pandas as pd
from pathlib import Path


@st.cache_data(ttl=3600)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load daily metrics and derive the latest per-ISIN snapshot.

    Reads ``backend/data/daily_metrics.parquet`` relative to the project
    root. If the file does not exist an empty tuple of DataFrames is
    returned, allowing the caller to display a user-friendly error.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        ``(df_hist, latest)`` where *df_hist* contains the full historical
        panel (all dates × ISINs) and *latest* contains one row per ISIN
        representing the most recent trading day.

    Notes
    -----
    Off-book trade percentages (``off_book_pct``) are overridden with each
    ISIN's historical mean because the single-day snapshot almost always
    shows zero variance, which would produce ``NaN`` correlations.
    """
    path = Path(__file__).resolve().parent.parent.parent / "backend" / "data" / "daily_metrics.parquet"
    if not path.exists():
        return pd.DataFrame(), pd.DataFrame()

    df = pd.read_parquet(path)
    df["Datum"] = pd.to_datetime(df["Datum"])

    latest = df.sort_values("Datum").groupby("Isin", as_index=False).last()

    # Off-book trades are rare: on >99% of trading days all ISINs have
    # off_book_pct == 0, so the single-day snapshot has zero variance and
    # produces NaN correlations.  Replace with the historical mean per ISIN
    # to surface the cross-sectional signal.
    hist_off_book = df.groupby("Isin")["off_book_pct"].mean()
    latest["off_book_pct"] = latest["Isin"].map(hist_off_book)

    return df, latest
