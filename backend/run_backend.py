"""
OTC-X Backend Data Pipeline Orchestrator
Professional entry point for the data processing pipeline.

Pipeline stages:
1. Scrape: Fetch securities from OTC-X API
2. Fetch: Download trade data for each security
3. Consolidate: Build master parquet from CSVs
4. Analyze: Compute liquidity metrics and anomalies
"""

import sys
from pathlib import Path
from datetime import datetime

# Add backend directory to path for imports
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

try:
    from operations.soft_crawl import run_crawl
    from operations.fetcher import main as run_fetcher
    from operations.build_master_parquet import build_master_parquet
    from operations.metrics import main as run_metrics
except ImportError as e:
    print(f"Error importing backend operations: {e}")
    sys.exit(1)


def print_header(text):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"--- {text.upper()} ---")
    print("=" * 80)


def main():
    """Main orchestrator for the backend data pipeline"""
    start_total = datetime.now()

    print_header("OTC-X Data Intelligence Pipeline")
    print(f"Started at: {start_total.strftime('%Y-%m-%d %H:%M:%S')}")

    # Stage 1: Scrape Valors
    print_header("Stage 1: Valor Extraction")
    try:
        run_crawl()
    except Exception as e:
        print(f"CRITICAL ERROR in Stage 1: {e}")
        return

    # Stage 2: Fetch Trade Data
    print_header("Stage 2: Trade Data Retrieval")
    try:
        run_fetcher()
    except Exception as e:
        print(f"CRITICAL ERROR in Stage 2: {e}")
        return

    # Stage 3: Consolidate Data
    print_header("Stage 3: Data Consolidation (Parquet)")
    try:
        build_master_parquet()
    except Exception as e:
        print(f"CRITICAL ERROR in Stage 3: {e}")
        return

    # Stage 4: Compute Metrics
    print_header("Stage 4: Liquidity Metrics Engine")
    try:
        run_metrics()
    except Exception as e:
        print(f"CRITICAL ERROR in Stage 4: {e}")
        return

    end_total = datetime.now()
    duration = end_total - start_total

    print_header("Pipeline Execution Complete")
    print(f"Total Duration: {duration}")
    print(f"Success! All data products delivered to '{backend_dir}/data' directory.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
