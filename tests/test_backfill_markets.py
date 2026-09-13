"""`backfill_markets`: whole events from the catalogue, never gated by `price_history` (B-136)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import duckdb
import pytest

from weather_agent import database as db

_SPEC = importlib.util.spec_from_file_location(
    "backfill_markets", Path(__file__).resolve().parents[1] / "scripts" / "backfill_markets.py")
backfill_markets = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(backfill_markets)

_COLUMNS = """market_id VARCHAR, condition_id VARCHAR, event_id VARCHAR, slug VARCHAR,
    question VARCHAR, city VARCHAR, station VARCHAR, station_identifier VARCHAR,
    resolution_source VARCHAR, unit VARCHAR, rounding_rule VARCHAR, endDate VARCHAR,
    closedTime VARCHAR, winning_outcome VARCHAR, clobTokenIds VARCHAR, outcomes VARCHAR,
    tick_size DOUBLE, min_order_size DOUBLE, group_item_title VARCHAR, lo DOUBLE, hi DOUBLE,
    umaResolutionStatus VARCHAR, feesEnabled BOOLEAN, feeSchedule VARCHAR"""


def _band(market_id, event_id, station, day, lo, hi, unit="C", tokens=True):
    return (str(market_id), f"c{market_id}", str(event_id), f"s{market_id}", "q", "London", "LCY",
            station, "https://www.wunderground.com/history/daily/gb/london/EGLC", unit,
            "whole degree", f"{day}T12:00:00Z", None, "No",
            json.dumps([f"y{market_id}", f"n{market_id}"]) if tokens else None,
            '["Yes", "No"]', 0.01, 5.0, f"{lo}", lo, hi, "resolved", True, None)


@pytest.fixture
def catalog(tmp_path):
    path = tmp_path / "cat.duckdb"
    con = duckdb.connect(str(path))
    con.execute(f"CREATE TABLE mk ({_COLUMNS})")
    rows = [
        # 341797: complete, three bands
        _band(1854400, 341797, "EGLC", "2026-04-08", None, 14.0),
        _band(1854401, 341797, "EGLC", "2026-04-08", 15.0, 15.0),
        _band(1854402, 341797, "EGLC", "2026-04-08", 16.0, None),
        # 321062: one band without a unit -> the WHOLE event stays out
        _band(1773885, 321062, "EGLC", "2026-04-02", None, 8.0),
        _band(1773886, 321062, "EGLC", "2026-04-02", 9.0, 9.0, unit=None),
        # 600000: no station -> excluded by the selection
        _band(2400000, 600000, None, "2026-05-21", None, 20.0),
        # 500666: one band without CLOB token ids -> the WHOLE event stays out
        _band(2299303, 500666, "EDDM", "2026-05-21", None, 18.0),
        _band(2299304, 500666, "EDDM", "2026-05-21", 19.0, None, tokens=False),
    ]
    con.executemany(f"INSERT INTO mk VALUES ({','.join('?' * 24)})", rows)
    con.close()
    return str(path)


def test_only_whole_valid_events_are_written_and_price_history_is_never_read(catalog, tmp_path):
    dbp = str(tmp_path / "pmw.duckdb")
    assert backfill_markets.main(["--db", dbp, "--catalog", catalog, "--dataset-version", "v2"]) == 0

    con = db.connect(dbp)
    markets = con.execute("SELECT event_id, count(*) FROM markets WHERE dataset_version = 'v2' "
                          "GROUP BY 1").fetchall()
    assert markets == [("341797", 3)], markets
    assert con.execute("SELECT count(*) FROM outcomes WHERE dataset_version = 'v2'").fetchone()[0] == 6
    assert con.execute("SELECT count(*) FROM price_history").fetchone()[0] == 0


def test_a_dry_run_writes_nothing_and_counts_every_exclusion_by_reason(catalog, tmp_path, capsys):
    dbp = tmp_path / "pmw.duckdb"
    assert backfill_markets.main(["--db", str(dbp), "--catalog", catalog,
                                  "--dataset-version", "v2", "--dry-run"]) == 0
    assert not dbp.exists(), "a dry run must not even create the database"

    out = json.loads(capsys.readouterr().out)
    assert out["events"] == 3 and out["events_writable"] == 1 and out["markets_writable"] == 3
    assert out["excluded"] == {
        backfill_markets.EXCLUDED_MARKET_WITHOUT_UNIT: 1,
        backfill_markets.EXCLUDED_UNPARSEABLE_TOKENS: 1,
        "no_station_identifier": 1,
    }


def test_the_dataset_version_is_required(catalog, tmp_path):
    with pytest.raises(SystemExit):
        backfill_markets.main(["--db", str(tmp_path / "x.duckdb"), "--catalog", catalog])
