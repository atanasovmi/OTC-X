"""Validate a complete snapshot before publishing it or marking it refreshed.

The existing Parquet schemas remain the data contract. Missing historical
labels are allowed; missing identifiers, invalid numbers, mismatched products,
and an inconsistent current securities universe are not.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import polars as pl


DATA_DIR = Path(__file__).resolve().parent / "data"
METRIC_COLUMNS = [
    "Isin", "Name", "Sektor", "Datum", "trades_today", "volume_today_units",
    "volume_today_chf", "price_min", "price_max", "price_first", "price_last",
    "price_change_pct", "log_returns", "volatility_daily", "amihud_daily",
    "spread_log_hl", "trade_duration_min", "off_book_pct", "trades_30d_median",
    "volume_30d_median", "volatility_30d_median", "amihud_30d_median",
    "volume_spike", "activity_spike", "price_gap", "anomaly_score",
]
RAW_COLUMNS = ["Isin", "Datum", "Zeit", "Kurs", "Volumen", "Off Book"]
NULLABLE_METRICS = {"Name", "Sektor", "amihud_daily", "amihud_30d_median"}
FLAG_COLUMNS = {"volume_spike", "activity_spike", "price_gap"}


class SnapshotValidationError(ValueError):
    """A candidate snapshot cannot safely replace the published snapshot."""


@dataclass(frozen=True)
class ValidationReport:
    """Small, non-sensitive snapshot summary for CI and operating logs."""

    metric_rows: int
    trade_rows: int
    active_securities: int
    historical_securities: int
    latest_trade_date: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SnapshotValidationError(message)


def _no_rows(frame: pl.DataFrame, invalid: pl.Expr, message: str) -> None:
    _require(frame.filter(invalid).is_empty(), message)


def _validate_identifiers(frame: pl.DataFrame, column: str, product: str) -> None:
    from backend.operations.security_registry import is_valid_isin

    _require(frame[column].null_count() == 0, f"{product}: missing {column}")
    _require(all(is_valid_isin(value) for value in frame[column].unique()),
             f"{product}: malformed ISIN or checksum")


def validate_snapshot(data_dir: Path = DATA_DIR) -> ValidationReport:
    """Check schema, numeric invariants, registry coverage, and raw/metric totals.

    Reads only the supplied directory. Zero-volume trades may legitimately
    produce null Amihud values; historical labels may be unknown. Neither is
    confused with a failed refresh or a malformed numeric field.
    """
    data_dir = Path(data_dir)
    try:
        raw = pl.read_parquet(data_dir / "master_trades.parquet")
        metrics = pl.read_parquet(data_dir / "daily_metrics.parquet")
        current = pl.read_csv(data_dir / "securities.csv", infer_schema=False)
        registry = pl.read_csv(
            data_dir / "security_registry.csv",
            schema_overrides={"ISIN": pl.String, "VALOR": pl.String,
                              "NAME": pl.String, "SEKTOR": pl.String,
                              "is_active": pl.Boolean},
        )
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise SnapshotValidationError(f"Cannot read snapshot: {exc}") from exc

    _require(raw.columns == RAW_COLUMNS, "Trades: schema columns changed")
    _require(metrics.columns == METRIC_COLUMNS, "Metrics: schema columns changed")
    _require(not raw.is_empty() and not metrics.is_empty(), "Snapshot is empty")
    _require(current.columns == ["NAME", "SEKTOR", "VALOR", "ISIN"],
             "Current securities: schema columns changed")
    _require(set(registry.columns) == {"ISIN", "VALOR", "NAME", "SEKTOR", "is_active"},
             "Registry: schema columns changed")
    _require(not current.is_empty() and not registry.is_empty(), "Securities universe is empty")

    for frame, key, product in [(raw, "Isin", "Trades"), (metrics, "Isin", "Metrics"),
                                (current, "ISIN", "Current securities"),
                                (registry, "ISIN", "Registry")]:
        _require(frame.schema[key] == pl.String, f"{product}: ISIN is not text")
        _validate_identifiers(frame, key, product)
    for frame, product in [(raw, "Trades"), (metrics, "Metrics")]:
        _require(frame.schema["Datum"] == pl.Date, f"{product}: Datum is not a date")
        _require(frame["Datum"].null_count() == 0, f"{product}: missing date")
        _no_rows(frame, pl.col("Datum") > datetime.now(timezone.utc).date() + timedelta(days=1),
                 f"{product}: future date")

    for col in RAW_COLUMNS:
        _require(raw[col].null_count() == 0, f"Trades: missing {col}")
    _require(raw.schema["Off Book"] == pl.Boolean, "Trades: off-book flag is not Boolean")
    _require(raw.schema["Zeit"] == pl.String, "Trades: time is not text")
    _no_rows(raw, ~pl.col("Zeit").str.contains(r"^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$"),
             "Trades: malformed time")
    for col in ("Kurs", "Volumen"):
        _require(raw.schema[col].is_numeric(), f"Trades: {col} is not numeric")
        _no_rows(raw, ~pl.col(col).is_finite(), f"Trades: non-finite {col}")
    _no_rows(raw, (pl.col("Kurs") <= 0) | (pl.col("Volumen") < 0),
             "Trades: invalid price or volume")

    for col in METRIC_COLUMNS:
        if col not in NULLABLE_METRICS:
            _require(metrics[col].null_count() == 0, f"Metrics: missing {col}")
        dtype = metrics.schema[col]
        if col in FLAG_COLUMNS:
            _require(dtype == pl.Boolean, f"Metrics: {col} is not Boolean")
        elif col in {"Name", "Sektor"}:
            _require(dtype == pl.String, f"Metrics: {col} is not text")
        elif col not in {"Isin", "Datum"}:
            _require(dtype.is_numeric(), f"Metrics: {col} is not numeric")
            _no_rows(metrics, pl.col(col).is_not_null() & ~pl.col(col).is_finite(),
                     f"Metrics: non-finite {col}")

    _require(metrics.select(["Isin", "Datum"]).n_unique() == metrics.height,
             "Metrics: duplicate ISIN/date keys")
    _require(raw.unique().height == raw.height, "Trades: duplicate records")
    _no_rows(metrics, pl.col("trades_today") < 1, "Metrics: invalid trade count")
    for col in ("volume_today_units", "volume_today_chf", "volatility_daily",
                "trade_duration_min", "trades_30d_median", "volume_30d_median",
                "volatility_30d_median", "amihud_daily", "amihud_30d_median"):
        _no_rows(metrics, pl.col(col) < 0, f"Metrics: negative {col}")
    _no_rows(metrics, pl.col("spread_log_hl") < -1e-10, "Metrics: negative spread")
    _no_rows(metrics, ~pl.col("off_book_pct").is_between(0, 100),
             "Metrics: off-book percentage outside [0, 100]")
    _no_rows(metrics, (pl.col("price_min") <= 0) | (pl.col("price_min") > pl.col("price_max"))
             | ~pl.col("price_first").is_between(pl.col("price_min"), pl.col("price_max"))
             | ~pl.col("price_last").is_between(pl.col("price_min"), pl.col("price_max")),
             "Metrics: inconsistent price bounds")
    from backend.operations.metrics import (
        PRICE_GAP_PCT, SPIKE_MULTIPLIER, WEIGHT_ACTIVITY, WEIGHT_PRICE_GAP, WEIGHT_VOLUME,
    )
    for flag, condition in [
        ("volume_spike", pl.col("volume_today_chf") > pl.col("volume_30d_median") * SPIKE_MULTIPLIER),
        ("activity_spike", pl.col("trades_today") > pl.col("trades_30d_median") * SPIKE_MULTIPLIER),
        ("price_gap", pl.col("price_change_pct").abs() > PRICE_GAP_PCT),
    ]:
        _no_rows(metrics, pl.col(flag) != condition, f"Metrics: inconsistent {flag}")
    expected_score = (pl.col("volume_spike").cast(pl.UInt8) * WEIGHT_VOLUME
                      + pl.col("activity_spike").cast(pl.UInt8) * WEIGHT_ACTIVITY
                      + pl.col("price_gap").cast(pl.UInt8) * WEIGHT_PRICE_GAP)
    _no_rows(metrics, (pl.col("anomaly_score") != expected_score)
             | ~pl.col("anomaly_score").is_between(0, 7), "Metrics: inconsistent anomaly score")

    expected = raw.group_by(["Isin", "Datum"]).agg(
        pl.len().alias("expected_trades"),
        pl.col("Volumen").sum().alias("expected_units"),
        (pl.col("Volumen") * pl.col("Kurs")).sum().alias("expected_chf"),
        pl.col("Kurs").min().alias("expected_min"),
        pl.col("Kurs").max().alias("expected_max"),
        pl.col("Kurs").std().fill_null(0.0).alias("expected_volatility"),
        (pl.col("Off Book").mean() * 100).alias("expected_off_book"),
    )
    _require(expected.height == metrics.height, "Raw trades and metrics have different daily keys")
    joined = metrics.join(expected, on=["Isin", "Datum"], how="inner")
    _require(joined.height == metrics.height, "Raw trades and metrics have different daily keys")
    _no_rows(joined, pl.col("trades_today") != pl.col("expected_trades"),
             "Raw trades and metrics have different trade counts")
    for actual, target in [("volume_today_units", "expected_units"),
                           ("volume_today_chf", "expected_chf"),
                           ("price_min", "expected_min"), ("price_max", "expected_max"),
                           ("volatility_daily", "expected_volatility"),
                           ("off_book_pct", "expected_off_book")]:
        tolerance = pl.max_horizontal(pl.col(target).abs(), pl.lit(1.0)) * 1e-9
        _no_rows(joined, (pl.col(actual) - pl.col(target)).abs() > tolerance,
                 f"Raw trades and metrics have different {actual}")

    for column, formula in [
        ("price_change_pct", (pl.col("price_last") / pl.col("price_first") - 1) * 100),
        ("log_returns", (pl.col("price_last") / pl.col("price_first")).log()),
        ("spread_log_hl", (pl.col("price_max") / pl.col("price_min")).log()),
        ("amihud_daily", pl.col("log_returns").abs() / pl.col("volume_today_chf") * 1_000_000),
    ]:
        tolerance = pl.max_horizontal(formula.abs(), pl.lit(1.0)) * 1e-9
        invalid = (pl.col(column) - formula).abs() > tolerance
        if column == "amihud_daily":
            invalid = ((pl.col("volume_today_chf") > 0)
                       & (pl.col(column).is_null() | invalid)) | (
                           (pl.col("volume_today_chf") == 0) & pl.col(column).is_not_null())
        _no_rows(metrics, invalid, f"Metrics: inconsistent {column} formula")

    _require(current["ISIN"].n_unique() == current.height, "Current securities: duplicate ISINs")
    _require(registry["ISIN"].n_unique() == registry.height, "Registry: duplicate ISINs")
    _require(registry["is_active"].null_count() == 0, "Registry: missing active status")
    active = set(registry.filter(pl.col("is_active"))["ISIN"].to_list())
    _require(active == set(current["ISIN"].to_list()), "Registry active universe differs from source")
    known = set(registry["ISIN"].to_list())
    history = set(metrics["Isin"].to_list())
    _require(history <= known, "Registry omits historical securities")

    return ValidationReport(metrics.height, raw.height, len(active), len(history),
                            metrics["Datum"].max().isoformat())


def write_refresh_status(data_dir: Path, report: ValidationReport) -> None:
    """Atomically mark a validated refresh; failures cannot replace the timestamp."""
    from backend.operations.security_registry import atomic_write_bytes

    target = Path(data_dir) / "refresh_status.json"
    payload = {"refreshed_at_utc": datetime.now(timezone.utc).isoformat(),
               "latest_trade_date": report.latest_trade_date}
    atomic_write_bytes(target, (json.dumps(payload, indent=2) + "\n").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    """CLI publication gate; status writing is explicit and follows validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--write-refresh-status", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate_snapshot(args.data_dir)
        if args.write_refresh_status:
            write_refresh_status(args.data_dir, report)
    except (SnapshotValidationError, OSError) as exc:
        print(f"Snapshot validation failed: {exc}")
        return 1
    print(json.dumps(asdict(report), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
