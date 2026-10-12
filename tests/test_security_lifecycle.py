"""Regression coverage for complete-universe lifecycle and fail-closed ingestion."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import polars as pl
import pytest
import requests

from backend.operations import fetcher, soft_crawl
from backend.operations.build_master_parquet import build_master_parquet, parse_trade_csv
from backend.operations.metrics import compute_daily_metrics, main as run_metrics
from backend.operations.security_registry import build_registry, read_registry, validate_universe

A = "CH0001574596"
B = "CH0001574604"
C = "CH0001579363"
HEADER = b"Isin, Datum, Zeit, Kurs, Volumen, Off Book\n"


def securities(*isins):
    return pd.DataFrame([
        {"NAME": f"Name {isin}", "SEKTOR": "Banken", "VALOR": "999", "ISIN": isin}
        for isin in isins
    ])


def trade(isin=A, date_text="01.01.2024", price="100", volume="10", time_text="09:00", flag=""):
    return f"{isin}, {date_text}, {time_text}, {price}, {volume}, {flag}\n".encode()


def response(content=b"", status=200, payload=None):
    result = MagicMock()
    result.content = content
    result.status_code = status
    result.json.return_value = payload
    return result


def universe_payload(*isins, page=0, size=None, total=None):
    size = len(isins) if size is None else size
    total = len(isins) if total is None else total
    return {
        "items": [{"name": f"Name {isin}", "sector": "Banken", "valor": 999, "isin": isin} for isin in isins],
        "pagination": {"currentPage": page, "pageSize": size, "totalCount": total,
                       "totalPages": (total + size - 1) // size if size else 0},
    }


def fake_session(monkeypatch, responses):
    session = MagicMock()
    session.__enter__.return_value = session
    session.get.side_effect = responses
    monkeypatch.setattr(fetcher.requests, "Session", lambda: session)
    monkeypatch.setattr(fetcher.time, "sleep", lambda _: None)
    return session


def test_added_removed_and_reappearing_keep_identity_and_metadata():
    initial = build_registry(securities(A, B))
    changed = build_registry(securities(B, C), existing=initial)
    inactive = changed.set_index("ISIN").loc[A]
    assert not inactive["is_active"]
    assert inactive["NAME"] == f"Name {A}"
    assert changed.set_index("ISIN").loc[C, "is_active"]
    renamed = securities(A, C)
    renamed.loc[0, "NAME"] = "Renamed issuer"
    restored = build_registry(renamed, existing=changed).set_index("ISIN")
    assert len(restored) == 3
    assert restored.loc[A, "is_active"] and restored.loc[A, "NAME"] == "Renamed issuer"
    assert not restored.loc[B, "is_active"]


def test_registry_uses_last_nonblank_history_fields_independently():
    history = pd.DataFrame({
        "Isin": [A, A, A], "Datum": [date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 1)],
        "Name": ["Original", "Latest", None], "Sektor": ["Banken", None, " "],
    })
    result = build_registry(securities(B), history=history).set_index("ISIN")
    assert result.loc[A, "NAME"] == "Latest"
    assert result.loc[A, "SEKTOR"] == "Banken"
    current = securities(A)
    current.loc[0, ["NAME", "SEKTOR"]] = [" ", None]
    updated = build_registry(current, existing=result.reset_index()).set_index("ISIN")
    assert updated.loc[A, "NAME"] == "Latest" and updated.loc[A, "SEKTOR"] == "Banken"


@pytest.mark.parametrize("frame", [securities(A, A), securities("CH0001574597")])
def test_universe_rejects_duplicate_or_invalid_isin(frame):
    with pytest.raises(ValueError):
        validate_universe(frame)


def test_registry_bool_and_uniqueness_are_validated(tmp_path):
    registry = build_registry(securities(A))
    path = tmp_path / "security_registry.csv"
    registry.to_csv(path, index=False)
    assert read_registry(path).loc[0, "is_active"]
    registry["is_active"] = "maybe"
    registry.to_csv(path, index=False)
    with pytest.raises(ValueError, match="is_active"):
        read_registry(path)


@pytest.mark.parametrize("payload", [
    {"items": [], "pagination": {"currentPage": 0, "pageSize": 3, "totalCount": 0, "totalPages": 0}},
    universe_payload(A, size=3, total=3),
    universe_payload(A, A),
    universe_payload("CH0001574597"),
    {"items": [], "pagination": {}},
])
def test_invalid_universe_preserves_current_and_registry(tmp_path, monkeypatch, payload):
    securities(A, B).to_csv(tmp_path / "securities.csv", index=False)
    build_registry(securities(A, B)).to_csv(tmp_path / "security_registry.csv", index=False)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    monkeypatch.setattr(soft_crawl.requests, "get", lambda *a, **kw: response(payload=payload))
    with pytest.raises(ValueError):
        soft_crawl.run_crawl(tmp_path)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_crawl_fetches_all_pages_before_marking_inactive(tmp_path, monkeypatch):
    securities(A, B).to_csv(tmp_path / "securities.csv", index=False)
    build_registry(securities(A, B)).to_csv(tmp_path / "security_registry.csv", index=False)
    mock = MagicMock(side_effect=[
        response(payload=universe_payload(B, size=1, total=2)),
        response(payload=universe_payload(C, page=1, size=1, total=2)),
    ])
    monkeypatch.setattr(soft_crawl.requests, "get", mock)
    result = soft_crawl.run_crawl(tmp_path)
    assert set(result["ISIN"]) == {B, C}
    assert mock.call_args.kwargs["params"] == {"page": 1, "size": 1}
    registry = read_registry(tmp_path / "security_registry.csv").set_index("ISIN")
    assert not registry.loc[A, "is_active"] and registry.loc[C, "is_active"]


def test_crawl_rejects_changing_pagination_without_writes(tmp_path, monkeypatch):
    path = tmp_path / "securities.csv"
    securities(A).to_csv(path, index=False)
    previous = path.read_bytes()
    mock = MagicMock(side_effect=[
        response(payload=universe_payload(A, size=1, total=2)),
        response(payload=universe_payload(B, page=1, size=1, total=3)),
    ])
    monkeypatch.setattr(soft_crawl.requests, "get", mock)
    with pytest.raises(ValueError, match="changed"):
        soft_crawl.run_crawl(tmp_path)
    assert path.read_bytes() == previous
    assert not (tmp_path / "security_registry.csv").exists()


@pytest.mark.parametrize("content", [b"", b"  \n", HEADER])
def test_empty_exports_keep_good_existing_history(tmp_path, content):
    path = tmp_path / f"{A}.csv"
    prior = HEADER + trade()
    path.write_bytes(prior)
    assert not fetcher._save_trades(A, content, tmp_path)
    assert path.read_bytes() == prior


@pytest.mark.parametrize("content", [
    b"<html>maintenance</html>", b"header\ndata\n",
    HEADER + trade(isin=B), HEADER + trade(price="NaN"),
    HEADER + trade(volume=""), HEADER + trade(date_text="31.02.2024"),
    HEADER + trade(time_text="25:00"), HEADER + trade(flag="unknown"),
    HEADER + b"broken,row\n",
])
def test_malformed_exports_are_rejected_before_replacement(tmp_path, content):
    path = tmp_path / f"{A}.csv"
    previous = HEADER + trade()
    path.write_bytes(previous)
    with pytest.raises(ValueError):
        fetcher._save_trades(A, content, tmp_path)
    assert path.read_bytes() == previous


def test_truncated_cumulative_history_is_rejected(tmp_path):
    previous = HEADER + trade() + trade(date_text="02.01.2024")
    path = tmp_path / f"{A}.csv"
    path.write_bytes(previous)
    with pytest.raises(ValueError, match="removes or changes"):
        fetcher._save_trades(A, HEADER + trade(date_text="02.01.2024"), tmp_path)
    assert path.read_bytes() == previous
    assert fetcher._save_trades(A, previous + trade(date_text="03.01.2024"), tmp_path)


def test_retry_validates_payload_and_retry_failures_raise(tmp_path, monkeypatch):
    session = fake_session(monkeypatch, [response(status=429), response(HEADER + trade())])
    assert fetcher.download_trades(A, session, tmp_path) == "success"
    assert session.get.call_count == 2
    session = fake_session(monkeypatch, [response(status=403), response(status=503)])
    with pytest.raises(requests.HTTPError):
        fetcher.download_trades(A, session, tmp_path)


def test_main_uses_source_isin_and_separates_no_trade_outcomes(tmp_path, monkeypatch):
    securities(A, B, C).to_csv(tmp_path / "securities.csv", index=False)
    session = fake_session(monkeypatch, [response(HEADER + trade()), response(status=404), response(HEADER)])
    stats = fetcher.main(tmp_path, log_dir=tmp_path / "logs")
    assert [call.args[0] for call in session.get.call_args_list] == [fetcher.BASE_URL.format(isin) for isin in (A, B, C)]
    assert stats == {"total": 3, "success": 1, "not_found": 1, "empty": 1, "failed": 0, "created_files": 1}


@pytest.mark.parametrize("responses", [
    [response(status=404)],
    [response(HEADER)],
    [requests.ConnectionError("network down")],
    [response(b"<html>not CSV</html>")],
])
def test_stage_fails_on_zero_valid_downloads_or_real_failure(tmp_path, monkeypatch, responses):
    securities(A).to_csv(tmp_path / "securities.csv", index=False)
    fake_session(monkeypatch, responses)
    with pytest.raises(RuntimeError):
        fetcher.main(tmp_path, log_dir=tmp_path / "logs")


def test_consolidation_accepts_short_valid_csv_and_header_only(tmp_path):
    directory = tmp_path / "trades"
    directory.mkdir()
    valid = HEADER + trade(price="1", volume="1")
    assert len(valid) < 100
    (directory / f"{A}.csv").write_bytes(valid)
    (directory / f"{B}.csv").write_bytes(HEADER)
    build_master_parquet(tmp_path)
    result = pl.read_parquet(tmp_path / "master_trades.parquet")
    assert result.shape == (1, 6)
    assert result["Kurs"].to_list() == [1.0]
    assert parse_trade_csv((tmp_path / "master_trades_cleaned.csv").read_bytes()).equals(result)


def test_consolidation_rejects_corrupt_file_preserving_outputs(tmp_path):
    directory = tmp_path / "trades"
    directory.mkdir()
    (directory / f"{A}.csv").write_bytes(HEADER + trade())
    (directory / f"{B}.csv").write_bytes(HEADER + trade(B, price="bad"))
    prior = tmp_path / "master_trades.parquet"
    prior.write_bytes(b"previous valid artifact placeholder")
    with pytest.raises(ValueError, match=B):
        build_master_parquet(tmp_path)
    assert prior.read_bytes() == b"previous valid artifact placeholder"


def test_metrics_preserve_inactive_metadata_and_short_history_contract(tmp_path):
    trades = parse_trade_csv(HEADER + trade() + trade(date_text="02.01.2024", price="105"))
    trades.write_parquet(tmp_path / "master_trades.parquet")
    build_registry(securities(B), existing=build_registry(securities(A))).to_csv(tmp_path / "security_registry.csv", index=False)
    run_metrics(tmp_path)
    result = pl.read_parquet(tmp_path / "daily_metrics.parquet")
    assert result.shape == (2, 26)
    assert result["Name"].to_list() == [f"Name {A}"] * 2
    assert result["Sektor"].to_list() == ["Banken"] * 2
    assert result["trades_30d_median"].to_list() == [1.0, 1.0]
    assert result["anomaly_score"].to_list() == [0, 0]


def test_metrics_propagate_missing_input_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_metrics(tmp_path)


def test_zero_volume_is_valid_and_amihud_remains_unassessed(tmp_path):
    trades = parse_trade_csv(HEADER + trade(volume="0"))
    trades.write_parquet(tmp_path / "master_trades.parquet")
    build_registry(securities(A)).to_csv(tmp_path / "security_registry.csv", index=False)
    run_metrics(tmp_path)
    result = pl.read_parquet(tmp_path / "daily_metrics.parquet")
    assert result["volume_today_chf"].to_list() == [0.0]
    assert result["amihud_daily"].to_list() == [None]


def test_blank_unknown_historical_labels_keep_text_schema(tmp_path):
    parse_trade_csv(HEADER + trade()).write_parquet(tmp_path / "master_trades.parquet")
    build_registry(securities(B), historical_isins=[A]).to_csv(tmp_path / "security_registry.csv", index=False)
    run_metrics(tmp_path)
    result = pl.read_parquet(tmp_path / "daily_metrics.parquet")
    assert result.schema["Name"] == pl.String and result.schema["Sektor"] == pl.String
    assert result["Name"].to_list() == [""] and result["Sektor"].to_list() == [""]


def test_consolidation_keeps_published_order_for_same_minute_prices(tmp_path):
    directory = tmp_path / "trades"
    directory.mkdir()
    old = parse_trade_csv(HEADER + trade(price="110") + trade(price="100"))
    old.write_parquet(tmp_path / "master_trades.parquet")
    # Changed API order must not retroactively invert first/last prices.
    (directory / f"{A}.csv").write_bytes(HEADER + trade(price="100") + trade(price="110") + trade(date_text="02.01.2024"))
    build_master_parquet(tmp_path)
    result = pl.read_parquet(tmp_path / "master_trades.parquet")
    assert result.head(2).equals(old)
    from backend.operations.metrics import compute_daily_metrics
    metrics = compute_daily_metrics(result).sort("Datum")
    assert metrics["price_first"].to_list() == [110.0, 100.0]
    assert metrics["price_last"].to_list() == [100.0, 100.0]


def test_consolidation_refuses_removal_of_published_trades(tmp_path):
    directory = tmp_path / "trades"
    directory.mkdir()
    prior = parse_trade_csv(HEADER + trade() + trade(date_text="02.01.2024"))
    path = tmp_path / "master_trades.parquet"
    prior.write_parquet(path)
    before = path.read_bytes()
    (directory / f"{A}.csv").write_bytes(HEADER + trade())
    with pytest.raises(ValueError, match="previously published history"):
        build_master_parquet(tmp_path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("fails", [False, True])
def test_stage_logging_uses_persistent_directory_and_closes_handlers(tmp_path, monkeypatch, fails):
    directory = tmp_path / "candidate"
    directory.mkdir()
    securities(A).to_csv(directory / "securities.csv", index=False)
    logs = tmp_path / "persistent-logs"
    fake_session(monkeypatch, [response(status=503)] if fails else [response(HEADER + trade())])
    if fails:
        with pytest.raises(RuntimeError):
            fetcher.main(directory, log_dir=logs)
    else:
        fetcher.main(directory, log_dir=logs)
    assert not fetcher.logger.handlers
    assert len(list(logs.glob("downloader_*.log"))) == 1


def test_new_isin_and_new_day_preserve_published_historical_metrics():
    prior = parse_trade_csv(HEADER + trade(price="110") + trade(price="100") + trade(B, price="200"))
    old_metrics = compute_daily_metrics(prior).sort(["Isin", "Datum"])
    additions = parse_trade_csv(HEADER + trade(C) + trade(date_text="02.01.2024"))
    current = pl.concat([prior, additions])
    result = compute_daily_metrics(current, previous_trades=prior, previous_metrics=old_metrics)
    unchanged = result.join(old_metrics.select(["Isin", "Datum"]), on=["Isin", "Datum"]).sort(["Isin", "Datum"])
    from polars.testing import assert_frame_equal
    assert_frame_equal(old_metrics, unchanged, check_exact=False, rel_tol=1e-12, abs_tol=1e-12)
    for column in ["price_first", "price_last", "volume_spike", "activity_spike", "price_gap", "anomaly_score"]:
        assert old_metrics[column].equals(unchanged[column])


def test_backdated_trade_recomputes_changed_day_and_following_baselines():
    prior = parse_trade_csv(
        HEADER + trade(volume="10") + trade(date_text="02.01.2024", volume="10")
        + trade(date_text="03.01.2024", volume="20") + trade(B, price="200")
    )
    old = compute_daily_metrics(prior)
    current = pl.concat([prior, parse_trade_csv(HEADER + trade(volume="100", time_text="09:01"))])
    result = compute_daily_metrics(current, previous_trades=prior, previous_metrics=old)
    days = result.filter(pl.col("Isin").eq(A)).sort("Datum")
    assert days["volume_today_units"].to_list() == [110.0, 10.0, 20.0]
    assert old.filter((pl.col("Isin") == A) & (pl.col("Datum") == date(2024, 1, 3)))["volume_spike"].to_list() == [True]
    assert days["volume_spike"].to_list()[-1] is False
    assert old.filter(pl.col("Isin").eq(B)).equals(result.filter(pl.col("Isin").eq(B)))


def test_changed_groups_use_deterministic_source_order_for_tied_times():
    prior = parse_trade_csv(HEADER + trade(B))
    previous = compute_daily_metrics(prior)
    added = parse_trade_csv(HEADER + trade(price="110") + trade(price="100"))
    first = compute_daily_metrics(pl.concat([prior, added]), previous_trades=prior, previous_metrics=previous)
    more = parse_trade_csv(HEADER + trade(C, date_text="02.01.2024"))
    second = compute_daily_metrics(pl.concat([prior, added, more]), previous_trades=prior, previous_metrics=previous)
    assert first.filter(pl.col("Isin").eq(A))["price_first"].to_list() == [110.0]
    assert first.filter(pl.col("Isin").eq(A))["price_last"].to_list() == [100.0]
    assert first.filter(pl.col("Isin").eq(A)).equals(second.filter(pl.col("Isin").eq(A)))


@pytest.mark.parametrize("failure", ["removed", "coverage", "duplicate", "unpaired"])
def test_incremental_metrics_reject_unverified_baselines(failure):
    prior = parse_trade_csv(HEADER + trade() + trade(date_text="02.01.2024"))
    old = compute_daily_metrics(prior)
    current = prior
    kwargs = {"previous_trades": prior, "previous_metrics": old}
    if failure == "removed":
        current = prior.head(1)
    elif failure == "coverage":
        kwargs["previous_metrics"] = old.head(1)
    elif failure == "duplicate":
        current = pl.concat([prior, prior.head(1)])
    else:
        kwargs.pop("previous_metrics")
    with pytest.raises(ValueError):
        compute_daily_metrics(current, **kwargs)
