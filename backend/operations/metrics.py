"""OTC-X Liquidity Metrics Engine.

Computes daily liquidity metrics from raw trade data for 243 Swiss OTC
securities.  This module is the **quantitative core** of the pipeline,
transforming consolidated trade records into risk-relevant signals
suitable for institutional dashboards and anomaly detection.

Input
-----
- ``data/master_trades.parquet`` — ≈133 k trades spanning 20+ years.
- ``data/securities.csv`` — ISIN → Name / Sektor mapping.

Output
------
- ``data/daily_metrics.parquet`` — one row per ISIN per trading day.

Metrics computed
----------------
1. **Price Change (%)** — daily price movement (first → last).
2. **Log Returns** — natural log of the intraday price ratio.
3. **Daily Volatility** — standard deviation of intraday prices.
4. **Amihud Illiquidity** — price impact per CHF million traded.
5. **Spread Proxy** — log high-low spread estimate.
6. **Trade Intensity** — number of trades per day.
7. **Trade Duration** — maximum gap between consecutive trades (min).

Plus: 30-trading-day rolling medians and composite anomaly flags.
"""

import logging
import polars as pl
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Tunable parameters ──────────────────────────────────────────────
ROLLING_WINDOW_DAYS  = 30    # Trading-day window for rolling medians
SPIKE_MULTIPLIER     = 1.5   # Volume/activity spike threshold (× median)
PRICE_GAP_PCT        = 5.0   # Minimum |price_change_pct| for a gap flag
WEIGHT_VOLUME        = 3     # Anomaly score contribution: volume spike
WEIGHT_ACTIVITY      = 2     # Anomaly score contribution: activity spike
WEIGHT_PRICE_GAP     = 2     # Anomaly score contribution: price gap


def parse_time_to_minutes(zeit_col: pl.Expr) -> pl.Expr:
    """Convert a ``Zeit`` string column to minutes since midnight.

    Splits on ``':'`` and combines the hour and minute components into
    a single floating-point value representing minutes past 00:00.
    Seconds (if present in ``HH:MM:SS`` format) are silently ignored.

    Parameters
    ----------
    zeit_col : pl.Expr
        Polars expression referencing a ``Utf8`` column whose values
        are formatted as ``"HH:MM"`` or ``"HH:MM:SS"``.

    Returns
    -------
    pl.Expr
        Float64 expression — minutes since midnight.
    """
    return (
        zeit_col
        .str.split(":")
        .list.get(0).cast(pl.Float64) * 60  # Hours to minutes
        + zeit_col.str.split(":").list.get(1).cast(pl.Float64)  # Minutes
    )


def compute_daily_aggregates(df_trades: pl.DataFrame) -> pl.DataFrame:
    """Aggregate raw trades into daily metrics per security.

    Groups trades by ISIN and date, computing trade counts, volume
    totals, price bounds, intraday volatility, off-book percentages,
    and the maximum gap between consecutive trades.

    Parameters
    ----------
    df_trades : pl.DataFrame
        Raw trade-level DataFrame with columns: ``Isin``, ``Datum``,
        ``Zeit``, ``Kurs``, ``Volumen``, ``Off Book``.

    Returns
    -------
    pl.DataFrame
        One row per ISIN per trading day with aggregated metrics
        including ``trades_today``, ``volume_today_units``,
        ``volume_today_chf``, ``price_min/max/first/last``,
        ``volatility_daily``, ``trade_duration_min``, and
        ``off_book_pct``.
    """
    # Add minutes column for trade duration calculation
    df_with_minutes = df_trades.with_columns(
        parse_time_to_minutes(pl.col("Zeit")).alias("time_minutes")
    )
    
    # Sort by time within each day to get proper first/last
    df_sorted = df_with_minutes.sort(["Isin", "Datum", "time_minutes"])
    
    # Daily aggregation
    df_daily = df_sorted.group_by(["Isin", "Datum"]).agg([
        # Trade intensity
        pl.len().cast(pl.UInt32).alias("trades_today"),
        
        # Volume
        pl.col("Volumen").sum().alias("volume_today_units"),
        (pl.col("Volumen") * pl.col("Kurs")).sum().alias("volume_today_chf"),
        
        # Price bounds
        pl.col("Kurs").min().alias("price_min"),
        pl.col("Kurs").max().alias("price_max"),
        pl.col("Kurs").first().alias("price_first"),
        pl.col("Kurs").last().alias("price_last"),
        
        # Volatility (std dev of prices within day)
        pl.col("Kurs").std().fill_null(0.0).alias("volatility_daily"),
        
        # Trade duration: max gap between consecutive trades
        # For single trades, this will be null/0
        pl.col("time_minutes").diff().max().fill_null(0.0).alias("trade_duration_min"),
        
        # Off-book percentage
        (pl.col("Off Book").sum().cast(pl.Float64) / pl.len() * 100).alias("off_book_pct"),
    ])
    
    return df_daily


def compute_liquidity_metrics(df_daily: pl.DataFrame) -> pl.DataFrame:
    """Derive liquidity metrics from daily price and volume aggregates.

    Adds the following columns:

    * ``price_change_pct`` — percentage change from first to last price.
    * ``log_returns`` — ``ln(price_last / price_first)``.
    * ``spread_log_hl`` — ``ln(price_max / price_min)``, a proxy for
      the bid-ask spread.
    * ``amihud_daily`` — Amihud illiquidity ratio:
      ``|log_returns| / volume_chf * 10^6``.  Guarded against
      division by zero (returns ``None`` when volume is zero).

    Parameters
    ----------
    df_daily : pl.DataFrame
        Daily aggregated DataFrame produced by
        :func:`compute_daily_aggregates`.

    Returns
    -------
    pl.DataFrame
        Input DataFrame augmented with the four liquidity columns.
    """
    df_metrics = df_daily.with_columns([
        # Price change (%)
        ((pl.col("price_last") - pl.col("price_first")) / pl.col("price_first") * 100)
        .fill_nan(0.0)
        .fill_null(0.0)
        .alias("price_change_pct"),
        
        # Log returns
        (pl.col("price_last") / pl.col("price_first"))
        .log()
        .fill_nan(0.0)
        .fill_null(0.0)
        .alias("log_returns"),
        
        # Spread proxy: log(high/low)
        (pl.col("price_max") / pl.col("price_min"))
        .log()
        .fill_nan(0.0)
        .fill_null(0.0)
        .alias("spread_log_hl"),
    ])
    
    # Amihud: needs log_returns, computed separately to avoid double calculation
    df_metrics = df_metrics.with_columns([
        # Amihud illiquidity: |log_returns| / volume_chf * 10^6
        # Guard against division by zero
        pl.when(pl.col("volume_today_chf") > 0)
        .then(
            pl.col("log_returns").abs() / pl.col("volume_today_chf") * 1_000_000
        )
        .otherwise(None)
        .alias("amihud_daily"),
    ])
    
    return df_metrics


def compute_rolling_baselines(df_metrics: pl.DataFrame) -> pl.DataFrame:
    """Compute 30-trading-day rolling medians for key metrics.

    Uses **trading days** (not calendar days): each row represents a
    day on which the security actually traded, so a window of 30 means
    the last 30 sessions with activity for that ISIN.

    Rolling medians are computed for:

    * ``trades_today`` → ``trades_30d_median``
    * ``volume_today_chf`` → ``volume_30d_median``
    * ``volatility_daily`` → ``volatility_30d_median``
    * ``amihud_daily`` → ``amihud_30d_median``

    Parameters
    ----------
    df_metrics : pl.DataFrame
        DataFrame with daily metrics produced by
        :func:`compute_liquidity_metrics`.

    Returns
    -------
    pl.DataFrame
        Input DataFrame augmented with four ``*_30d_median`` columns.

    Notes
    -----
    ``min_samples=1`` ensures that newly listed securities with fewer
    than 30 trading days still receive a baseline estimate.
    """
    # Sort by date within each ISIN before computing rolling stats
    df_sorted = df_metrics.sort(["Isin", "Datum"])
    
    # Compute rolling medians per ISIN
    df_rolling = df_sorted.with_columns([
        pl.col("trades_today")
        .cast(pl.Float64)
        .rolling_median(window_size=ROLLING_WINDOW_DAYS, min_samples=1)
        .over("Isin")
        .alias("trades_30d_median"),

        pl.col("volume_today_chf")
        .rolling_median(window_size=ROLLING_WINDOW_DAYS, min_samples=1)
        .over("Isin")
        .alias("volume_30d_median"),

        pl.col("volatility_daily")
        .rolling_median(window_size=ROLLING_WINDOW_DAYS, min_samples=1)
        .over("Isin")
        .alias("volatility_30d_median"),

        pl.col("amihud_daily")
        .rolling_median(window_size=ROLLING_WINDOW_DAYS, min_samples=1)
        .over("Isin")
        .alias("amihud_30d_median"),
    ])
    
    return df_rolling


def compute_anomaly_flags(df_rolling: pl.DataFrame) -> pl.DataFrame:
    """Flag anomalous trading activity by deviation from baselines.

    Three binary flags are created and combined into a weighted
    composite anomaly score (range 0–7):

    +----------------+------------------------------------------+--------+
    | Flag           | Condition                                | Weight |
    +================+==========================================+========+
    | volume_spike   | volume > SPIKE_MULTIPLIER × 30d median   | 3      |
    +----------------+------------------------------------------+--------+
    | activity_spike | trades > SPIKE_MULTIPLIER × 30d median   | 2      |
    +----------------+------------------------------------------+--------+
    | price_gap      | |price_change_pct| > PRICE_GAP_PCT       | 2      |
    +----------------+------------------------------------------+--------+

    Parameters
    ----------
    df_rolling : pl.DataFrame
        DataFrame with rolling baselines produced by
        :func:`compute_rolling_baselines`.

    Returns
    -------
    pl.DataFrame
        Input DataFrame augmented with ``volume_spike``,
        ``activity_spike``, ``price_gap`` (all ``Boolean``), and
        ``anomaly_score`` (``UInt8``, 0–7).
    """
    df_anomaly = df_rolling.with_columns([
        # Volume spike: exceeds rolling median by multiplier
        (pl.col("volume_today_chf") > pl.col("volume_30d_median") * SPIKE_MULTIPLIER)
        .fill_null(False)
        .alias("volume_spike"),

        # Activity spike: exceeds rolling median by multiplier
        (pl.col("trades_today").cast(pl.Float64) > pl.col("trades_30d_median") * SPIKE_MULTIPLIER)
        .fill_null(False)
        .alias("activity_spike"),

        # Price gap: absolute change exceeds threshold
        (pl.col("price_change_pct").abs() > PRICE_GAP_PCT)
        .fill_null(False)
        .alias("price_gap"),
    ])
    
    # Compute weighted anomaly score (0-7 range)
    df_anomaly = df_anomaly.with_columns([
        (
            pl.col("volume_spike").cast(pl.UInt8) * WEIGHT_VOLUME
            + pl.col("activity_spike").cast(pl.UInt8) * WEIGHT_ACTIVITY
            + pl.col("price_gap").cast(pl.UInt8) * WEIGHT_PRICE_GAP
        ).alias("anomaly_score")
    ])
    
    return df_anomaly


def compute_daily_metrics(df_trades: pl.DataFrame) -> pl.DataFrame:
    """Run the full metrics pipeline on raw trade data.

    Orchestrates the four-step transformation:

    1. **Daily aggregation** — group trades by ISIN × date.
    2. **Liquidity metrics** — derive price change, log returns,
       Amihud illiquidity, and spread proxy.
    3. **Rolling baselines** — 30-trading-day medians per ISIN.
    4. **Anomaly detection** — flag volume spikes, activity surges,
       and price gaps; compute composite score.

    Parameters
    ----------
    df_trades : pl.DataFrame
        Raw trade-level DataFrame (output of
        ``build_master_parquet``).

    Returns
    -------
    pl.DataFrame
        Complete daily metrics with anomaly scores — one row per
        ISIN per trading day.
    """
    logger.info("    Step 1/4: Daily aggregation...")
    df_daily = compute_daily_aggregates(df_trades)
    logger.info("             %s daily observations", f"{len(df_daily):,}")

    logger.info("    Step 2/4: Liquidity metrics...")
    df_metrics = compute_liquidity_metrics(df_daily)

    logger.info("    Step 3/4: Rolling baselines (%d trading days)...", ROLLING_WINDOW_DAYS)
    df_rolling = compute_rolling_baselines(df_metrics)

    logger.info("    Step 4/4: Anomaly detection...")
    df_anomaly = compute_anomaly_flags(df_rolling)
    
    return df_anomaly


def main() -> None:
    """Entry point for the metrics engine.

    Loads the master trades Parquet and the securities metadata CSV,
    runs the full metrics pipeline (:func:`compute_daily_metrics`),
    enriches the output with security name and sector, and writes the
    final ``daily_metrics.parquet`` to disk.

    Raises
    ------
    FileNotFoundError
        If ``master_trades.parquet`` or ``securities.csv`` is
        missing from ``backend/data/``.
    """
    start_time = datetime.now()
    
    logger.info("=" * 70)
    logger.info("OTC-X Liquidity Metrics Engine - Starting")
    logger.info("Timestamp: %s", start_time.strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 70)
    
    # Setup paths relative to script location
    script_dir = Path(__file__).resolve().parent
    trades_path = script_dir.parent / "data" / "master_trades.parquet"
    securities_path = script_dir.parent / "data" / "securities.csv"
    output_path = script_dir.parent / "data" / "daily_metrics.parquet"
    
    try:
        # 1. Load Data
        logger.info("[1/4] Loading input data...")
        logger.info("      Trades: %s", trades_path.resolve())
        df_trades = pl.read_parquet(trades_path)
        logger.info("      -> %s trades loaded (%d ISINs)", f"{len(df_trades):,}", df_trades['Isin'].n_unique())

        logger.info("      Securities: %s", securities_path.resolve())
        df_sec = pl.read_csv(
            securities_path,
            schema_overrides={"VALOR": pl.String},  # Avoid int parsing issues
            truncate_ragged_lines=True  # Handle any ragged lines
        )
        logger.info("      -> %s securities loaded (%d sectors)", f"{len(df_sec):,}", df_sec['SEKTOR'].n_unique())
        
        # 2. Compute Metrics
        logger.info("[2/4] Computing liquidity metrics...")
        df_metrics = compute_daily_metrics(df_trades)
        
        # 3. Enrich with Metadata
        logger.info("[3/4] Enriching with security metadata...")
        df_final = df_metrics.join(
            df_sec.select(["ISIN", "NAME", "SEKTOR"]),
            left_on="Isin",
            right_on="ISIN",
            how="left"
        )
        
        # Rename to consistent casing
        df_final = df_final.rename({"NAME": "Name", "SEKTOR": "Sektor"})
        
        # Reorder columns for clarity
        column_order = [
            "Isin", "Name", "Sektor", "Datum",
            "trades_today", "volume_today_units", "volume_today_chf",
            "price_min", "price_max", "price_first", "price_last",
            "price_change_pct", "log_returns", "volatility_daily",
            "amihud_daily", "spread_log_hl", "trade_duration_min", "off_book_pct",
            "trades_30d_median", "volume_30d_median", "volatility_30d_median", "amihud_30d_median",
            "volume_spike", "activity_spike", "price_gap", "anomaly_score"
        ]
        df_final = df_final.select(column_order)
        
        # Handle missing metadata gracefully
        missing_meta = df_final.filter(pl.col("Name").is_null()).select("Isin").unique()
        if len(missing_meta) > 0:
            logger.warning("      [!] %d ISINs have no metadata (Name/Sektor will be null)", len(missing_meta))

        logger.info("      -> Final shape: %s", df_final.shape)
        
        # 4. Save Output
        logger.info("[4/4] Saving output...")
        df_final.write_parquet(output_path, compression="snappy")
        output_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info("      -> Written to: %s", output_path.resolve())
        logger.info("      -> Size: %.2f MB", output_size_mb)
        
        # Summary
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("=" * 70)
        logger.info("SUCCESS! Pipeline completed.")
        logger.info("=" * 70)
        logger.info("Total rows:       %s", f"{len(df_final):,}")
        logger.info("Unique ISINs:     %d", df_final['Isin'].n_unique())
        logger.info("Unique Sectors:   %d", df_final['Sektor'].n_unique())
        logger.info("Date range:       %s to %s", df_final['Datum'].min(), df_final['Datum'].max())
        logger.info("Elapsed time:     %.1f seconds", elapsed)

        # Schema printout
        logger.info("Output Schema:")
        for col, dtype in df_final.schema.items():
            logger.info("  %-25s %s", col, dtype)
        
        # Sample anomalies
        high_anomaly = df_final.filter(pl.col("anomaly_score") >= 5).sort("Datum", descending=True)
        if len(high_anomaly) > 0:
            logger.info("High-anomaly observations (score >= 5): %s total", f"{len(high_anomaly):,}")
            for row in high_anomaly.head(5).iter_rows(named=True):
                logger.info("  %s | %s | Score: %d | Price Change: %.2f%%",
                            row['Datum'], row['Isin'], row['anomaly_score'], row['price_change_pct'])
        
    except FileNotFoundError as e:
        logger.error("FILE NOT FOUND: %s", e)
        logger.error("   Ensure master_trades.parquet and securities.csv exist in data/")
        exit(1)
    except Exception as e:
        logger.error("CRITICAL ERROR: %s: %s", type(e).__name__, e)
        exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
