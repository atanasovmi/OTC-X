"""Strict trade ingestion that refuses corrupt exports before replacing data."""

from pathlib import Path
import sys
import csv
from datetime import datetime
import io
import math
import re

import polars as pl

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.operations.security_registry import DATA_DIR, atomic_write_bytes, is_valid_isin

TRADE_COLUMNS = ["Isin", "Datum", "Zeit", "Kurs", "Volumen", "Off Book"]
TRADE_SCHEMA = {
    "Isin": pl.String, "Datum": pl.Date, "Zeit": pl.String,
    "Kurs": pl.Float64, "Volumen": pl.Float64, "Off Book": pl.Boolean,
}
_TIME = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?")


def parse_trade_csv(content: bytes, *, expected_isin: str | None = None) -> pl.DataFrame:
    """Validate CSV shape, identity, date/time and finite trade fields.

    A genuinely empty body or a valid header-only CSV represents no trades.
    Malformed/HTML payloads, missing fields and nonmatching identities fail.
    """
    if not content.strip():
        return pl.DataFrame(schema=TRADE_SCHEMA)
    try:
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text), skipinitialspace=True, strict=True)
        header = [value.strip() for value in next(reader)]
        if header != TRADE_COLUMNS:
            raise ValueError(f"Unexpected trade CSV header: {header!r}")
        rows = []
        for line_number, fields in enumerate(reader, start=2):
            if not fields or all(not field.strip() for field in fields):
                continue
            if len(fields) != len(TRADE_COLUMNS):
                raise ValueError(f"Trade CSV line {line_number} has {len(fields)} fields")
            isin, date_text, time_text, price_text, volume_text, off_book = [field.strip() for field in fields]
            if not is_valid_isin(isin) or (expected_isin is not None and isin != expected_isin):
                raise ValueError(f"Invalid or mismatched trade ISIN at line {line_number}: {isin!r}")
            try:
                date = datetime.strptime(date_text, "%d.%m.%Y").date()
                if not _TIME.fullmatch(time_text):
                    raise ValueError("invalid trade time")
                price = float(price_text.replace("'", "").replace(",", "."))
                volume = float(volume_text.replace("'", "").replace(",", "."))
                if not math.isfinite(price) or not math.isfinite(volume) or price <= 0 or volume < 0:
                    raise ValueError("price must be positive and volume nonnegative; both must be finite")
                if off_book not in ("", "X"):
                    raise ValueError("invalid Off Book flag")
            except ValueError as exc:
                raise ValueError(f"Invalid critical trade field at line {line_number}: {exc}") from exc
            rows.append((isin, date, time_text, price, volume, off_book == "X"))
        return pl.DataFrame(rows, schema=TRADE_SCHEMA, orient="row")
    except (UnicodeDecodeError, csv.Error, StopIteration) as exc:
        raise ValueError(f"Malformed trade CSV: {exc}") from exc


def format_trade_csv(frame: pl.DataFrame) -> bytes:
    """Keep the established comma-space CSV and six-decimal numeric format."""
    lines = [", ".join(TRADE_COLUMNS)]
    for row in frame.iter_rows(named=True):
        lines.append(", ".join([
            row["Isin"], row["Datum"].strftime("%d.%m.%Y"), row["Zeit"],
            f'{row["Kurs"]:.6f}', f'{row["Volumen"]:.6f}', "X" if row["Off Book"] else "",
        ]))
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_master_parquet(data_dir: Path | None = None) -> None:
    """Consolidate every historic ISIN; fail instead of skipping corrupt files."""
    data_dir = Path(data_dir) if data_dir is not None else DATA_DIR
    files = sorted((data_dir / "trades").glob("*.csv"))
    frames = []
    empty_count = 0
    for path in files:
        try:
            frame = parse_trade_csv(path.read_bytes(), expected_isin=path.stem)
        except ValueError as exc:
            raise ValueError(f"Invalid trade file {path.name}: {exc}") from exc
        if frame.is_empty():
            empty_count += 1
        else:
            frames.append(frame)
    if not frames:
        raise ValueError("No valid trade records to consolidate; keeping previous master data")
    final = pl.concat(frames).unique(maintain_order=True)
    prior_path = data_dir / "master_trades.parquet"
    if prior_path.exists():
        prior = pl.read_parquet(prior_path)
        if prior.schema != TRADE_SCHEMA:
            raise ValueError("Previous master trade schema is invalid; refusing replacement")
        if prior.join(final, on=TRADE_COLUMNS, how="anti").height:
            raise ValueError("Raw trade files remove or change previously published history")
        additions = final.join(prior, on=TRADE_COLUMNS, how="anti", maintain_order="left")
        # Legacy exports have minute-resolution timestamps. Their row order
        # determines first/last price when times tie. Preserve the published
        # order so an infrastructure fix cannot rewrite historical signals.
        final = pl.concat([prior, additions])
    parquet = io.BytesIO()
    final.write_parquet(parquet, compression="zstd")
    csv_content = format_trade_csv(final)
    atomic_write_bytes(data_dir / "master_trades.parquet", parquet.getvalue())
    atomic_write_bytes(data_dir / "master_trades_cleaned.csv", csv_content)
    print(f"Consolidated {len(final):,} trades from {len(frames)} files; {empty_count} empty/header-only files.")
    print(f"Schema: {final.schema}")


if __name__ == "__main__":
    build_master_parquet()
