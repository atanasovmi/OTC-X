"""Read published snapshots with file-aware caching and display-only fallbacks.

The metrics interface remains (full_history, latest_per_isin). Listing lifecycle
and refresh health are separate inputs. The app never writes published data or
invents zero-valued metrics for untraded listings.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "backend" / "data"
REGISTRY_COLUMNS = ["ISIN", "VALOR", "NAME", "SEKTOR", "is_active"]


def _file_version(path: Path) -> tuple[int, int, int] | None:
    """Make replacing or editing a snapshot invalidate its cached reader."""
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size, stat.st_ino
    except FileNotFoundError:
        return None


def normalize_display_labels(frame: pd.DataFrame) -> pd.DataFrame:
    """Copy labels into uniform strings without changing numeric fields."""
    result = frame.copy()
    if "Isin" not in result:
        return result
    for column, fallback in (("Name", result["Isin"]), ("Sektor", "Unknown sector")):
        if column not in result:
            result[column] = fallback
            continue
        labels = result[column].map(
            lambda value: value.strip() if isinstance(value, str) and value.strip() else None
        ).astype(object)
        result[column] = labels.fillna(fallback)
    return result


@st.cache_data(ttl=3600, max_entries=8)
def _load_metrics(path_string: str, version: tuple | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if version is None:
        return pd.DataFrame(), pd.DataFrame()
    df = normalize_display_labels(pd.read_parquet(path_string))
    df["Datum"] = pd.to_datetime(df["Datum"])
    latest = df.sort_values("Datum").groupby("Isin", as_index=False).last()
    # Preserve the established correlation treatment for rare off-book trades.
    hist_off_book = df.groupby("Isin")["off_book_pct"].mean()
    latest["off_book_pct"] = latest["Isin"].map(hist_off_book)
    return df, latest


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the complete historical panel and complete latest snapshots."""
    path = DATA_DIR / "daily_metrics.parquet"
    return _load_metrics(str(path), _file_version(path))


@st.cache_data(ttl=3600, max_entries=8)
def _load_registry(directory: str, versions: tuple) -> pd.DataFrame:
    data_dir = Path(directory)
    registry_path = data_dir / "security_registry.csv"
    if versions[0] is not None:
        registry = pd.read_csv(registry_path, dtype=str, keep_default_na=False)
        missing = set(REGISTRY_COLUMNS) - set(registry.columns)
        if missing:
            raise ValueError(f"Securities registry is missing columns: {sorted(missing)}")
        registry = registry[REGISTRY_COLUMNS].copy()
        flags = registry["is_active"].str.lower().str.strip()
        if not flags.isin(["true", "false", "1", "0"]).all():
            raise ValueError("Securities registry contains invalid active status")
        registry["is_active"] = flags.isin(["true", "1"])
        if registry["ISIN"].eq("").any() or not registry["ISIN"].is_unique:
            raise ValueError("Securities registry requires unique nonempty ISINs")
        return registry

    # Legacy snapshots retain both current and historic identities, read-only.
    current = (
        pd.read_csv(data_dir / "securities.csv", dtype=str, keep_default_na=False)
        if versions[1] is not None else pd.DataFrame(columns=REGISTRY_COLUMNS[:-1])
    )
    if versions[2] is not None:
        labels = normalize_display_labels(pd.read_parquet(
            data_dir / "daily_metrics.parquet", columns=["Isin", "Name", "Sektor", "Datum"]
        ))
        latest = labels.sort_values("Datum").groupby("Isin", as_index=False).last()
        historical = latest[["Isin", "Name", "Sektor"]].rename(
            columns={"Isin": "ISIN", "Name": "NAME", "Sektor": "SEKTOR"}
        )
        historical["VALOR"] = ""
    else:
        historical = pd.DataFrame(columns=REGISTRY_COLUMNS[:-1])
    registry = pd.concat([historical, current], ignore_index=True).drop_duplicates("ISIN", keep="last")
    registry["is_active"] = (
        registry["ISIN"].isin(current["ISIN"])
        if versions[1] is not None else True
    )
    return registry.reindex(columns=REGISTRY_COLUMNS)


def load_security_registry() -> pd.DataFrame:
    """Read the persistent universe, or bootstrap a read-only legacy view."""
    versions = tuple(_file_version(DATA_DIR / name) for name in (
        "security_registry.csv", "securities.csv", "daily_metrics.parquet"
    ))
    return _load_registry(str(DATA_DIR), versions)


def security_universe(registry: pd.DataFrame, latest: pd.DataFrame) -> pd.DataFrame:
    """Join listing identities to trading coverage, retaining inactive history."""
    universe = registry.rename(columns={"ISIN": "Isin", "NAME": "Name", "SEKTOR": "Sektor"}).copy()
    known = set(universe["Isin"])
    if not latest.empty:
        unknown = latest.loc[~latest["Isin"].isin(known), ["Isin", "Name", "Sektor"]].copy()
        unknown["VALOR"] = ""
        unknown["is_active"] = False
        universe = pd.concat([universe, unknown], ignore_index=True)
    universe = normalize_display_labels(universe)
    traded = set(latest["Isin"]) if "Isin" in latest else set()
    universe["has_trading_data"] = universe["Isin"].isin(traded)
    universe["Listing status"] = universe["is_active"].map({True: "Active", False: "Inactive"})
    universe["Trading data"] = universe["has_trading_data"].map({True: "Available", False: "No trading data"})
    return universe.sort_values(["Name", "Isin"]).reset_index(drop=True)


def filter_active(frame: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    """Scope current-market metrics without discarding historic data."""
    return frame[frame["Isin"].isin(universe.loc[universe["is_active"], "Isin"])].copy()


def risk_assessment(history: pd.DataFrame, universe: pd.DataFrame) -> tuple[pd.DataFrame, set[str]]:
    """Return active flags and observed identities in the last 30 market dates."""
    if history.empty:
        return history.copy(), set()
    dates = sorted(history["Datum"].dropna().unique())[-30:]
    window = filter_active(history[history["Datum"].isin(dates)], universe)
    assessed = set(window["Isin"])
    flagged = window[window["anomaly_score"] >= 1]
    risk = flagged.sort_values("Datum").groupby("Isin", as_index=False).last()
    return risk, assessed


def security_choices(universe: pd.DataFrame, search: str = "", sector: str | None = None) -> pd.DataFrame:
    """Select listings independently of history/date filters, including new ones."""
    choices = universe.copy()
    if search:
        query = search.casefold()
        matches = pd.Series(False, index=choices.index)
        for column in ("Isin", "Name", "Sektor"):
            matches |= choices[column].str.casefold().str.contains(query, regex=False, na=False)
        choices = choices[matches]
    if sector and sector != "All Sectors":
        choices = choices[choices["Sektor"] == sector]
    return choices


@st.cache_data(ttl=300, max_entries=8)
def _load_refresh_status(path_string: str, version: tuple | None) -> dict:
    if version is None:
        return {}
    try:
        status = json.loads(Path(path_string).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return status if isinstance(status, dict) else {}


def load_refresh_status() -> dict:
    """Read refresh metadata, invalidating the cache on each snapshot update."""
    path = DATA_DIR / "refresh_status.json"
    return _load_refresh_status(str(path), _file_version(path))


def refresh_freshness(status: dict, now: datetime | None = None) -> dict:
    """Assess pipeline age in UTC; the last market trade is not a health clock."""
    now = now or datetime.now(timezone.utc)
    try:
        stamp = datetime.fromisoformat(status["refreshed_at_utc"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or now.tzinfo is None:
            raise ValueError("Refresh timestamps must include a timezone")
        stamp = stamp.astimezone(timezone.utc)
        age_hours = (now.astimezone(timezone.utc) - stamp).total_seconds() / 3600
        if age_hours < 0:
            raise ValueError("Refresh timestamp is in the future")
    except (KeyError, TypeError, ValueError, AttributeError):
        return {"state": "unknown", "refreshed_at_utc": None, "age_hours": None}
    return {"state": "overdue" if age_hours > 36 else "current", "refreshed_at_utc": stamp, "age_hours": age_hours}
