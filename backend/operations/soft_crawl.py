"""Fetch and validate the complete universe before updating its registry."""

from pathlib import Path
import sys
import pandas as pd
import requests

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.operations.security_registry import (
    DATA_DIR, SECURITIES_COLUMNS, atomic_write_bytes, build_registry,
    load_registry, validate_universe,
)

TIMEOUT = 30
URL = "https://www.otc-x.ch/api/market/securities"


def _page(response: requests.Response) -> tuple[list, dict]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Securities response must be a JSON object")
    items, pagination = payload.get("items"), payload.get("pagination")
    required = {"currentPage", "pageSize", "totalCount", "totalPages"}
    if not isinstance(items, list) or not isinstance(pagination, dict) or not required.issubset(pagination):
        raise ValueError("Securities response lacks items or complete pagination")
    if any(type(pagination[key]) is not int for key in required):
        raise ValueError("Securities pagination must contain integer counters")
    if pagination["pageSize"] <= 0 or pagination["totalCount"] <= 0 or pagination["totalPages"] <= 0:
        raise ValueError("Empty or invalid securities universe")
    expected_pages = (pagination["totalCount"] + pagination["pageSize"] - 1) // pagination["pageSize"]
    if pagination["totalPages"] != expected_pages:
        raise ValueError("Inconsistent securities pagination totals")
    return items, pagination


def run_crawl(data_dir: Path | None = None) -> pd.DataFrame:
    """Persist a complete market snapshot and preserve removed ISINs.

    The public endpoint uses zero-based page and size parameters. A changing
    or partial paginated response fails without replacing files.
    """
    data_dir = Path(data_dir) if data_dir is not None else DATA_DIR
    headers = {"Accept": "application/json", "User-Agent": "OTC-X-DataProcessor/1.0"}
    items, pagination = _page(requests.get(URL, headers=headers, timeout=TIMEOUT))
    if pagination["currentPage"] != 0:
        raise ValueError("Securities response did not start with page zero")
    first = pagination.copy()
    if len(items) != min(first["pageSize"], first["totalCount"]):
        raise ValueError("Incomplete first securities page")
    for number in range(1, first["totalPages"]):
        page_items, page_info = _page(requests.get(
            URL, headers=headers, timeout=TIMEOUT,
            params={"page": number, "size": first["pageSize"]},
        ))
        if page_info != {**first, "currentPage": number}:
            raise ValueError("Securities pagination changed during refresh")
        if len(page_items) != min(first["pageSize"], first["totalCount"] - number * first["pageSize"]):
            raise ValueError(f"Incomplete securities page {number}")
        items.extend(page_items)
    if len(items) != first["totalCount"] or any(not isinstance(item, dict) for item in items):
        raise ValueError("Securities count does not match the complete API universe")
    frame = validate_universe(pd.DataFrame([
        {"NAME": item.get("name"), "SEKTOR": item.get("sector"),
         "VALOR": item.get("valor"), "ISIN": item.get("isin")}
        for item in items
    ], columns=SECURITIES_COLUMNS))
    existing = load_registry(data_dir) if (data_dir / "securities.csv").exists() else None
    registry = build_registry(frame, existing=existing)
    atomic_write_bytes(data_dir / "securities.csv", frame.to_csv(index=False).encode("utf-8"))
    atomic_write_bytes(data_dir / "security_registry.csv", registry.to_csv(index=False).encode("utf-8"))
    print(f"Validated {len(frame)} current securities; retained {len(registry)} registry identities.")
    return frame


if __name__ == "__main__":
    run_crawl()
