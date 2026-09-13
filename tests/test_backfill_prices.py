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


def test_max_events_alone_is_a_BOUND_not_a_scope_and_is_refused(catalog, tmp_path, fetches, capsys):
    """`--max-events 999999` would price the whole catalogue while passing a gate whose
    own text says that has to be written out (session A)."""
    calls, _ = fetches
    dbp = tmp_path / "pmw.duckdb"
    assert _run(catalog, dbp, "--max-events", "999999") == 2
    assert calls == [] and not dbp.exists()
    assert "--max-events is a bound" in capsys.readouterr().err


def _db_at_schema_7(path, priced_tokens=(), dataset_version="v2"):
    """A REAL database at schema 7: built, then migration 8 taken back out. Prices
    written for `priced_tokens` in `dataset_version`."""
    con = db.init_db(db.connect(str(path)))
    for i, tok in enumerate(priced_tokens):
        db.insert(con, "price_history", {
            "observation_time": f"2026-04-07T{10 + i:02d}:00:00+00:00", "market_id": tok[1:],
            "token_id": tok, "indicative_price": 0.5, "fidelity": 1, "source_window": "DIRECT",
            "fetched_at": "2026-09-09T15:00:00+00:00", "source": "clob",
            "source_timestamp": f"2026-04-07T{10 + i:02d}:00:00+00:00",
            "ingestion_timestamp": "2026-09-09T15:00:00+00:00",
            "dataset_version": dataset_version, "record_version": 1,
        })
    con.execute("DROP TABLE price_fetch_attempts")
    con.execute("DELETE FROM schema_version WHERE version = 8")
    assert db.get_schema_version(con) == 7
    con.close()


def test_a_dry_run_on_an_existing_database_does_NOT_migrate_it_and_counts_what_it_has(
        catalog, tmp_path, fetches, capsys):
    """A rehearsal that migrates the database it is sizing is not a rehearsal
    (session A). Tokens already priced in this dataset_version are not pending, even
    before migration 8 has seeded anything."""
    calls, _ = fetches
    dbp = tmp_path / "pmw.duckdb"
    _db_at_schema_7(dbp, priced_tokens=("y1854400",), dataset_version="v2")

    assert _run(catalog, dbp, "--stations", "EGLC", "--dry-run") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["requests_pending"] == 2 and out["tokens_already_final"] == 1
    assert calls == []

    con = db.connect(str(dbp), read_only=True)
    assert db.get_schema_version(con) == 7
    assert "price_fetch_attempts" not in db.table_names(con)


def test_the_dry_run_says_how_many_pending_tokens_have_prices_under_ANOTHER_version(
        catalog, tmp_path, fetches, capsys):
    dbp = tmp_path / "pmw.duckdb"
    _db_at_schema_7(dbp, priced_tokens=("y1854400", "y1854401"), dataset_version="backfill_2b_v1")
    assert _run(catalog, dbp, "--stations", "EGLC", "--dry-run") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["requests_pending"] == 3
    assert out["pending_with_prices_in_other_dataset_versions"] == 2


def test_migration_8_SEEDS_the_attempts_from_price_history(tmp_path):
    """A row in `price_history` is proof the token was asked for and returned points.
    Without the seed, every token already held counts as pending (measured: 807 EGLC
    tokens, 1 997 against 1 190)."""
    dbp = tmp_path / "pmw.duckdb"
    _db_at_schema_7(dbp, priced_tokens=("y1854400", "y1854400x", "y1854401"), dataset_version="backfill_2b_v1")
    con = db.init_db(db.connect(str(dbp)))
    assert db.get_schema_version(con) == 8
    got = con.execute("SELECT token_id, dataset_version, status, points_written, source "
                      "FROM price_fetch_attempts ORDER BY token_id").fetchall()
    assert got == [
        ("y1854400", "backfill_2b_v1", "OK", 1, "seeded_from_price_history"),
        ("y1854400x", "backfill_2b_v1", "OK", 1, "seeded_from_price_history"),
        ("y1854401", "backfill_2b_v1", "OK", 1, "seeded_from_price_history"),
    ]

