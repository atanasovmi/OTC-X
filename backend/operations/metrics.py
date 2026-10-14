"""OTC-X Liquidity Metrics Engine.

Computes daily liquidity metrics from raw trade data for 243 Swiss OTC
securities.  This module is the **quantitative core** of the pipeline,
transforming consolidated trade records into risk-relevant signals
suitable for institutional dashboards and anomaly detection.

Input
-----
- ``data/master_trades.parquet`` — ≈133 k trades spanning 20+ years.
- ``data/security_registry.csv`` — durable active/historical ISIN metadata.
- Previous validated master/metric snapshot — preserves untouched history.

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
import sys
from datetime import datetime

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)

# ── Tunable parameters ──────────────────────────────────────────────
ROLLING_WINDOW_DAYS  = 30    # Trading-day window for rolling medians
SPIKE_MULTIPLIER     = 1.5   # Volume/activity spike threshold (× median)
PRICE_GAP_PCT        = 5.0   # Minimum |price_change_pct| for a gap flag
WEIGHT_VOLUME        = 3     # Anomaly score contribution: volume spike
WEIGHT_ACTIVITY      = 2     # Anomaly score contribution: activity spike
WEIGHT_PRICE_GAP     = 2     # Anomaly score contribution: price gap

DAILY_AGGREGATE_COLUMNS = [
    "Isin", "Datum", "trades_today", "volume_today_units", "volume_today_chf",
    "price_min", "price_max", "price_first", "price_last", "volatility_daily",
    "trade_duration_min", "off_book_pct",
]


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


def compute_daily_aggregates(df_trades: pl.DataFrame, *, stable_ties: bool = False) -> pl.DataFrame:
    """Aggregate raw trades into daily metrics per security.

    Groups trades by ISIN and date, computing trade counts, volume
    totals, price bounds, intraday volatility, off-book percentages,
    and the maximum gap between consecutive trades.

    Parameters
    ----------
    df_trades : pl.DataFrame
        Raw trade-level DataFrame with columns: ``Isin``, ``Datum``,
        ``Zeit``, ``Kurs``, ``Volumen``, ``Off Book``.
    stable_ties : bool
        Retain source order for equal-minute trades in changed/new groups.
        The default retains the legacy standalone computation contract.

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
    # Keep the public legacy behavior. Staged refreshes use source-order ties
    # for changed/new groups while retaining aggregates of unchanged history.
    df_sorted = df_with_minutes.sort(["Isin", "Datum", "time_minutes"], maintain_order=stable_ties)
    
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


def compute_daily_metrics(
    df_trades: pl.DataFrame,
    *,
    previous_trades: pl.DataFrame | None = None,
    previous_metrics: pl.DataFrame | None = None,
) -> pl.DataFrame:
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
    previous_trades, previous_metrics : pl.DataFrame | None
        Supply both validated previous products to retain unchanged daily
        aggregates. Full rolling baselines are still recomputed, including
        the effect of new backdated trades on subsequent trading days.

    Returns
    -------
    pl.DataFrame
        Complete daily metrics with anomaly scores — one row per
        ISIN per trading day.
    """
    logger.info("    Step 1/4: Daily aggregation...")
    if (previous_trades is None) != (previous_metrics is None):
        raise ValueError("Previous trades and metrics must be supplied together")
    df_daily = (
        compute_daily_aggregates(df_trades)
        if previous_trades is None
        else _daily_aggregates_with_history(df_trades, previous_trades, previous_metrics)
    )
    logger.info("             %s daily observations", f"{len(df_daily):,}")

    logger.info("    Step 2/4: Liquidity metrics...")
    df_metrics = compute_liquidity_metrics(df_daily)

    logger.info("    Step 3/4: Rolling baselines (%d trading days)...", ROLLING_WINDOW_DAYS)
    df_rolling = compute_rolling_baselines(df_metrics)

    logger.info("    Step 4/4: Anomaly detection...")
    df_anomaly = compute_anomaly_flags(df_rolling)
    
    return df_anomaly


def _daily_aggregates_with_history(
    current: pl.DataFrame, previous: pl.DataFrame, previous_metrics: pl.DataFrame,
) -> pl.DataFrame:
    """Retain published aggregates iff their complete raw group is unchanged.

    Minute-resolution times can tie. Re-sorting a larger table with an unstable
    legacy sort can change unrelated historic first/last prices. Reusing proven
    unchanged groups prevents that drift without changing any metric formula.
    """
    keys = ["Isin", "Datum"]
    trade_columns = ["Isin", "Datum", "Zeit", "Kurs", "Volumen", "Off Book"]
    if current.schema != previous.schema:
        raise ValueError("Previous and current master trade schemas differ")
    if current.is_duplicated().any() or previous.is_duplicated().any():
        raise ValueError("Cannot reuse metrics: duplicate raw trade records")
    if previous.join(current, on=trade_columns, how="anti").height:
        raise ValueError("Cannot reuse metrics: previously published raw trades were removed or changed")
    prior_daily = previous_metrics.select(DAILY_AGGREGATE_COLUMNS)
    raw_counts = previous.group_by(keys).len().rename({"len": "trades_today"})
    metric_counts = prior_daily.select(keys + ["trades_today"])
    if (
        prior_daily.select(keys).is_duplicated().any()
        or raw_counts.join(metric_counts, on=keys + ["trades_today"], how="anti").height
        or metric_counts.join(raw_counts, on=keys + ["trades_today"], how="anti").height
    ):
        raise ValueError("Cannot reuse metrics: previous raw/daily group coverage differs")
    additions = current.join(previous, on=trade_columns, how="anti", maintain_order="left")
    changed_keys = additions.select(keys).unique()
    if changed_keys.is_empty():
        return prior_daily
    unchanged = prior_daily.join(changed_keys, on=keys, how="anti", maintain_order="left")
    changed_raw = current.join(changed_keys, on=keys, how="inner", maintain_order="left")
    changed = compute_daily_aggregates(changed_raw, stable_ties=True)
    logger.info("             Retained %d unchanged daily groups; recomputed %d", len(unchanged), len(changed))
    return pl.concat([unchanged, changed.select(DAILY_AGGREGATE_COLUMNS)])


def main(data_dir: Path | None = None, *, previous_data_dir: Path | None = None) -> None:
    """Compute the existing 26-column metric contract with durable metadata.

    Genuine stage errors propagate to the orchestrator. Removed securities
    retain their history and last known labels through the security registry.
    The staged pipeline supplies ``previous_data_dir`` as its validated
    published baseline; standalone computation retains its legacy behavior.
    """
    from io import BytesIO
    from backend.operations.security_registry import DATA_DIR, atomic_write_bytes, load_registry

    data_dir = Path(data_dir) if data_dir is not None else DATA_DIR
    trades_path = data_dir / "master_trades.parquet"
    output_path = data_dir / "daily_metrics.parquet"
    started = datetime.now()
    df_trades = pl.read_parquet(trades_path)
    if df_trades.is_empty():
        raise ValueError("Cannot compute metrics from an empty trade snapshot")
    registry = load_registry(data_dir)
    known = set(registry["ISIN"])
    missing = set(df_trades["Isin"].to_list()) - known
    if missing:
        raise ValueError(f"Security registry does not cover historical trades: {sorted(missing)[:5]}")
    df_sec = pl.from_pandas(registry[["ISIN", "NAME", "SEKTOR"]])
    previous_trades = previous_metrics = None
    if previous_data_dir is not None:
        baseline = Path(previous_data_dir)
        old_trades, old_metrics = baseline / "master_trades.parquet", baseline / "daily_metrics.parquet"
        if old_trades.exists() != old_metrics.exists():
            raise ValueError("Incomplete previous raw/metric snapshot")
        if old_trades.exists():
            previous_trades = pl.read_parquet(old_trades)
            previous_metrics = pl.read_parquet(old_metrics)
    df_metrics = compute_daily_metrics(
        df_trades, previous_trades=previous_trades, previous_metrics=previous_metrics,
    )
    df_final = df_metrics.join(
        df_sec, left_on="Isin", right_on="ISIN", how="left",
    ).rename({"NAME": "Name", "SEKTOR": "Sektor"})
    column_order = [
        "Isin", "Name", "Sektor", "Datum",
        "trades_today", "volume_today_units", "volume_today_chf",
        "price_min", "price_max", "price_first", "price_last",
        "price_change_pct", "log_returns", "volatility_daily",
        "amihud_daily", "spread_log_hl", "trade_duration_min", "off_book_pct",
        "trades_30d_median", "volume_30d_median", "volatility_30d_median", "amihud_30d_median",
        "volume_spike", "activity_spike", "price_gap", "anomaly_score",
    ]
    df_final = df_final.select(column_order)
    output = BytesIO()
    df_final.write_parquet(output, compression="snappy")
    atomic_write_bytes(output_path, output.getvalue())
    print(
        f"Computed {len(df_final):,} daily metric rows for "
        f"{df_final['Isin'].n_unique()} ISINs; "
        f"{df_final['Datum'].min()} to {df_final['Datum'].max()}; "
        f"{(datetime.now() - started).total_seconds():.1f}s."
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
