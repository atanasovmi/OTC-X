"""Download validated cumulative trade exports using source ISIN identities.

Missing/empty exports preserve history. Malformed responses, failed requests,
and incomplete cumulative histories fail the stage rather than reporting success.
"""

from pathlib import Path
import sys
import logging
import math
import time
from datetime import datetime

import pandas as pd
import requests

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.operations.build_master_parquet import parse_trade_csv
from backend.operations.security_registry import DATA_DIR, atomic_write_bytes, validate_universe

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = DATA_DIR / "securities.csv"
OUTPUT_DIR = DATA_DIR / "trades"
LOG_DIR = SCRIPT_DIR.parent / "logs"
BASE_URL = "https://www.otc-x.ch/api/market/trades/{}/export"
TIMEOUT = 10
RATE_LIMIT_DELAY = 1.0
logger = logging.getLogger(__name__)


def setup_logging(log_dir: Path | None = None) -> logging.Logger:
    """Create logging only when running the stage; importing has no side effects."""
    directory = LOG_DIR if log_dir is None else log_dir
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / f"downloader_{datetime.now():%Y-%m-%d_%H%M%S}.log"
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    for handler in (logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def calculate_isin_check_digit(isin_without_check: str) -> str:
    """Calculate the compatible Swiss Valor conversion's Luhn check digit."""
    digits = []
    for char in isin_without_check:
        digits.extend(int(digit) for digit in (char if char.isdigit() else str(ord(char.upper()) - 55)))
    total = 0
    for index, digit in enumerate(reversed(digits)):
        product = digit * (2 if index % 2 == 0 else 1)
        total += product // 10 + product % 10
    return str((10 - total % 10) % 10)


def val_to_isin(valor: str | int | float) -> str | None:
    """Retain Valor conversion for callers; downloads use the API's actual ISIN."""
    try:
        number = float(valor)
        if not math.isfinite(number) or not number.is_integer() or not 0 < number < 1_000_000_000:
            return None
        clean = str(int(number)).zfill(9)
    except (ValueError, TypeError, OverflowError):
        return None
    prefix = "CH" + clean
    return prefix + calculate_isin_check_digit(prefix)


def _save_trades(isin: str, content: bytes, output_dir: Path | None = None) -> bool:
    """Validate before atomic replacement, preserving history for empty exports."""
    directory = OUTPUT_DIR if output_dir is None else Path(output_dir)
    incoming = parse_trade_csv(content, expected_isin=isin)
    if incoming.is_empty():
        logger.info("%s: empty/header-only export; retained existing history", isin)
        return False
    path = directory / f"{isin}.csv"
    if path.exists():
        stored = parse_trade_csv(path.read_bytes(), expected_isin=isin)
        # Full-history export is the source contract. Refuse truncation/corrections
        # until investigated instead of silently deleting or double-counting trades.
        if not set(stored.iter_rows()).issubset(set(incoming.iter_rows())):
            raise ValueError(f"{isin}: cumulative export removes or changes stored trades; retained previous file")
    atomic_write_bytes(path, content)
    logger.info("%s: %d validated trades", isin, len(incoming))
    return True


def download_trades(isin: str, session: requests.Session, output_dir: Path | None = None) -> str:
    """Return success/not_found/empty; genuine HTTP/network/CSV errors raise."""
    url = BASE_URL.format(isin)
    response = session.get(url, timeout=TIMEOUT)
    if response.status_code in (403, 429):
        logger.warning("%s: HTTP %d; retrying once", isin, response.status_code)
        time.sleep(5)
        response = session.get(url, timeout=TIMEOUT)
    if response.status_code == 404:
        logger.info("%s: no trades available (HTTP 404)", isin)
        return "not_found"
    if response.status_code != 200:
        raise requests.HTTPError(f"{isin}: trade export failed with HTTP {response.status_code}", response=response)
    return "success" if _save_trades(isin, response.content, output_dir) else "empty"


def main(data_dir: Path | None = None, *, log_dir: Path | None = None) -> dict[str, int]:
    """Fetch active source ISINs and flush stage logs on every exit path."""
    directory = (LOG_DIR if data_dir is None else Path(data_dir).parent / "logs") if log_dir is None else Path(log_dir)
    setup_logging(directory)
    try:
        return _run_downloads(data_dir)
    finally:
        # In particular, Windows cannot clean staged directories with open logs.
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()


def _run_downloads(data_dir: Path | None = None) -> dict[str, int]:
    """Fetch all active source ISINs; fail on real errors or zero valid downloads."""
    input_file = INPUT_FILE if data_dir is None else Path(data_dir) / "securities.csv"
    output_dir = OUTPUT_DIR if data_dir is None else Path(data_dir) / "trades"
    start = time.monotonic()
    frame = validate_universe(pd.read_csv(input_file, dtype=str, keep_default_na=False))
    stats = {"total": len(frame), "success": 0, "not_found": 0, "empty": 0, "failed": 0, "created_files": 0}
    errors = []
    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "OTC-X-Radar-DataCollector/1.0",
            "Accept": "text/csv",
        })
        for row in frame.to_dict("records"):
            isin = row["ISIN"]
            try:
                result = download_trades(isin, session, output_dir)
                stats[result] += 1
                if result == "success":
                    stats["created_files"] += 1
            except (requests.RequestException, ValueError, OSError) as exc:
                stats["failed"] += 1
                errors.append(f"{isin}: {exc}")
                logger.error("%s: %s", isin, exc)
            time.sleep(RATE_LIMIT_DELAY)
    print(f"Trade download outcomes: {stats}; elapsed {time.monotonic() - start:.1f}s")
    if errors:
        raise RuntimeError(f"Trade stage failed for {len(errors)} securities: {'; '.join(errors[:5])}")
    if stats["success"] == 0:
        raise RuntimeError("No valid nonempty trade exports downloaded; refusing an unverified refresh")
    return stats


if __name__ == "__main__":
    main()
