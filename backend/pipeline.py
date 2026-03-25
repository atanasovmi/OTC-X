"""OTC-X Master Orchestrator.

One-click data pipeline that executes the full ETL sequence::

    Scrape → Fetch → Consolidate → Analyse

Each stage is run in order; if any stage fails the pipeline halts
immediately.  Console output is tee'd so it appears live **and** is
captured for the receipt log.

After execution a detailed receipt file is written to
``backend/logs/pipeline_receipt_<timestamp>.log`` containing timing,
data-product statistics, an anomaly snapshot, and the verbatim output
of every stage.
"""

import sys
import io
import traceback as _tb
from pathlib import Path
from datetime import datetime

# Ensure project root is on sys.path so package imports work
# regardless of whether this module is invoked directly or via -m.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
import polars as pl

from backend.operations.soft_crawl import run_crawl
from backend.operations.fetcher import main as run_fetcher
from backend.operations.build_master_parquet import build_master_parquet
from backend.operations.metrics import main as run_metrics

# Paths
_BACKEND_DIR = Path(__file__).resolve().parent
_DATA_DIR = _BACKEND_DIR / "data"
_LOG_DIR = _BACKEND_DIR / "logs"


class _TeeStream(io.TextIOBase):
    """Dual-write stream that mirrors output to stdout and a buffer.

    Used to capture stage output for the receipt log while still
    displaying it live on the console.
    """

    def __init__(self, real_stdout: io.TextIOBase) -> None:
        """Initialise the tee stream.

        Parameters
        ----------
        real_stdout : io.TextIOBase
            The original ``sys.stdout`` to forward writes to.
        """
        self._real = real_stdout
        self._buf = io.StringIO()

    def write(self, s: str) -> int:
        """Write *s* to both the real stdout and the internal buffer.

        Parameters
        ----------
        s : str
            Text to write.

        Returns
        -------
        int
            Number of characters written (always ``len(s)``).
        """
        self._real.write(s)
        self._buf.write(s)
        return len(s)

    def flush(self) -> None:
        """Flush the underlying real stdout stream."""
        self._real.flush()

    def getvalue(self) -> str:
        """Return everything captured in the internal buffer.

        Returns
        -------
        str
            Accumulated output since construction.
        """
        return self._buf.getvalue()


def _file_stats(path: Path) -> str:
    """Return a human-readable file size string for *path*.

    Parameters
    ----------
    path : Path
        Filesystem path to inspect.

    Returns
    -------
    str
        Size formatted as ``"X.XX MB"``, ``"X.X KB"``, or ``"X B"``.
        Returns ``"N/A"`` if the file does not exist.
    """
    if path.exists():
        size = path.stat().st_size
        if size >= 1_048_576:
            return f"{size / 1_048_576:.2f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"
    return "N/A"


def _count_files(directory: Path, pattern: str = "*.csv") -> int:
    """Count files matching a glob pattern inside *directory*.

    Parameters
    ----------
    directory : Path
        Directory to search.
    pattern : str, optional
        Glob pattern to match, by default ``"*.csv"``.

    Returns
    -------
    int
        Number of matching files, or ``0`` if the directory does not
        exist.
    """
    if directory.exists():
        return len(list(directory.glob(pattern)))
    return 0


def _run_stage(
    name: str,
    func: callable,
    receipt_lines: list[str],
    stage_results: list[dict],
) -> bool:
    """Execute a single pipeline stage with output capture and timing.

    Temporarily replaces ``sys.stdout`` with a :class:`_TeeStream` so
    that stage output streams live to the console **and** is buffered
    for the receipt log.

    Parameters
    ----------
    name : str
        Human-readable stage name (e.g. ``"Stage 1: Valor Extraction"``).
    func : callable
        Zero-argument callable that performs the stage work.
    receipt_lines : list[str]
        Mutable list to which receipt summary lines are appended.
    stage_results : list[dict]
        Mutable list to which a result dict (``name``, ``success``,
        ``elapsed``, ``error``, ``output``) is appended.

    Returns
    -------
    bool
        ``True`` if the stage completed without raising an exception,
        ``False`` otherwise.
    """
    start = datetime.now()
    success = False
    error_msg = ""

    print(f"\n{'=' * 80}")
    print(f"--- {name.upper()} ---")
    print(f"{'=' * 80}")

    tee = _TeeStream(sys.stdout)
    old_stdout = sys.stdout
    try:
        sys.stdout = tee
        func()
        success = True
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}\n{_tb.format_exc()}"
        sys.stdout = old_stdout
        print(f"CRITICAL ERROR in {name}: {error_msg}")
    finally:
        sys.stdout = old_stdout

    elapsed = (datetime.now() - start).total_seconds()
    output = tee.getvalue()

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


def _build_receipt(
    start_time: datetime,
    end_time: datetime,
    stage_results: list[dict],
    receipt_stages: list[str],
) -> str:
    """Build the full pipeline receipt as a formatted string.

    Assembles a human-readable report containing execution timing,
    per-stage status, data-product statistics (row counts, file sizes),
    an anomaly snapshot of the latest trading day per ISIN, and the
    verbatim log output of each stage.

    Parameters
    ----------
    start_time : datetime
        Pipeline start timestamp.
    end_time : datetime
        Pipeline end timestamp.
    stage_results : list[dict]
        Per-stage result dicts produced by :func:`_run_stage`.
    receipt_stages : list[str]
        Per-stage summary lines produced by :func:`_run_stage`.

    Returns
    -------
    str
        Multi-line receipt string ready to be written to a log file.
    """
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
            sec_rows = f"{len(pd.read_csv(securities_path)):,} securities"
        except Exception:
            sec_rows = _file_stats(securities_path)

    trade_files = _count_files(trades_dir, "*.csv")

    master_info = "—"
    if master_path.exists():
        try:
            df = pl.read_parquet(master_path)
            isin_col = "Isin" if "Isin" in df.columns else df.columns[0]
            master_info = f"{len(df):,} rows, {df[isin_col].n_unique()} ISINs ({_file_stats(master_path)})"
        except Exception:
            master_info = _file_stats(master_path)

    metrics_info = "—"
    if metrics_path.exists():
        try:
            df = pl.read_parquet(metrics_path)
            if "Datum" in df.columns and "Isin" in df.columns:
                date_range = f"{df['Datum'].min()} → {df['Datum'].max()}"
                sektor_info = ""
                if "Sektor" in df.columns:
                    sektor_info = f", {df['Sektor'].drop_nulls().n_unique()} sectors"
                metrics_info = (
                    f"{len(df):,} rows, {df['Isin'].n_unique()} ISINs{sektor_info}"
                )
                lines.append(f"  Date Range:        {date_range}")
            else:
                metrics_info = f"{len(df):,} rows ({_file_stats(metrics_path)})"
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
            df = pl.read_parquet(metrics_path)
            if "Isin" not in df.columns or "anomaly_score" not in df.columns:
                raise KeyError("missing required columns")
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


def main() -> None:
    """Run the full OTC-X data pipeline end-to-end.

    Executes four stages in sequence:

    1. **Valor Extraction** — crawl the OTC-X API for the securities
       universe.
    2. **Trade Data Retrieval** — download per-security trade CSVs.
    3. **Data Consolidation** — merge CSVs into a master Parquet.
    4. **Liquidity Metrics Engine** — compute daily metrics and anomaly
       scores.

    If any stage fails, subsequent stages are skipped and the receipt
    is finalised immediately.
    """
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


def _finalise_receipt(
    start_total: datetime,
    receipt_stages: list[str],
    stage_results: list[dict],
) -> None:
    """Write the receipt log to disk and print a final status summary.

    Parameters
    ----------
    start_total : datetime
        Pipeline start timestamp (used for duration calculation and
        filename generation).
    receipt_stages : list[str]
        Per-stage summary lines produced by :func:`_run_stage`.
    stage_results : list[dict]
        Per-stage result dicts produced by :func:`_run_stage`.
    """
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
