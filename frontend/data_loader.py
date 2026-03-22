from typing import NamedTuple

import pandas as pd
import streamlit as st

from otcx_paths import DATA_DIR


class MarketDataset(NamedTuple):
    history: pd.DataFrame
    latest: pd.DataFrame

    @property
    def latest_date(self) -> str:
        if self.history.empty:
            return "—"
        return self.history["Datum"].max().strftime("%d.%m.%Y")


@st.cache_data(ttl=3600)
def load_data() -> MarketDataset:
    path = DATA_DIR / "daily_metrics.parquet"
    if not path.exists():
        return MarketDataset(pd.DataFrame(), pd.DataFrame())

    df = pd.read_parquet(path)
    df["Datum"] = pd.to_datetime(df["Datum"])

    latest = df.sort_values("Datum").groupby("Isin", as_index=False).last()

    hist_off_book = df.groupby("Isin")["off_book_pct"].mean()
    latest["off_book_pct"] = latest["Isin"].map(hist_off_book)

    return MarketDataset(df, latest)

