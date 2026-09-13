"""`backfill_prices`: whole events, no launch without filters, attempts recorded (B-136)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import duckdb
import pytest

from weather_agent import database as db
from weather_agent.polymarket import prices

_SPEC = importlib.util.spec_from_file_location(
    "backfill_prices", Path(__file__).resolve().parents[1] / "scripts" / "backfill_prices.py")
backfill_prices = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(backfill_prices)


@pytest.fixture
def catalog(tmp_path):
    path = tmp_path / "cat.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE mk (market_id VARCHAR, event_id VARCHAR, station_identifier VARCHAR, "
                "city VARCHAR, endDate VARCHAR, clobTokenIds VARCHAR)")
    rows = [(str(m), e, st, "x", f"{d}T12:00:00Z", json.dumps([f"y{m}", f"n{m}"]))
            for m, e, st, d in (
                (1854400, "341797", "EGLC", "2026-04-08"),
                (1854401, "341797", "EGLC", "2026-04-08"),
                (1854402, "341797", "EGLC", "2026-04-08"),
                (2299303, "500666", "EDDM", "2026-05-21"),
                (2299304, "500666", "EDDM", "2026-05-21"),
                (2400000, "600000", None, "2026-05-21"),
            )]
    con.executemany("INSERT INTO mk VALUES (?,?,?,?,?,?)", rows)
    con.close()
    return str(path)


@pytest.fixture
def fetches(monkeypatch):
    """Replace the network: record every call and answer from a status map."""
    calls, statuses = [], {}

    def ingest(con, session, token_id, market_id, start, end, dataset_version):
        calls.append(token_id)
        st = statuses.get(token_id, prices.S_OK)
        return {"status": st, "points_written": 0 if st != prices.S_OK else 5}

    monkeypatch.setattr(backfill_prices.prices, "ingest", ingest)
    monkeypatch.setattr(backfill_prices.prices, "default_session", lambda: object())
    return calls, statuses


def _run(catalog, dbp, *extra):
    return backfill_prices.main(["--db", str(dbp), "--catalog", catalog,
                                 "--dataset-version", "v2", "--sleep", "0", *extra])


def test_a_launch_without_filters_is_REFUSED_and_asks_for_nothing(catalog, tmp_path, fetches, capsys):
    calls, _ = fetches
    dbp = tmp_path / "pmw.duckdb"
    assert _run(catalog, dbp) == 2
    assert calls == [] and not dbp.exists()
    assert "REFUSED" in capsys.readouterr().err


def test_a_dry_run_needs_no_filter_asks_for_nothing_and_counts_the_requests(catalog, tmp_path, fetches, capsys):
    calls, _ = fetches
    dbp = tmp_path / "pmw.duckdb"
    assert _run(catalog, dbp, "--dry-run") == 0
    assert calls == [] and not dbp.exists()
    out = json.loads(capsys.readouterr().out)
    assert (out["events"], out["markets"], out["requests_pending"]) == (2, 5, 5)
    assert out["excluded"] == {"no_station_identifier": 1}


def test_a_station_launch_fetches_the_whole_event_and_records_every_attempt(catalog, tmp_path, fetches):
    calls, statuses = fetches
    statuses.update({"y1854401": prices.S_EMPTY})
    dbp = tmp_path / "pmw.duckdb"
    assert _run(catalog, dbp, "--stations", "EGLC") == 0
    assert calls == ["y1854400", "y1854401", "y1854402"]
    con = db.connect(str(dbp))
    got = con.execute("SELECT token_id, status FROM price_fetch_attempts WHERE dataset_version = 'v2' "
                      "ORDER BY token_id").fetchall()
    assert got == [("y1854400", "OK"), ("y1854401", "EMPTY"), ("y1854402", "OK")]


def test_a_rerun_asks_again_only_for_what_did_not_reach_a_final_status(catalog, tmp_path, fetches, capsys):
    """EMPTY is a result, not an omission: it is not asked for again. An HTTP error is."""
    calls, statuses = fetches
    statuses.update({"y1854401": prices.S_EMPTY, "y1854402": prices.S_HTTP_ERROR})
    dbp = tmp_path / "pmw.duckdb"
    assert _run(catalog, dbp, "--stations", "EGLC") == 1
    calls.clear(); capsys.readouterr()

    assert _run(catalog, dbp, "--stations", "EGLC", "--dry-run") == 0
    assert json.loads(capsys.readouterr().out)["requests_pending"] == 1

    statuses["y1854402"] = prices.S_OK
    assert _run(catalog, dbp, "--stations", "EGLC") == 0
    assert calls == ["y1854402"]


def test_a_429_stops_the_walk_and_leaves_the_token_pending(catalog, tmp_path, fetches):
    calls, statuses = fetches
    statuses.update({"y1854400": prices.S_RATE_LIMITED})
    dbp = tmp_path / "pmw.duckdb"
    assert _run(catalog, dbp, "--stations", "EGLC") == 1
    assert calls == ["y1854400"], "nothing after a rate limit, and it is never retried in the same pass"
    statuses.clear(); calls.clear()
    assert _run(catalog, dbp, "--stations", "EGLC") == 0
    assert calls[0] == "y1854400"


def test_the_dataset_version_is_required(catalog, tmp_path):
    with pytest.raises(SystemExit):
        backfill_prices.main(["--db", str(tmp_path / "x.duckdb"), "--catalog", catalog, "--dry-run"])
