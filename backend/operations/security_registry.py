"""Persistent ISIN identity and metadata for active and historical securities.

The current market universe is a view, not a deletion instruction. Stored
metadata survives delisting; a later reappearance reactivates the same ISIN.
"""

from pathlib import Path
import os
import re
import tempfile

import pandas as pd

SECURITIES_COLUMNS = ["NAME", "SEKTOR", "VALOR", "ISIN"]
REGISTRY_COLUMNS = ["ISIN", "VALOR", "NAME", "SEKTOR", "is_active"]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def is_valid_isin(value: object) -> bool:
    """Validate ISO 6166 shape and the Luhn check digit without guessing Valor."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value):
        return False
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in value)
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = int(char) * (2 if index % 2 else 1)
        total += number // 10 + number % 10
    return total % 10 == 0


def _label(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def validate_universe(frame: pd.DataFrame) -> pd.DataFrame:
    """Fail before replacing metadata when the source universe is incomplete."""
    if frame.empty or set(frame.columns) != set(SECURITIES_COLUMNS):
        raise ValueError("Securities universe must contain nonempty NAME, SEKTOR, VALOR, ISIN columns")
    result = frame.loc[:, SECURITIES_COLUMNS].copy()
    for column in SECURITIES_COLUMNS:
        result[column] = result[column].map(_label)
    invalid = result.loc[~result["ISIN"].map(is_valid_isin), "ISIN"].tolist()
    if invalid or result["ISIN"].duplicated().any():
        raise ValueError(f"Securities universe has invalid or duplicate ISINs: {invalid[:5]}")
    return result


def read_registry(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(frame.columns) != REGISTRY_COLUMNS or frame.empty:
        raise ValueError(f"Invalid security registry schema: {path}")
    if not frame["ISIN"].map(is_valid_isin).all() or frame["ISIN"].duplicated().any():
        raise ValueError(f"Invalid or duplicate ISIN in registry: {path}")
    active = frame["is_active"].str.lower()
    if not active.isin(["true", "false"]).all():
        raise ValueError(f"Invalid is_active value in registry: {path}")
    frame["is_active"] = active.eq("true")
    return frame


def build_registry(
    current: pd.DataFrame,
    *,
    existing: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge the current universe into stored identities and nonblank labels."""
    current = validate_universe(current)
    records: dict[str, dict] = {}
    for frame in (existing, current):
        if frame is None:
            continue
        for row in frame.to_dict("records"):
            isin = _label(row.get("ISIN"))
            if not is_valid_isin(isin):
                raise ValueError(f"Invalid historical ISIN: {isin!r}")
            entry = records.setdefault(isin, {"ISIN": isin, "VALOR": "", "NAME": "", "SEKTOR": ""})
            for column in ("VALOR", "NAME", "SEKTOR"):
                label = _label(row.get(column))
                if label:
                    entry[column] = label
    active = set(current["ISIN"])
    for isin, record in records.items():
        record["is_active"] = isin in active
    return pd.DataFrame(records.values(), columns=REGISTRY_COLUMNS).sort_values("ISIN").reset_index(drop=True)


def load_registry(data_dir: Path | None = None) -> pd.DataFrame:
    """Load the committed registry; missing metadata requires explicit recovery."""
    data_dir = Path(data_dir) if data_dir is not None else DATA_DIR
    return read_registry(data_dir / "security_registry.csv")


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Replace one validated file after its complete bytes are on disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
