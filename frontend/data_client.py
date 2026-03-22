"""
OTC-X Data Client
Data loading and caching for the frontend dashboard
"""

import streamlit as st
import pandas as pd
from pathlib import Path


@st.cache_data(ttl=3600)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load daily metrics data from backend and return full history + latest snapshot.

    Returns:
        tuple: (df_full, df_latest) where:
            - df_full: Complete historical metrics
            - df_latest: Latest snapshot per ISIN with off_book_pct historical mean
    """
    # Dynamic path resolution: frontend module -> backend/data/
    path = Path(__file__).parent.parent / "backend" / "data" / "daily_metrics.parquet"

    if not path.exists():
        return pd.DataFrame(), pd.DataFrame()

    df = pd.read_parquet(path)
    df["Datum"] = pd.to_datetime(df["Datum"])

    latest = df.sort_values("Datum").groupby("Isin", as_index=False).last()

    # Off-book trades are rare: on >99% of trading days all ISINs have
    # off_book_pct == 0, so the single-day snapshot has zero variance and
    # produces NaN correlations. Replace with the historical mean per ISIN
    # to surface the cross-sectional signal.
    hist_off_book = df.groupby("Isin")["off_book_pct"].mean()
    latest["off_book_pct"] = latest["Isin"].map(hist_off_book)

    return df, latest
