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


def test_a_shard_whose_rows_carry_different_columns_still_loads(con, tmp_path):
    """The replay must not raise halfway through when a schema generation changes.

    `upsert_many` refuses a ragged batch — correctly, since binding a short row
    to a wide statement would put values in the wrong parameters. So the replay
    groups by column set before batching.

    This is not hypothetical shape-guessing: the shard store already carries
    THREE column generations in `venue_coverage` and TWO in `cycle_params`,
    written across 2026-09-09/10 as fields were added. Those two tables happen to
    have no conflict columns and are never replayed, so the trap is not armed
    today — which is exactly why it has to be closed now rather than on the day a
    replayed table gains a field and a cycle dies between collect and dump.
    """
    wide = {"token_id": "A", "timestamp": T0.isoformat(), "dataset_version": "ds1",
            "record_version": 1, "best_bid": 0.4, "best_ask": 0.6}
    narrow = {"token_id": "B", "timestamp": T0.isoformat(), "dataset_version": "ds1",
              "record_version": 1}
    store.write_shard([wide, narrow], table="orderbook_snapshots", run_id="r1",
                      root=tmp_path, when=T0)

    from weather_agent import database
    fresh = database.init_db(database.connect(":memory:"))
    try:
        out = store.load_shards(fresh, table="orderbook_snapshots", root=tmp_path)
        assert out["rows_read"] == 2
        assert out["rows_written"] == 2, "both column generations must land"
        got = fresh.execute("SELECT token_id, best_bid FROM orderbook_snapshots "
                            "ORDER BY token_id").fetchall()
        assert got == [("A", 0.4), ("B", None)]
    finally:
        fresh.close()


def test_the_replay_applies_rows_in_one_statement_per_column_group(con, tmp_path, monkeypatch):
    """The fast path is USED, not merely available.

    `upsert_many`'s docstring measured this workload at 24.99 s row-by-row
    against 0.05 s for the bulk path — 478x — and the replay was calling the slow
    one. A speedup nobody can observe is a speedup that silently regresses, so
    this pins the call shape rather than the wall clock.
    """
    from weather_agent import database
    calls = {"many": 0, "one": 0}
    real_many = database.upsert_many
    monkeypatch.setattr(database, "upsert",
                        lambda *a, **k: calls.__setitem__("one", calls["one"] + 1))
    monkeypatch.setattr(database, "upsert_many",
                        lambda *a, **k: (calls.__setitem__("many", calls["many"] + 1),
                                         real_many(*a, **k))[1])
    store.write_shard(_rows(5), table="orderbook_snapshots", run_id="r1",
                      root=tmp_path, when=T0)
    fresh = database.init_db(database.connect(":memory:"))
    try:
        out = store.load_shards(fresh, table="orderbook_snapshots", root=tmp_path)
        assert out["rows_written"] == 5
        assert calls["many"] == 1, "five rows, one column set: one batched call"
        assert calls["one"] == 0, "the row-at-a-time path must not be used"
    finally:
        fresh.close()


# ---------------------------------------------------------------------------
# Newest-first replay: the same table, without re-applying what it overwrites
# ---------------------------------------------------------------------------

def _snapshot(n, *, tick, extra=0):
    """A catalogue-shaped snapshot: the same keys every time, values that move."""
    return [{"market_id": f"m{i}", "dataset_version": "ds1", "record_version": 1,
             "event_id": f"e{i}", "question": f"q{i}", "tick_size": tick}
            for i in range(n + extra)]


def _plantar(root, table, rows, *, run_id, when):
    store.write_shard(rows, table=table, run_id=run_id, root=root, when=when)


def _cargar(root, table, db):
    con = db.init_db(db.connect(":memory:"))
    out = store.load_shards(con, table=table, root=root)
    filas = {(r["market_id"], r["dataset_version"], r["record_version"]): r
             for r in db.query(con, f"SELECT * FROM {table}")}
    con.close()
    return filas, out


def test_newest_first_gives_the_SAME_table_as_the_full_replay(tmp_path, monkeypatch):
    """The equivalence this optimisation rests on, asserted and not argued.

    `upsert` is last-write-wins, so after a full oldest->newest replay the row
    standing for a key is the one from the NEWEST shard that holds it. Going the
    other way and skipping keys already seen reaches the same row without writing
    the ones it would have overwritten.

    Measured on the real store before this was written: `markets` went from
    26 092 upserts to 2 761 and `outcomes` from 46 662 to 5 522, both tables
    coming out identical row for row.
    """
    from weather_agent import database as db
    raiz = tmp_path / "store"
    # tres instantaneas del mismo universo, con un valor que cambia y el universo
    # creciendo — que es la forma que tiene el catalogo de la caja
    for i, (tick, extra, hora) in enumerate(((0.01, 0, 9), (0.01, 2, 12), (0.001, 4, 15))):
        _plantar(raiz, "markets", _snapshot(5, tick=tick, extra=extra),
                 run_id=f"col_2026091{2}T{hora:02d}0705Z_aaaaaa",
                 when=dt.datetime(2026, 9, 12, hora, 7, tzinfo=dt.timezone.utc))

    nuevo, res_nuevo = _cargar(raiz, "markets", db)
    assert res_nuevo["replay"] == "newest_first"

    monkeypatch.setattr(store, "_newest_first", lambda shards: None)
    viejo, res_viejo = _cargar(raiz, "markets", db)
    assert res_viejo["replay"] == "full"

    assert nuevo == viejo, "el replay nuevo-primero no reproduce la tabla completa"
    assert res_nuevo["rows_written"] < res_viejo["rows_written"], (
        f"no ahorro nada: {res_nuevo['rows_written']} contra "
        f"{res_viejo['rows_written']} — si no salta filas, no hace lo que dice")
    assert res_nuevo["rows_read"] == res_viejo["rows_read"], (
        "rows_read tiene que seguir siendo lo OFRECIDO: se leen todos los shards "
        "en los dos modos, y sólo cambia lo que se aplica")


def test_a_tie_inside_one_day_DISABLES_it_rather_than_guessing(tmp_path):
    """Two shards in one directory and one without an instant: full replay.

    Fail-CLOSED is the danger here, not fail-open: an unrecognised shard that
    really was the newest would be visited last and its rows dropped for older
    ones. So anything unresolvable degrades to today's behaviour, which is
    order-insensitive and always correct.
    """
    raiz = tmp_path / "store"
    cuando = dt.datetime(2026, 9, 9, 18, 53, tzinfo=dt.timezone.utc)
    _plantar(raiz, "markets", _snapshot(2, tick=0.01),
             run_id="col_20260909T185316Z_77df77", when=cuando)
    _plantar(raiz, "markets", _snapshot(2, tick=0.01),
             run_id="cyc_34369049661", when=cuando)          # mismo dia, sin marca
    assert store._newest_first(store.iter_shards(raiz, "markets")) is None


def test_an_undated_shard_ALONE_in_its_day_does_not_disable_it(tmp_path):
    """And this is why the rule is per DIRECTORY and not per filename.

    The store's oldest `markets` shard is `cyc_34369049661`, an Actions id with
    no timestamp. It sits alone in `2026/09/09`. A rule demanding every filename
    parse would refuse the whole table — disabling the optimisation on exactly
    the table that needs it most, `load:markets`, which went 109 s -> 462 s in
    sixteen hours and is the stage the catalogue gate can never skip.
    """
    raiz = tmp_path / "store"
    _plantar(raiz, "markets", _snapshot(2, tick=0.01), run_id="cyc_34369049661",
             when=dt.datetime(2026, 9, 9, 18, 53, tzinfo=dt.timezone.utc))
    _plantar(raiz, "markets", _snapshot(3, tick=0.001),
             run_id="col_20260912T180705Z_84bd52",
             when=dt.datetime(2026, 9, 12, 18, 7, tzinfo=dt.timezone.utc))
    orden = store._newest_first(store.iter_shards(raiz, "markets"))
    assert orden is not None and "col_20260912T180705Z" in orden[0].name, (
        f"orden={[p.name for p in (orden or [])]}")


def test_a_ledger_shaped_table_is_unaffected(tmp_path):
    """Unique conflict keys means nothing is ever skipped: same rows, same count.

    Said with a test because "harmless" is a claim about behaviour, and the
    optimisation costs a set lookup per row that must buy something or be inert.
    """
    from weather_agent import database as db
    raiz = tmp_path / "store"
    for h in (9, 12):
        filas = [{"token_id": f"t{h}{i}", "observation_time": f"2026-09-12T{h:02d}:00:00Z",
                  "dataset_version": "ds1", "record_version": 1, "indicative_price": 0.5}
                 for i in range(4)]
        store.write_shard(filas, table="price_history",
                          run_id=f"col_20260912T{h:02d}0705Z_aaaaaa", root=raiz,
                          when=dt.datetime(2026, 9, 12, h, 7, tzinfo=dt.timezone.utc))
    con = db.init_db(db.connect(":memory:"))
    out = store.load_shards(con, table="price_history", root=raiz)
    assert out["rows_read"] == out["rows_written"] == 8, out
    con.close()


def test_shard_time_reads_only_the_boxs_own_ids(tmp_path):
    assert store.shard_time("markets__col_20260912T180705Z_84bd52__0000.ndjson.gz") \
        == "20260912T180705Z"
    for otro in ("markets__cyc_34369049661__0000.ndjson.gz",
                 "markets__col_34340664711_2026-09-09__0000.ndjson.gz"):
        assert store.shard_time(otro) is None, (
            f"{otro}: un id de Actions no lleva instante, y devolver algo aqui "
            "seria inventarse el orden que esta funcion existe para no inventar")


def test_rows_written_counts_what_was_OFFERED_not_what_the_store_holds(tmp_path):
    """The second seam in `rows_loaded`, pinned so it cannot be read as continuous.

    In `newest_first` mode the rows a newer shard already claimed are never
    offered to `upsert_many`, so `rows_written` falls without anything leaving
    the store. Measured across the merge on the box:

        21:07   rows_loaded 156 776   resident 91 592   redundantes 65 184
        00:07   rows_loaded  94 130   resident 93 426   redundantes    704

    Differencing that series reads as the store shrinking by 62 646 rows, which
    never happened. `rows_read` is the invariant: it counts every row in every
    shard in both modes, which is what makes the seam detectable rather than
    silent.
    """
    from weather_agent import database as db
    raiz = tmp_path / "store"
    for h in (9, 12, 15):
        store.write_shard(_snapshot(4, tick=0.01), table="markets",
                          run_id=f"col_20260912T{h:02d}0705Z_aaaaaa", root=raiz,
                          when=dt.datetime(2026, 9, 12, h, 7, tzinfo=dt.timezone.utc))

    con = db.init_db(db.connect(":memory:"))
    nuevo = store.load_shards(con, table="markets", root=raiz)
    con.close()
    assert nuevo["replay"] == "newest_first"

    import weather_agent.store as _s
    orig, _s._newest_first = _s._newest_first, lambda shards: None
    try:
        con = db.init_db(db.connect(":memory:"))
        viejo = store.load_shards(con, table="markets", root=raiz)
        con.close()
    finally:
        _s._newest_first = orig

    assert viejo["replay"] == "full"
    assert nuevo["rows_read"] == viejo["rows_read"] == 12, (
        "`rows_read` tiene que ser el INVARIANTE entre los dos modos: es lo que "
        "hace la costura detectable en vez de silenciosa")
    # LOS VALORES EXACTOS, no `<`. Sesion A en revision: la tesis de esta entrada
    # es que la costura NO es un redondeo, y un `<` pasaria con 11 contra 12 --
    # que es precisamente el mundo en el que la tesis es falsa. El fixture es
    # determinista: tres instantaneas de las MISMAS cuatro claves, asi que el
    # replay completo ofrece 12 y el nuevo-primero 4.
    assert (nuevo["rows_written"], viejo["rows_written"]) == (4, 12), (
        f"{nuevo['rows_written']} contra {viejo['rows_written']}: se esperaban "
        "4 y 12 exactos. Un margen menor no distingue esta costura de un "
        "redondeo, que es lo unico que este test existe para distinguir")
