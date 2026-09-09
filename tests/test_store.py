"""Tests for weather_agent.store — the append-only shard store (paper state).

These pin the three properties the design rests on: shards are never rewritten,
two runs never touch the same path, and a DuckDB rebuilt from the shards is
indistinguishable from the original.
"""
from __future__ import annotations

import datetime as dt
from datetime import date
import gzip
import json

import pytest

from weather_agent import collector, store


T0 = dt.datetime(2026, 9, 9, 7, 30, tzinfo=dt.timezone.utc)

#: The caller's target_date (2D §C). A trade carries the day it was opened
#: for; nothing downstream rebuilds it from `endDate`.
TD_TEST = date(2026, 9, 10)



def _rows(n=3, token_prefix="TOK"):
    return [
        {"token_id": f"{token_prefix}{i}", "timestamp": T0.isoformat(),
         "best_bid": 0.48, "best_ask": 0.52,
         "book_snapshot": {"hash": "h", "bids": [{"price": 0.48, "size": 30.0}]},
         "dataset_version": "ds1", "record_version": 1}
        for i in range(n)
    ]


# --------------------------------------------------------------------------- layout
def test_shard_path_is_dated_and_named_after_the_run(tmp_path):
    p = store.shard_path(tmp_path, "orderbook_snapshots", run_id="col_1", when=T0)
    assert p.parent == tmp_path / "orderbook_snapshots" / "2026" / "09" / "09"
    assert p.name == "orderbook_snapshots__col_1__0000.ndjson"


def test_run_ids_are_sanitised_into_path_components(tmp_path):
    p = store.shard_path(tmp_path, "trades", run_id="run/../etc/passwd", when=T0)
    assert ".." not in p.name and "/" not in p.name
    assert p.parent == tmp_path / "trades" / "2026" / "09" / "09"


def test_an_empty_component_is_rejected_rather_than_silently_renamed():
    with pytest.raises(ValueError):
        store.shard_path("/tmp", "orderbook_snapshots", run_id="///", when=T0)


# --------------------------------------------------------------------------- write
def test_write_shard_creates_one_file_per_call(tmp_path):
    out = store.write_shard(_rows(3), table="orderbook_snapshots", run_id="r1",
                            root=tmp_path, when=T0, compress=False)
    assert out["n_rows"] == 3 and out["skipped"] is False
    lines = open(out["path"], encoding="utf-8").read().strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[0])["token_id"] == "TOK0"


def test_writing_zero_rows_creates_no_file(tmp_path):
    out = store.write_shard([], table="trades", run_id="r1", root=tmp_path, when=T0)
    assert out["skipped"] is True and out["path"] is None
    assert store.iter_shards(tmp_path, "trades") == []


def test_a_second_write_never_overwrites_the_first(tmp_path):
    """Append-only is enforced, not merely intended."""
    a = store.write_shard(_rows(1, "A"), table="orderbook_snapshots", run_id="r1",
                          root=tmp_path, when=T0, compress=False)
    b = store.write_shard(_rows(1, "B"), table="orderbook_snapshots", run_id="r1",
                          root=tmp_path, when=T0, compress=False)
    assert a["path"] != b["path"]
    assert a["path"].endswith("0000.ndjson") and b["path"].endswith("0001.ndjson")
    assert json.loads(open(a["path"], encoding="utf-8").readline())["token_id"] == "A0"


def test_two_runs_write_disjoint_paths(tmp_path):
    """The conflict-free-merge property: distinct run ids cannot collide."""
    a = store.write_shard(_rows(1), table="orderbook_snapshots", run_id="cycle_A",
                          root=tmp_path, when=T0)
    b = store.write_shard(_rows(1), table="orderbook_snapshots", run_id="cycle_B",
                          root=tmp_path, when=T0)
    assert a["path"] != b["path"]
    assert len(store.iter_shards(tmp_path, "orderbook_snapshots")) == 2


def test_gzip_shards_are_byte_stable_for_identical_content(tmp_path):
    """mtime=0: the same rows produce the same blob, so a redundant commit is a
    no-op in git instead of noise."""
    a = store.write_shard(_rows(2), table="trades", run_id="r1", root=tmp_path,
                          when=T0, compress=True)
    b = store.write_shard(_rows(2), table="trades", run_id="r2", root=tmp_path,
                          when=T0, compress=True)
    assert open(a["path"], "rb").read() == open(b["path"], "rb").read()


def test_datetimes_and_nested_json_survive_serialisation(tmp_path):
    row = {"token_id": "T", "timestamp": T0, "when_date": dt.date(2026, 9, 9),
           "book_snapshot": {"bids": [{"price": 0.4, "size": 1.0}]},
           "dataset_version": "ds1", "record_version": 1}
    out = store.write_shard([row], table="orderbook_snapshots", run_id="r1",
                            root=tmp_path, when=T0, compress=True)
    back = list(store.read_shard(out["path"]))[0]
    assert back["timestamp"] == T0.isoformat()
    assert back["when_date"] == "2026-09-09"
    assert back["book_snapshot"]["bids"][0]["price"] == 0.4


def test_an_unserialisable_value_raises_instead_of_being_dropped(tmp_path):
    with pytest.raises(TypeError):
        store.write_shard([{"x": object()}], table="trades", run_id="r1",
                          root=tmp_path, when=T0)


# --------------------------------------------------------------------------- read
def test_read_shard_reports_the_line_of_a_corrupt_record(tmp_path):
    p = tmp_path / "trades" / "2026" / "09" / "09" / "trades__r1__0000.ndjson"
    p.parent.mkdir(parents=True)
    p.write_text('{"a":1}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r":2: malformed NDJSON"):
        list(store.read_shard(p))


def test_iter_shards_reads_both_plain_and_gzipped(tmp_path):
    store.write_shard(_rows(1), table="trades", run_id="r1", root=tmp_path,
                      when=T0, compress=False)
    store.write_shard(_rows(1), table="trades", run_id="r2", root=tmp_path,
                      when=T0, compress=True)
    paths = store.iter_shards(tmp_path, "trades")
    assert len(paths) == 2
    assert sum(len(list(store.read_shard(p))) for p in paths) == 2


def test_iter_shards_is_chronological_by_path_order(tmp_path):
    later = T0 + dt.timedelta(days=1)
    store.write_shard(_rows(1), table="trades", run_id="r2", root=tmp_path, when=later)
    store.write_shard(_rows(1), table="trades", run_id="r1", root=tmp_path, when=T0)
    paths = store.iter_shards(tmp_path, "trades")
    assert "/09/" in str(paths[0]) and "/10/" in str(paths[1])


def test_iter_shards_on_a_missing_root_is_empty_not_an_error(tmp_path):
    assert store.iter_shards(tmp_path / "nope", "trades") == []


# --------------------------------------------------------------------------- round trip
def test_a_database_can_be_rebuilt_from_shards_alone(con, tmp_path):
    """The property that lets the 546 MB DuckDB stay out of git."""
    s = _FakeSession()
    collector.collect_books(con, ["A", "B"], dataset_version="ds1",
                            collector_session_id="cyc1", session=s, delay_s=0)
    store.dump_table(con, "orderbook_snapshots", run_id="cyc1", root=tmp_path, when=T0)

    from weather_agent import database
    fresh = database.init_db(database.connect(":memory:"))
    try:
        out = store.load_shards(fresh, table="orderbook_snapshots", root=tmp_path)
        assert out["rows_written"] == 2
        original = con.execute(
            "SELECT token_id, best_bid, best_ask, imbalance FROM orderbook_snapshots "
            "ORDER BY token_id").fetchall()
        restored = fresh.execute(
            "SELECT token_id, best_bid, best_ask, imbalance FROM orderbook_snapshots "
            "ORDER BY token_id").fetchall()
        assert original == restored
        # the nested JSON column must not come back double-encoded
        snap = fresh.execute("SELECT book_snapshot FROM orderbook_snapshots "
                             "WHERE token_id = 'A'").fetchone()[0]
        assert json.loads(snap)["bids"][0]["price"] == 0.48
    finally:
        fresh.close()


def test_loading_the_same_shards_twice_changes_nothing(con, tmp_path):
    s = _FakeSession()
    collector.collect_books(con, ["A"], dataset_version="ds1",
                            collector_session_id="cyc1", session=s, delay_s=0)
    store.dump_table(con, "orderbook_snapshots", run_id="cyc1", root=tmp_path, when=T0)
    from weather_agent import database
    fresh = database.init_db(database.connect(":memory:"))
    try:
        store.load_shards(fresh, table="orderbook_snapshots", root=tmp_path)
        store.load_shards(fresh, table="orderbook_snapshots", root=tmp_path)
        n = fresh.execute("SELECT count(*) FROM orderbook_snapshots").fetchone()[0]
        assert n == 1
    finally:
        fresh.close()


def test_load_refuses_a_table_with_no_known_key(con, tmp_path):
    with pytest.raises(ValueError, match="conflict columns"):
        store.load_shards(con, table="data_quality", root=tmp_path)


def test_dump_table_can_filter_to_one_run(con, tmp_path):
    s = _FakeSession()
    collector.collect_books(con, ["A"], dataset_version="ds1",
                            collector_session_id="cyc1", session=s, delay_s=0)
    s2 = _FakeSession(asset_ids=("B",))
    collector.collect_books(con, ["B"], dataset_version="ds1",
                            collector_session_id="cyc2", session=s2, delay_s=0)
    out = store.dump_table(con, "orderbook_snapshots", run_id="cyc2", root=tmp_path,
                           where="collector_session_id = ?", params=["cyc2"], when=T0)
    assert out["n_rows"] == 1
    assert list(store.read_shard(out["path"]))[0]["token_id"] == "B"


def test_store_stats_reports_growth_per_table(tmp_path):
    store.write_shard(_rows(2), table="trades", run_id="r1", root=tmp_path, when=T0)
    store.write_shard(_rows(2), table="orderbook_snapshots", run_id="r1",
                      root=tmp_path, when=T0)
    stats = store.store_stats(tmp_path)
    assert set(stats["tables"]) == {"trades", "orderbook_snapshots"}
    assert stats["total_bytes"] > 0
    assert store.store_stats(tmp_path / "missing")["exists"] is False


# --------------------------------------------------------------------------- helpers
class _FakeSession:
    """Minimal stand-in for requests.Session returning one book per token."""

    def __init__(self, asset_ids=("A", "B")):
        self._asset_ids = asset_ids

    def post(self, url, json=None, timeout=None):
        wanted = [t["token_id"] for t in (json or [])]
        books = [
            {"market": "0xm", "asset_id": a, "timestamp": "1788937456569", "hash": "h",
             "bids": [{"price": "0.48", "size": "30"}],
             "asks": [{"price": "0.52", "size": "25"}]}
            for a in self._asset_ids if a in wanted
        ]
        return _FakeResp(books)


class _FakeResp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


# --------------------------------------------------------------------------- sequences
def test_the_paper_trade_sequence_survives_a_rebuild(con, tmp_path):
    """The ledger's surrogate key is sequence-generated. A DuckDB rebuilt from
    shards starts that sequence at 1, so without restoration the next position
    written would collide with paper_trade_id 1 — overwriting a real trade."""
    from weather_agent import database, paper

    fill = paper.Fill(shares=100.0, notional=50.0, vwap=0.5, fee=0.625,
                      outlay=50.625, executable=True)
    ids = [paper.record_paper_trade(
        con, backtest_id="r", market_id="m", token_id=f"t{i}",
        entry_time=T0, fill=fill, bankroll_after=1.0, dataset_version="ds1", target_date=TD_TEST)
        for i in range(3)]
    assert ids == [1, 2, 3]
    store.dump_table(con, "paper_trades", run_id="r", root=tmp_path, when=T0)

    fresh = database.init_db(database.connect(":memory:"))
    try:
        out = store.load_shards(fresh, table="paper_trades", root=tmp_path)
        assert out["rows_written"] == 3
        assert out["sequence_restarted_at"] == 4
        new_id = paper.record_paper_trade(
            fresh, backtest_id="r", market_id="m", token_id="t9", entry_time=T0,
            fill=fill, bankroll_after=1.0, dataset_version="ds1", target_date=TD_TEST)
        assert new_id == 4                      # continues, does not collide
        n = fresh.execute("SELECT count(*) FROM paper_trades").fetchone()[0]
        assert n == 4
    finally:
        fresh.close()


def test_restoring_an_empty_ledger_leaves_the_sequence_at_one(con):
    assert store.restore_sequences(con, table="paper_trades") == 1


def test_a_table_without_a_sequence_reports_none(con):
    assert store.restore_sequences(con, table="orderbook_snapshots") is None
