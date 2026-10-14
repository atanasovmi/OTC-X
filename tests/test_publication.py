"""Publication boundaries: reject bad candidates and preserve the last good data."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import polars as pl
import pytest

from backend import pipeline, validation
from backend.operations.metrics import main as compute_metrics
from backend.operations import fetcher, soft_crawl
from backend.operations.build_master_parquet import format_trade_csv
from backend.operations.security_registry import build_registry


ISIN = "CH0001574596"


@pytest.fixture
def snapshot(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    current = pd.DataFrame([{"NAME": "Issuer", "SEKTOR": "Banken",
                             "VALOR": "157459", "ISIN": ISIN}])
    current.to_csv(data / "securities.csv", index=False)
    build_registry(current).to_csv(data / "security_registry.csv", index=False)
    pl.DataFrame({
        "Isin": [ISIN, ISIN], "Datum": [date(2024, 1, 2)] * 2,
        "Zeit": ["09:00:00", "10:00:00"], "Kurs": [100.0, 102.0],
        "Volumen": [10.0, 20.0], "Off Book": [False, True],
    }).write_parquet(data / "master_trades.parquet")
    compute_metrics(data)
    return data


def contents(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


def alter_metrics(data, expression):
    path = data / "daily_metrics.parquet"
    pl.read_parquet(path).with_columns(expression).write_parquet(path)


def test_complete_snapshot_has_reconciled_totals(snapshot):
    report = validation.validate_snapshot(snapshot)
    assert (report.trade_rows, report.metric_rows, report.active_securities) == (2, 1, 1)
    assert report.latest_trade_date == "2024-01-02"


@pytest.mark.parametrize("expression, error", [
    (pl.lit(float("nan")).alias("price_last"), "non-finite price_last"),
    (pl.lit("102").alias("price_last"), "price_last is not numeric"),
    (pl.lit(0.0).alias("price_min"), "price bounds"),
    (pl.lit(101.0).alias("off_book_pct"), "percentage"),
    (pl.lit(7).alias("anomaly_score"), "anomaly score"),
    (pl.lit(-1.0).alias("volume_30d_median"), "negative volume_30d_median"),
    (pl.lit(None, dtype=pl.UInt32).alias("trades_today"), "missing trades_today"),
    (pl.lit(99.0).alias("volume_today_chf"), "different volume_today_chf"),
    (pl.lit(3).alias("trades_today"), "different trade counts"),
    (pl.lit(date(2099, 1, 1)).alias("Datum"), "future date"),
    (pl.lit(date(2024, 1, 3)).alias("Datum"), "different daily keys"),
    (pl.lit("CH0001574597").alias("Isin"), "checksum"),
    (pl.lit(0.0).alias("log_returns"), "log_returns formula"),
    (pl.lit(0.0).alias("spread_log_hl"), "spread_log_hl formula"),
    (pl.lit(None, dtype=pl.Float64).alias("amihud_daily"), "amihud_daily formula"),
    ([pl.lit(True).alias("volume_spike"), pl.lit(3).alias("anomaly_score")], "inconsistent volume_spike"),
    ([pl.lit(90.0).alias("price_min"), pl.lit(102.0 / 90.0).log().alias("spread_log_hl")], "different price_min"),
    (pl.lit(0.0).alias("off_book_pct"), "different off_book_pct"),
    (pl.lit(0.0).alias("volatility_daily"), "different volatility_daily"),
])
def test_bad_metrics_block_publication(snapshot, expression, error):
    alter_metrics(snapshot, expression)
    with pytest.raises(validation.SnapshotValidationError, match=error):
        validation.validate_snapshot(snapshot)


@pytest.mark.parametrize("product", ["daily_metrics.parquet", "master_trades.parquet"])
def test_duplicate_products_block_publication(snapshot, product):
    path = snapshot / product
    frame = pl.read_parquet(path)
    pl.concat([frame, frame.head(1)]).write_parquet(path)
    with pytest.raises(validation.SnapshotValidationError, match="duplicate"):
        validation.validate_snapshot(snapshot)


def test_registry_must_match_current_source(snapshot):
    path = snapshot / "security_registry.csv"
    frame = pd.read_csv(path)
    frame["is_active"] = False
    frame.to_csv(path, index=False)
    with pytest.raises(validation.SnapshotValidationError, match="active universe"):
        validation.validate_snapshot(snapshot)


def test_snapshot_accepts_unknown_labels_and_legitimate_zero_volume(snapshot):
    raw_path = snapshot / "master_trades.parquet"
    pl.read_parquet(raw_path).with_columns(pl.lit(0.0).alias("Volumen")).write_parquet(raw_path)
    compute_metrics(snapshot)
    alter_metrics(snapshot, [pl.lit(None, dtype=pl.String).alias("Name"),
                             pl.lit(None, dtype=pl.String).alias("Sektor")])
    assert validation.validate_snapshot(snapshot).trade_rows == 2


def test_status_is_only_written_after_successful_validation(snapshot):
    status = snapshot / "refresh_status.json"
    status.write_text('{"refreshed_at_utc": "previous-success"}', encoding="utf-8")
    assert validation.main(["--data-dir", str(snapshot)]) == 0
    assert json.loads(status.read_text()) == {"refreshed_at_utc": "previous-success"}
    alter_metrics(snapshot, pl.lit(-10.0).alias("volume_today_units"))
    assert validation.main(["--data-dir", str(snapshot), "--write-refresh-status"]) == 1
    assert json.loads(status.read_text()) == {"refreshed_at_utc": "previous-success"}


def test_successful_gate_records_refresh_and_market_clocks(snapshot):
    assert validation.main(["--data-dir", str(snapshot), "--write-refresh-status"]) == 0
    status = json.loads((snapshot / "refresh_status.json").read_text())
    assert status["latest_trade_date"] == "2024-01-02"
    assert status["refreshed_at_utc"].endswith("+00:00")


def configure_pipeline(monkeypatch, snapshot):
    monkeypatch.setattr(pipeline, "_BACKEND_DIR", snapshot.parent)
    monkeypatch.setattr(pipeline, "_DATA_DIR", snapshot)
    monkeypatch.setattr(pipeline, "_LOG_DIR", snapshot.parent / "logs")
    for name in ("run_crawl", "run_fetcher", "build_master_parquet", "run_metrics"):
        monkeypatch.setattr(pipeline, name, lambda *, data_dir, **kwargs: None)


@pytest.mark.parametrize("failure", [RuntimeError("upstream unavailable"), SystemExit(1)])
def test_failed_stage_preserves_data_and_stops_later_stages(snapshot, monkeypatch, failure):
    configure_pipeline(monkeypatch, snapshot)
    before = contents(snapshot)
    later_calls = []

    def fail(*, data_dir):
        (data_dir / "securities.csv").write_text("corrupt staged candidate", encoding="utf-8")
        raise failure

    monkeypatch.setattr(pipeline, "run_crawl", fail)
    monkeypatch.setattr(pipeline, "run_fetcher", lambda **kw: later_calls.append(kw))
    assert pipeline.main() == 1
    assert contents(snapshot) == before
    assert later_calls == []
    receipt = next((snapshot.parent / "logs").glob("pipeline_receipt_*.log"))
    assert "PIPELINE FAILED" in receipt.read_text(encoding="utf-8")
    assert not list(snapshot.parent.glob(".otc-x-run-*"))


def test_validation_failure_never_installs_candidate(snapshot, monkeypatch):
    configure_pipeline(monkeypatch, snapshot)
    before = contents(snapshot)
    monkeypatch.setattr(pipeline, "run_metrics", lambda *, data_dir, **kwargs: alter_metrics(
        data_dir, pl.lit(float("inf")).alias("price_last")))
    assert pipeline.main() == 1
    assert contents(snapshot) == before


def test_success_installs_complete_snapshot_and_receipt(snapshot, monkeypatch):
    configure_pipeline(monkeypatch, snapshot)
    monkeypatch.setattr(pipeline, "run_crawl", lambda *, data_dir: (
        data_dir / "candidate-marker.txt").write_text("complete", encoding="utf-8"))
    assert pipeline.main() == 0
    assert (snapshot / "candidate-marker.txt").read_text() == "complete"
    assert validation.validate_snapshot(snapshot).metric_rows == 1
    assert not list(snapshot.parent.glob(".data-previous-*"))
    receipt = next((snapshot.parent / "logs").glob("pipeline_receipt_*.log"))
    assert "ALL STAGES PASSED" in receipt.read_text(encoding="utf-8")


def test_install_failure_restores_previous_snapshot(snapshot, monkeypatch):
    staged = snapshot.parent / "candidate"
    staged.mkdir()
    (staged / "marker.txt").write_text("new", encoding="utf-8")
    before = contents(snapshot)
    rename = Path.rename

    def fail_install(path, destination):
        if path == staged:
            raise PermissionError("destination locked")
        return rename(path, destination)

    monkeypatch.setattr(Path, "rename", fail_install)
    with pytest.raises(PermissionError, match="locked"):
        pipeline._publish_snapshot(staged, snapshot)
    assert contents(snapshot) == before
    assert not list(snapshot.parent.glob(".data-previous-*"))


@pytest.mark.parametrize("invalid_export", [False, True])
def test_real_stage_chain_preserves_history_and_publishes_only_complete_refresh(
        snapshot, monkeypatch, invalid_export):
    """Run all real stages with offline source responses, including one failure."""
    new_isin, untraded_isin = "CH0001574604", "CH0001579363"
    trades = snapshot / "trades"
    trades.mkdir()
    raw = pl.read_parquet(snapshot / "master_trades.parquet")
    (trades / f"{ISIN}.csv").write_bytes(format_trade_csv(raw))
    before = contents(snapshot)
    monkeypatch.setattr(pipeline, "_BACKEND_DIR", snapshot.parent)
    monkeypatch.setattr(pipeline, "_DATA_DIR", snapshot)
    monkeypatch.setattr(pipeline, "_LOG_DIR", snapshot.parent / "logs")

    universe_response = MagicMock()
    universe_response.json.return_value = {
        "items": [{"name": "New issuer", "sector": "Banken", "valor": "1", "isin": isin}
                  for isin in (new_isin, untraded_isin)],
        "pagination": {"currentPage": 0, "pageSize": 2, "totalCount": 2, "totalPages": 1},
    }
    monkeypatch.setattr(soft_crawl.requests, "get", lambda *args, **kwargs: universe_response)
    downloaded = raw.head(1).with_columns(pl.lit(new_isin).alias("Isin"))
    good, empty_or_bad = MagicMock(status_code=200), MagicMock(status_code=200)
    good.content = format_trade_csv(downloaded)
    empty_or_bad.content = b"<html>source unavailable</html>" if invalid_export else b""
    session = MagicMock()
    session.__enter__.return_value = session
    session.get.side_effect = [good, empty_or_bad]
    monkeypatch.setattr(fetcher.requests, "Session", lambda: session)
    monkeypatch.setattr(fetcher.time, "sleep", lambda delay: None)

    assert pipeline.main() == (1 if invalid_export else 0)
    assert list((snapshot.parent / "logs").glob("downloader_*.log"))
    assert not fetcher.logger.handlers
    if invalid_export:
        assert contents(snapshot) == before
    else:
        registry = pd.read_csv(snapshot / "security_registry.csv").set_index("ISIN")
        assert not registry.loc[ISIN, "is_active"]
        assert registry.loc[new_isin, "is_active"] and registry.loc[untraded_isin, "is_active"]
        final = pl.read_parquet(snapshot / "master_trades.parquet")
        assert final.filter(pl.col("Isin") == ISIN).equals(raw)
        assert set(final["Isin"]) == {ISIN, new_isin}
        assert validation.validate_snapshot(snapshot).trade_rows == 3
        assert not (snapshot / "refresh_status.json").exists()  # Post-test gate stamps it.
