"""
OTC-X Master Orchestrator
One-click data pipeline: Scrape -> Fetch -> Consolidate -> Analyze
"""

import sys
from pathlib import Path
from datetime import datetime

from backend.operations.soft_crawl import run_crawl
from backend.operations.fetcher import main as run_fetcher
from backend.operations.build_master_parquet import build_master_parquet
from backend.operations.metrics import main as run_metrics


def print_header(text):
    print("\n" + "=" * 80)
    print(f"--- {text.upper()} ---")
    print("=" * 80)


def main():
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
    print(f"Success! All data products delivered to the 'data' directory.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
