"""OTC-X Trade Data Fetcher.

Downloads per-security trade CSV exports from the OTC-X API for every
security listed in ``backend/data/securities.csv``.  This is **Stage 2**
of the OTC-X data pipeline, executed after the securities crawl
(``soft_crawl.py``) and before data consolidation
(``build_master_parquet.py``).

Key behaviours
--------------
* Converts Swiss Valor numbers to ISINs via the Luhn check-digit
  algorithm before requesting the trade export endpoint.
* Respects a configurable rate-limit delay (default 1 req/s) and
  performs a single automatic retry on HTTP 403 / 429 responses.
* Existing CSV files are never overwritten — a timestamped filename is
  used when the canonical path already exists.
* Duplicate Valor entries in the input CSV are silently deduplicated.
"""

import pandas as pd
import requests
import os
from pathlib import Path
import time
import logging
from datetime import datetime

# --- Configuration ---
SCRIPT_DIR: Path = Path(__file__).resolve().parent
INPUT_FILE: Path = SCRIPT_DIR.parent / "data" / "securities.csv"
OUTPUT_DIR: Path = SCRIPT_DIR.parent / "data" / "trades"
LOG_DIR: Path = SCRIPT_DIR.parent / "logs"
BASE_URL: str = "https://www.otc-x.ch/api/market/trades/{}/export"
TIMEOUT: int = 10
RATE_LIMIT_DELAY: float = 1.0  # Seconds between requests


# --- Setup Logging ---
def setup_logging() -> logging.Logger:
    """Configure dual-output logging (file + console).

    Creates a timestamped log file under ``backend/logs/`` and
    attaches both a file handler and a stream handler to the root
    logger.

    Returns
    -------
    logging.Logger
        Configured root logger instance.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file = LOG_DIR / f"downloader_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger()


logger = setup_logging()


# --- Helper Functions ---

def calculate_isin_check_digit(isin_without_check: str) -> str:
    """Calculate the ISIN check digit using the Luhn algorithm.

    Each letter in the ISIN prefix is expanded into two decimal digits
    (A = 10 … Z = 35). The resulting digit sequence is then processed
    right-to-left with alternating ×2 / ×1 weights, and the check
    digit is ``(10 − (sum mod 10)) mod 10``.

    Parameters
    ----------
    isin_without_check : str
        The 11-character ISIN prefix **without** the final check digit
        (e.g. ``"CH001629001"``).

    Returns
    -------
    str
        Single-character string containing the computed check digit
        (``'0'`` – ``'9'``).
    """
    # Convert letters to numbers
    digits: list[int] = []
    for char in isin_without_check:
        if char.isdigit():
            digits.append(int(char))
        else:
            # A=10, ..., Z=35
            val = ord(char.upper()) - 55
            digits.extend([int(d) for d in str(val)])
    
    # Process right to left, double every second digit starting from rightmost
    total_sum: int = 0
    # We iterate reversed digits
    # The rightmost of the payload is multiplied by 2
    # Then 1, then 2...
    # Example payload resulted in 1217001629001. Rightmost is '1'.
    # In the example I manually did: 1*2, 0*1, 0*2... 
    # So odd positions (1-based from right) usually get x2 if we count check digit as pos 1? 
    # Wait. The payload is "CH001629001".
    # We need the check digit.
    # The standard says: double every second digit from the right.
    # "From the right" means starting with the last digit of the sequence we have.
    # In my successful manual calc:
    # Seq: ...0 0 1. Rightmost is 1. I multiplied it by 2.
    # So yes, multiply by 2, then 1, then 2.
    
    for i, digit in enumerate(reversed(digits)):
        weight = 2 if i % 2 == 0 else 1
        product = digit * weight
        total_sum += (product // 10) + (product % 10)
        
    check_digit = (10 - (total_sum % 10)) % 10
    return str(check_digit)


def val_to_isin(valor: str | int | float) -> str | None:
    """Convert a Swiss Valor number to a fully-qualified ISIN.

    Pads the numeric Valor to 9 digits, prepends the ``CH`` country
    code, and appends a Luhn check digit.

    Parameters
    ----------
    valor : str | int | float
        Valor number.  Accepts floats (e.g. ``123.0`` as read by
        pandas) and stringified floats (``"123.0"``).

    Returns
    -------
    str | None
        12-character ISIN string (e.g. ``"CH0016290012"``), or
        ``None`` if the input cannot be parsed as a numeric Valor.
    """
    try:
        # Handle cases where pandas reads as float (e.g., 123.0) or string '123.0'
        clean_valor = str(int(float(valor)))
    except (ValueError, TypeError):
        return None
        
    # Pad to 9 digits
    padded_valor = clean_valor.zfill(9)
    isin_prefix = "CH" + padded_valor
    check_digit = calculate_isin_check_digit(isin_prefix)
    return isin_prefix + check_digit


def download_trades(isin: str, session: requests.Session) -> str:
    """Download the trade-history CSV for a single ISIN.

    Fetches the CSV export from the OTC-X API.  On HTTP 403/429 the
    request is retried once after a 5-second back-off.  Existing files
    are preserved by appending a timestamp to the filename.

    Parameters
    ----------
    isin : str
        12-character ISIN identifying the security.
    session : requests.Session
        Pre-configured ``requests`` session with default headers.

    Returns
    -------
    str
        Download outcome — one of ``'success'``, ``'not_found'``, or
        ``'error'``.
    """
    output_file = OUTPUT_DIR / f"{isin}.csv"
    if output_file.exists():
        # Optional: Skipping if exists? 
        # The prompt says: "Do NOT overwrite existing files; append or version (optional: add timestamp)"
        # "Preserve original CSV format exactly as downloaded"
        # "Edge Cases: ... duplicate ISINs in input -> process only once"
        # If I run it multiple times, I should probably check if it exists.
        # But maybe I should append if it's a new run? The prompt says "Do NOT overwrite ... append or version".
        # Since I'm making a downloader, and usually we want to fetch fresh data, maybe skipping is safer for now to avoid mess 
        # unless I implement versioning.
        # "Resumable downloads (skip already-downloaded ISINs)" is an Optional Enhancement.
        # So by default I should probably download it.
        # But "Do NOT overwrite" is strict.
        # Let's create a versioned filename if it exists.
        pass

    url = BASE_URL.format(isin)
    try:
        # Rate limit before request (or after, but strictly max 1 req/sec)
        # We'll sleep at end of loop, but let's ensure we don't hit it.
        
        response = session.get(url, timeout=TIMEOUT)
        
        if response.status_code == 200:
            content = response.content
            # Check for empty content or specific "no data" markers?
            # "Empty CSV responses -> log as warning, still save"
            if not content:
                logger.warning(f"{isin}: Empty response content")
                
            # Handle filename versioning
            save_path = output_file
            if save_path.exists():
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = OUTPUT_DIR / f"{isin}_{timestamp_str}.csv"
                
            with open(save_path, 'wb') as f:
                f.write(content)
            
            # Count lines for log (approximate trades count)
            try:
                text_content = content.decode('utf-8', errors='ignore')
                line_count = len(text_content.strip().split('\n')) - 1 # Header
                line_count = max(0, line_count)
                logger.info(f"✓ {isin}: {line_count} trades downloaded")
            except:
                logger.info(f"✓ {isin}: downloaded (binary/unknown size)")
                
            return 'success'
            
        elif response.status_code == 404:
            logger.warning(f"✗ {isin}: HTTP 404 (no trades available)")
            return 'not_found'
            
        elif response.status_code in [403, 429]:
            logger.warning(f"⚠ {isin}: Rate limit/Forbidden ({response.status_code}). Retrying once...")
            time.sleep(5)
            # Retry once
            response = session.get(url, timeout=TIMEOUT)
            if response.status_code == 200:
                # Save as above (should dedup this code ideally but keeping simple)
                 # Handle filename versioning
                save_path = output_file
                if save_path.exists():
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    save_path = OUTPUT_DIR / f"{isin}_{timestamp_str}.csv"
                    
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"✓ {isin}: downloaded after retry")
                return 'success'
            else:
                logger.error(f"✗ {isin}: Failed after retry ({response.status_code})")
                return 'error'
        else:
            logger.error(f"✗ {isin}: HTTP {response.status_code}")
            return 'error'
            
    except requests.RequestException as e:
        logger.error(f"✗ {isin}: Network error: {e}")
        return 'error'


# --- Main Logic ---
def main() -> None:
    """Run the full trade-download pipeline.

    Reads the securities CSV produced by ``soft_crawl.py``, converts
    each Valor to an ISIN, downloads the trade CSV export from the
    OTC-X API, and writes per-ISIN CSV files to ``backend/data/trades/``.

    The function logs a summary of successful / failed downloads and
    total elapsed time upon completion.

    Returns
    -------
    None
    """
    logger.info("OTC-X Trade Downloader started")
    start_time = time.time()
    
    # 1. Setup
    if not INPUT_FILE.exists():
        logger.critical(f"Missing input file: {INPUT_FILE}")
        return
        
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 2. Load Data
    try:
        df = pd.read_csv(INPUT_FILE)
        logger.info(f"Loaded {len(df)} rows from {INPUT_FILE}")
    except Exception as e:
        logger.critical(f"Failed to read CSV: {e}")
        return
        
    # Check columns
    # File has ,NAME,VALOR. 
    # We need VALOR.
    if 'VALOR' not in df.columns:
        logger.critical("Input CSV missing 'VALOR' column.")
        return
        
    # 3. Process
    stats: dict[str, int] = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'created_files': 0
    }
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'OTC-X-Radar-DataCollector/1.0 (Educational Project)',
        'Accept': 'text/csv,application/json' 
    })
    
    unique_processed: set[str] = set()
    
    for index, row in df.iterrows():
        name = row.get('NAME', 'Unknown')
        valor = row.get('VALOR')
        
        if pd.isna(valor):
            logger.warning(f"Row {index}: Missing VALOR, skipping.")
            stats['failed'] += 1
            continue
            
        isin = val_to_isin(str(valor))
        
        if not isin:
             logger.warning(f"Row {index}: Invalid VALOR {valor}, skipping.")
             stats['failed'] += 1
             continue
             
        if isin in unique_processed:
            continue
        unique_processed.add(isin)
        
        stats['total'] += 1
        logger.info(f"Processing: {isin} ({name})")
        
        result = download_trades(isin, session)
        
        if result == 'success':
            stats['success'] += 1
            stats['created_files'] += 1
        elif result == 'not_found':
            stats['failed'] += 1 # Or 'skipped'? Prompt says "Failed downloads (with reason)"
        else:
            stats['failed'] += 1
            
        # Rate limit
        time.sleep(RATE_LIMIT_DELAY)
        
    # 4. Summary
    elapsed_time = time.time() - start_time
    m, s = divmod(elapsed_time, 60)
    
    logger.info("========== SUMMARY ==========")
    logger.info(f"Total ISINs processed: {stats['total']}")
    logger.info(f"Successful downloads: {stats['success']}")
    logger.info(f"Failed/Not Found: {stats['failed']}")
    logger.info(f"CSV files created: {stats['created_files']}")
    logger.info(f"Time elapsed: {int(m)}m {int(s)}s")
    logger.info(f"Log saved: {logger.handlers[0].baseFilename}")


if __name__ == "__main__":
    main()
