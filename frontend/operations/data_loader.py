import streamlit as st
import pandas as pd
from pathlib import Path


@st.cache_data(ttl=3600)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
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
