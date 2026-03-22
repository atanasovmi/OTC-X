"""
OTC-X Liquidity Metrics Engine
Computes daily liquidity metrics from raw trade data for 243 Swiss OTC securities.

Input:
    - data/master_trades.parquet (133k trades, 20 years)
    - data/securities_enriched.csv (ISIN -> Name, Sektor mapping)

Output:
    - data/daily_metrics.parquet (1 row per ISIN per trading day)

Metrics computed:
    1. Price Change (%) - Daily price movement
    2. Log Returns - Natural log of price ratio
    3. Daily Volatility - Standard deviation of intraday prices
    4. Amihud Illiquidity - Price impact per CHF million traded
    5. Spread Proxy - Log high-low spread estimate
    6. Trade Intensity - Number of trades per day
    7. Trade Duration - Maximum gap between trades (minutes)

Plus: 30-day rolling baselines (trading days) and anomaly flags.
"""

import polars as pl
from pathlib import Path
from datetime import datetime


def parse_time_to_minutes(zeit_col: pl.Expr) -> pl.Expr:
    """
    Convert Zeit string (HH:MM:SS or HH:MM) to minutes since midnight.
    
    Args:
        zeit_col: Polars expression for the Zeit column
        
    Returns:
        Polars expression with time in minutes (Float64)
    """
    return (
        zeit_col
        .str.split(":")
        .list.get(0).cast(pl.Float64) * 60  # Hours to minutes
        + zeit_col.str.split(":").list.get(1).cast(pl.Float64)  # Minutes
    )


def compute_daily_aggregates(df_trades: pl.DataFrame) -> pl.DataFrame:
    """
    Aggregate trade-level data to daily level per ISIN.
    
    Computes first/last/min/max prices, total volume, trade counts,
    and off-book percentage for each ISIN on each trading day.
    
    Args:
        df_trades: Raw trade DataFrame with Isin, Datum, Zeit, Kurs, Volumen, Off Book
        
    Returns:
        DataFrame with daily aggregates (1 row per Isin per Datum)
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
    """
    Calculate derived liquidity metrics from daily aggregates.
    
    Metrics:
        - price_change_pct: Percentage change from first to last price
        - log_returns: Natural log of (last/first) price ratio
        - amihud_daily: Price impact measure (|log_returns| / volume_chf * 10^6)
        - spread_log_hl: Spread proxy using log(high/low)
    
    Args:
        df_daily: Daily aggregated DataFrame
        
    Returns:
        DataFrame with computed liquidity metrics
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
    """
    Compute 30-trading-day rolling medians for key metrics.
    
    Uses trading days (not calendar days) - each row represents a trading day,
    so a window of 30 means the last 30 days that the stock actually traded.
    
    Args:
        df_metrics: DataFrame with daily metrics
        
    Returns:
        DataFrame with rolling baseline columns added
    """
    # Sort by date within each ISIN before computing rolling stats
    df_sorted = df_metrics.sort(["Isin", "Datum"])
    
    # Compute rolling medians per ISIN
    df_rolling = df_sorted.with_columns([
        pl.col("trades_today")
        .cast(pl.Float64)
        .rolling_median(window_size=30, min_samples=1)
        .over("Isin")
        .alias("trades_30d_median"),
        
        pl.col("volume_today_chf")
        .rolling_median(window_size=30, min_samples=1)
        .over("Isin")
        .alias("volume_30d_median"),
        
        pl.col("volatility_daily")
        .rolling_median(window_size=30, min_samples=1)
        .over("Isin")
        .alias("volatility_30d_median"),
        
        pl.col("amihud_daily")
        .rolling_median(window_size=30, min_samples=1)
        .over("Isin")
        .alias("amihud_30d_median"),
    ])
    
    return df_rolling


def compute_anomaly_flags(df_rolling: pl.DataFrame) -> pl.DataFrame:
    """
    Flag anomalous trading activity based on deviation from baselines.
    
    Flags:
        - volume_spike: Volume > 1.5x the 30-day median (weight: 3)
        - activity_spike: Trades > 1.5x the 30-day median (weight: 2)
        - price_gap: |price_change_pct| > 5% (weight: 2)
    
    Args:
        df_rolling: DataFrame with rolling baselines
        
    Returns:
        DataFrame with anomaly flags and composite score
    """
    df_anomaly = df_rolling.with_columns([
        # Volume spike: > 1.5x median
        (pl.col("volume_today_chf") > pl.col("volume_30d_median") * 1.5)
        .fill_null(False)
        .alias("volume_spike"),
        
        # Activity spike: > 1.5x median
        (pl.col("trades_today").cast(pl.Float64) > pl.col("trades_30d_median") * 1.5)
        .fill_null(False)
        .alias("activity_spike"),
        
        # Price gap: |change| > 5%
        (pl.col("price_change_pct").abs() > 5.0)
        .fill_null(False)
        .alias("price_gap"),
    ])
    
    # Compute weighted anomaly score (0-7 range)
    df_anomaly = df_anomaly.with_columns([
        (
            pl.col("volume_spike").cast(pl.UInt8) * 3
            + pl.col("activity_spike").cast(pl.UInt8) * 2
            + pl.col("price_gap").cast(pl.UInt8) * 2
        ).alias("anomaly_score")
    ])
    
    return df_anomaly


def compute_daily_metrics(df_trades: pl.DataFrame) -> pl.DataFrame:
    """
    Main pipeline: aggregate trades to daily metrics with anomaly scoring.
    
    Pipeline:
        1. Daily aggregation (group by Isin, Datum)
        2. Liquidity metrics calculation
        3. 30-day rolling baselines
        4. Anomaly detection
    
    Args:
        df_trades: Raw trade-level DataFrame
        
    Returns:
        DataFrame with complete daily metrics per ISIN
    """
    print("    Step 1/4: Daily aggregation...")
    df_daily = compute_daily_aggregates(df_trades)
    print(f"             {len(df_daily):,} daily observations")
    
    print("    Step 2/4: Liquidity metrics...")
    df_metrics = compute_liquidity_metrics(df_daily)
    
    print("    Step 3/4: Rolling baselines (30 trading days)...")
    df_rolling = compute_rolling_baselines(df_metrics)
    
    print("    Step 4/4: Anomaly detection...")
    df_anomaly = compute_anomaly_flags(df_rolling)
    
    return df_anomaly


def main() -> None:
    """
    Entry point for the metrics engine.
    
    Loads data, computes metrics, enriches with metadata, and saves output.
    """
    start_time = datetime.now()
    
    print("=" * 70)
    print("OTC-X Liquidity Metrics Engine - Starting")
    print(f"Timestamp: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Setup paths relative to script location
    script_dir = Path(__file__).resolve().parent
    trades_path = script_dir.parent.parent / "data" / "master_trades.parquet"
    securities_path = script_dir.parent.parent / "data" / "securities_enriched.csv"
    output_path = script_dir.parent.parent / "data" / "daily_metrics.parquet"
    
    try:
        # 1. Load Data
        print("\n[1/4] Loading input data...")
        print(f"      Trades: {trades_path.resolve()}")
        df_trades = pl.read_parquet(trades_path)
        print(f"      -> {len(df_trades):,} trades loaded ({df_trades['Isin'].n_unique()} ISINs)")
        
        print(f"      Securities: {securities_path.resolve()}")
        df_sec = pl.read_csv(
            securities_path,
            schema_overrides={"VALOR": pl.String},  # Avoid int parsing issues
            truncate_ragged_lines=True  # Handle any ragged lines
        )
        print(f"      -> {len(df_sec):,} securities loaded ({df_sec['SEKTOR'].n_unique()} sectors)")
        
        # 2. Compute Metrics
        print("\n[2/4] Computing liquidity metrics...")
        df_metrics = compute_daily_metrics(df_trades)
        
        # 3. Enrich with Metadata
        print("\n[3/4] Enriching with security metadata...")
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
            print(f"      [!] {len(missing_meta)} ISINs have no metadata (Name/Sektor will be null)")
        
        print(f"      -> Final shape: {df_final.shape}")
        
        # 4. Save Output
        print("\n[4/4] Saving output...")
        df_final.write_parquet(output_path, compression="snappy")
        output_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"      -> Written to: {output_path.resolve()}")
        print(f"      -> Size: {output_size_mb:.2f} MB")
        
        # Summary
        elapsed = (datetime.now() - start_time).total_seconds()
        print("\n" + "=" * 70)
        print("SUCCESS! Pipeline completed.")
        print("=" * 70)
        print(f"Total rows:       {len(df_final):,}")
        print(f"Unique ISINs:     {df_final['Isin'].n_unique()}")
        print(f"Unique Sectors:   {df_final['Sektor'].n_unique()}")
        print(f"Date range:       {df_final['Datum'].min()} to {df_final['Datum'].max()}")
        print(f"Elapsed time:     {elapsed:.1f} seconds")
        
        # Schema printout
        print("\nOutput Schema:")
        for col, dtype in df_final.schema.items():
            print(f"  {col:25} {dtype}")
        
        # Sample anomalies
        high_anomaly = df_final.filter(pl.col("anomaly_score") >= 5).sort("Datum", descending=True)
        if len(high_anomaly) > 0:
            print(f"\nHigh-anomaly observations (score >= 5): {len(high_anomaly):,} total")
            # Show top 5 as simple text (avoid Unicode table borders on Windows)
            for row in high_anomaly.head(5).iter_rows(named=True):
                try:
                    print(f"  {row['Datum']} | {row['Isin']} | Score: {row['anomaly_score']} | Price Change: {row['price_change_pct']:.2f}%")
                except UnicodeEncodeError:
                    print(f"  {row['Datum']} | {row['Isin']} | Score: {row['anomaly_score']} | Price Change: {row['price_change_pct']:.2f}%")
        
    except FileNotFoundError as e:
        print(f"\n[ERROR] FILE NOT FOUND: {e}")
        print("   Ensure master_trades.parquet and securities_enriched.csv exist in data/")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
