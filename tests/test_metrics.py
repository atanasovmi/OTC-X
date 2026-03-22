import datetime as dt

import polars as pl

from backend.operations import metrics


def _sample_trades() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Isin": ["A", "A", "A", "B", "B"],
            "Datum": [
                dt.date(2024, 1, 2),
                dt.date(2024, 1, 2),
                dt.date(2024, 1, 3),
                dt.date(2024, 1, 2),
                dt.date(2024, 1, 3),
            ],
            "Zeit": ["09:00:00", "10:00:00", "09:30:00", "09:00:00", "09:15:00"],
            "Kurs": [10.0, 12.0, 11.0, 5.0, 5.5],
            "Volumen": [100, 200, 150, 50, 60],
            "Off Book": [0, 1, 0, 0, 0],
        }
    )


def test_parse_time_to_minutes_handles_hours_and_minutes():
    df = pl.DataFrame({"Zeit": ["00:15:00", "09:30:00", "18:45:00"]})
    parsed = df.with_columns(
        metrics.parse_time_to_minutes(pl.col("Zeit")).alias("minutes")
    )
    assert parsed["minutes"].to_list() == [15.0, 570.0, 1125.0]


def test_compute_daily_aggregates_builds_expected_columns():
    daily = metrics.compute_daily_aggregates(_sample_trades())
    assert {"price_first", "price_last", "volume_today_chf", "trades_today"} <= set(
        daily.columns
    )
    a_day1 = daily.filter((pl.col("Isin") == "A") & (pl.col("Datum") == dt.date(2024, 1, 2)))
    assert a_day1.select("trades_today").item() == 2
    assert a_day1.select("volume_today_chf").item() == 3400.0
    assert a_day1.select("off_book_pct").item() == 50.0


def test_compute_liquidity_metrics_and_rolling_medians_are_consistent():
    daily = metrics.compute_daily_aggregates(_sample_trades())
    liq = metrics.compute_liquidity_metrics(daily)
    rolling = metrics.compute_rolling_baselines(liq)

    a_day2 = rolling.filter((pl.col("Isin") == "A") & (pl.col("Datum") == dt.date(2024, 1, 3)))
    # Median over two trading days for ISIN A: trades (2,1) -> 1.5, volume (3400,1650) -> 2525
    assert a_day2.select("trades_30d_median").item() == 1.5
    assert a_day2.select("volume_30d_median").item() == 2525.0


def test_compute_anomaly_flags_scores_price_gap_only():
    daily = metrics.compute_daily_aggregates(_sample_trades())
    liq = metrics.compute_liquidity_metrics(daily)
    rolling = metrics.compute_rolling_baselines(liq)
    anomaly = metrics.compute_anomaly_flags(rolling)

    a_day1 = anomaly.filter((pl.col("Isin") == "A") & (pl.col("Datum") == dt.date(2024, 1, 2)))
    assert a_day1.select("price_gap").item() is True
    assert a_day1.select("volume_spike").item() is False
    assert a_day1.select("activity_spike").item() is False
    assert a_day1.select("anomaly_score").item() == 2

    a_day2 = anomaly.filter((pl.col("Isin") == "A") & (pl.col("Datum") == dt.date(2024, 1, 3)))
    assert a_day2.select("anomaly_score").item() == 0
