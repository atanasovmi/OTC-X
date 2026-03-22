"""
OTC-X Master Orchestrator
One-click data pipeline: Scrape -> Fetch -> Consolidate -> Analyze
Produces a detailed receipt log in backend/logs/ after each run.
"""

import sys
import io
import traceback
from pathlib import Path
from datetime import datetime
from contextlib import redirect_stdout

# Ensure project root is on sys.path so package imports work
# regardless of whether this module is invoked directly or via -m.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.operations.soft_crawl import run_crawl
from backend.operations.fetcher import main as run_fetcher
from backend.operations.build_master_parquet import build_master_parquet
from backend.operations.metrics import main as run_metrics

# Paths
_BACKEND_DIR = Path(__file__).resolve().parent
_DATA_DIR = _BACKEND_DIR / "data"
_LOG_DIR = _BACKEND_DIR / "logs"


def _file_stats(path: Path) -> str:
    """Return human-readable file size or 'N/A'."""
    if path.exists():
        size = path.stat().st_size
        if size >= 1_048_576:
            return f"{size / 1_048_576:.2f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"
    return "N/A"


def _count_files(directory: Path, pattern: str = "*.csv") -> int:
    """Count files matching a glob pattern."""
    if directory.exists():
        return len(list(directory.glob(pattern)))
    return 0


def _run_stage(name: str, func, receipt_lines: list, stage_results: list):
    """
    Execute a pipeline stage, capture its stdout, track timing and status.
    Returns True on success, False on failure.
    """
    start = datetime.now()
    captured = io.StringIO()
    success = False
    error_msg = ""

    print(f"\n{'=' * 80}")
    print(f"--- {name.upper()} ---")
    print(f"{'=' * 80}")

    try:
        # Capture stdout from the stage while also printing live
        with redirect_stdout(captured):
            func()
        success = True
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        print(f"CRITICAL ERROR in {name}: {error_msg}")

    elapsed = (datetime.now() - start).total_seconds()
    output = captured.getvalue()

    # Print captured output to real stdout
    if output.strip():
        print(output)

    stage_results.append({
        "name": name,
        "success": success,
        "elapsed": elapsed,
        "error": error_msg,
        "output": output.strip(),
    })

    # Build receipt section
    status = "✓ SUCCESS" if success else "✗ FAILED"
    receipt_lines.append(f"  {name}")
    receipt_lines.append(f"    Status:   {status}")
    receipt_lines.append(f"    Duration: {elapsed:.1f}s")
    if error_msg:
        receipt_lines.append(f"    Error:    {error_msg}")
    receipt_lines.append("")

    return success


def _build_receipt(start_time: datetime, end_time: datetime,
                   stage_results: list, receipt_stages: list) -> str:
    """Build the full pipeline receipt as a formatted string."""
    duration = end_time - start_time
    all_ok = all(s["success"] for s in stage_results)

    # Data directory stats
    securities_path = _DATA_DIR / "securities.csv"
    trades_dir = _DATA_DIR / "trades"
    master_path = _DATA_DIR / "master_trades.parquet"
    metrics_path = _DATA_DIR / "daily_metrics.parquet"

    lines = []
    lines.append("╔" + "═" * 78 + "╗")
    lines.append("║" + "OTC-X PIPELINE RECEIPT".center(78) + "║")
    lines.append("╚" + "═" * 78 + "╝")
    lines.append("")
    lines.append(f"  Run Date:     {start_time.strftime('%Y-%m-%d')}")
    lines.append(f"  Start Time:   {start_time.strftime('%H:%M:%S')}")
    lines.append(f"  End Time:     {end_time.strftime('%H:%M:%S')}")
    lines.append(f"  Duration:     {duration}")
    lines.append(f"  Status:       {'ALL STAGES PASSED' if all_ok else 'PIPELINE FAILED'}")
    lines.append("")

    # Stage summary
    lines.append("─" * 80)
    lines.append("  STAGE EXECUTION SUMMARY")
    lines.append("─" * 80)
    lines.extend(receipt_stages)

    # Data products
    lines.append("─" * 80)
    lines.append("  DATA PRODUCTS")
    lines.append("─" * 80)

    sec_rows = "—"
    if securities_path.exists():
        try:
            import pandas as pd
            sec_rows = f"{len(pd.read_csv(securities_path)):,} securities"
        except Exception:
            sec_rows = _file_stats(securities_path)

    trade_files = _count_files(trades_dir, "*.csv")

    master_info = "—"
    if master_path.exists():
        try:
            import polars as pl
            df = pl.read_parquet(master_path)
            master_info = f"{len(df):,} rows, {df['Isin'].n_unique()} ISINs ({_file_stats(master_path)})"
        except Exception:
            master_info = _file_stats(master_path)

    metrics_info = "—"
    if metrics_path.exists():
        try:
            import polars as pl
            df = pl.read_parquet(metrics_path)
            date_range = f"{df['Datum'].min()} → {df['Datum'].max()}"
            metrics_info = (
                f"{len(df):,} rows, {df['Isin'].n_unique()} ISINs, "
                f"{df['Sektor'].drop_nulls().n_unique()} sectors"
            )
            lines.append(f"  Date Range:        {date_range}")
        except Exception:
            metrics_info = _file_stats(metrics_path)

    lines.append(f"  Securities CSV:    {sec_rows}")
    lines.append(f"  Trade CSVs:        {trade_files} files in data/trades/")
    lines.append(f"  Master Parquet:    {master_info}")
    lines.append(f"  Daily Metrics:     {metrics_info}")
    lines.append("")

    # Anomaly snapshot
    if metrics_path.exists():
        try:
            import polars as pl
            df = pl.read_parquet(metrics_path)
            latest = df.sort("Datum").group_by("Isin").last()
            anomaly_counts = latest.group_by("anomaly_score").len().sort("anomaly_score")

            lines.append("─" * 80)
            lines.append("  ANOMALY SNAPSHOT (latest day per ISIN)")
            lines.append("─" * 80)

            total_isins = len(latest)
            flagged = latest.filter(pl.col("anomaly_score") > 0)
            lines.append(f"  Total ISINs:       {total_isins}")
            lines.append(f"  Clean (score 0):   {total_isins - len(flagged)}")
            lines.append(f"  Flagged (score>0): {len(flagged)}")
            if len(flagged) > 0:
                lines.append("")
                lines.append("  Score  Count")
                lines.append("  ─────  ─────")
                for row in anomaly_counts.iter_rows(named=True):
                    if row["anomaly_score"] > 0:
                        lines.append(f"    {row['anomaly_score']:>3}    {row['len']:>4}")
            lines.append("")
        except Exception:
            pass

    # Stage detail logs
    lines.append("─" * 80)
    lines.append("  STAGE DETAIL LOGS")
    lines.append("─" * 80)
    for stage in stage_results:
        lines.append(f"  ┌─ {stage['name']}")
        if stage["output"]:
            for line in stage["output"].split("\n"):
                lines.append(f"  │ {line}")
        if stage["error"]:
            lines.append(f"  │ ERROR: {stage['error']}")
        lines.append(f"  └─ {'OK' if stage['success'] else 'FAILED'} ({stage['elapsed']:.1f}s)")
        lines.append("")

    lines.append("═" * 80)
    lines.append(f"  End of receipt — {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("═" * 80)

    return "\n".join(lines)


def main():
    start_total = datetime.now()

    print("\n" + "=" * 80)
    print("--- OTC-X DATA INTELLIGENCE PIPELINE ---")
    print("=" * 80)
    print(f"Started at: {start_total.strftime('%Y-%m-%d %H:%M:%S')}")

    receipt_stages = []
    stage_results = []

    # Stage 1 – Scrape Valors
    ok = _run_stage("Stage 1: Valor Extraction", run_crawl,
                    receipt_stages, stage_results)
    if not ok:
        _finalise_receipt(start_total, receipt_stages, stage_results)
        return

    # Stage 2 – Fetch Trade Data
    ok = _run_stage("Stage 2: Trade Data Retrieval", run_fetcher,
                    receipt_stages, stage_results)
    if not ok:
        _finalise_receipt(start_total, receipt_stages, stage_results)
        return

    # Stage 3 – Consolidate Data
    ok = _run_stage("Stage 3: Data Consolidation (Parquet)",
                    build_master_parquet, receipt_stages, stage_results)
    if not ok:
        _finalise_receipt(start_total, receipt_stages, stage_results)
        return

    # Stage 4 – Compute Metrics
    ok = _run_stage("Stage 4: Liquidity Metrics Engine", run_metrics,
                    receipt_stages, stage_results)

    _finalise_receipt(start_total, receipt_stages, stage_results)


def _finalise_receipt(start_total, receipt_stages, stage_results):
    """Write the receipt log and print final status."""
    end_total = datetime.now()
    duration = end_total - start_total
    all_ok = all(s["success"] for s in stage_results)

    # Build receipt
    receipt_text = _build_receipt(start_total, end_total,
                                 stage_results, receipt_stages)

    # Save to backend/logs/
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = start_total.strftime("%Y-%m-%d_%H%M%S")
    receipt_path = _LOG_DIR / f"pipeline_receipt_{timestamp}.log"
    receipt_path.write_text(receipt_text, encoding="utf-8")

    print(f"\n{'=' * 80}")
    if all_ok:
        print("--- PIPELINE EXECUTION COMPLETE ---")
        print(f"Total Duration: {duration}")
        print(f"Success! All data products delivered to 'backend/data/'.")
    else:
        print("--- PIPELINE FAILED ---")
        print(f"Total Duration: {duration}")
        failed = [s["name"] for s in stage_results if not s["success"]]
        print(f"Failed stages: {', '.join(failed)}")
    print(f"Receipt saved: {receipt_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
