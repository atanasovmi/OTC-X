import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from frontend import config
from frontend.components import render_header
from frontend.data_loader import load_data
from frontend.layout import (
    render_anomaly_tab,
    render_analytics_tab,
    render_market_data_tab,
    render_overview_tab,
)
from frontend.styles import inject_css


def main() -> None:
    st.set_page_config(**config.PAGE_CONFIG)
    inject_css()

    dataset = load_data()
    if dataset.history.empty:
        st.error(
            "No data available. Run `python run_backend.py` to populate the data pipeline."
        )
        st.stop()

    render_header(dataset.latest_date)

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "  Overview  ",
            "  Market Data  ",
            "  Analytics  ",
            "  Anomaly Monitor  ",
        ]
    )

    with tab1:
        render_overview_tab(dataset.history, dataset.latest)
    with tab2:
        render_market_data_tab(dataset.history, dataset.latest)
    with tab3:
        render_analytics_tab(dataset.history, dataset.latest)
    with tab4:
        render_anomaly_tab(dataset.history, dataset.latest)


if __name__ == "__main__":
    main()
