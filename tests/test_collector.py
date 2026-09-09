"""Tests for weather_agent.collector (R22) — offline, no network.

The book fixtures reproduce the SHAPE observed live on 2026-09-09, including the
detail that bit hardest: `asks` came back sorted DESCENDING by price, so the best
ask was the last element. Several tests exist only to pin that the collector never
indexes [0].
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from weather_agent import collector


# --------------------------------------------------------------------------- fixtures
def _book(asset_id="TOK1", *, bids=None, asks=None, hash_="h1", ts="1788937456569",
          market="0xmarket"):
    return {
        "market": market,
        "asset_id": asset_id,
        "timestamp": ts,
        "hash": hash_,
        "bids": bids if bids is not None else [
            # deliberately ASCENDING: best bid (highest) is last
            {"price": "0.40", "size": "10"},
            {"price": "0.45", "size": "20"},
            {"price": "0.48", "size": "30"},
        ],
        "asks": asks if asks is not None else [
            # deliberately DESCENDING, as observed live: best ask (lowest) is last
            {"price": "0.70", "size": "100"},
            {"price": "0.60", "size": "50"},
            {"price": "0.52", "size": "25"},
        ],
    }


class FakeResp:
    def __init__(self, status_code=200, payload=None, raise_json=False):
        self.status_code = status_code
        self._payload = payload
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Records calls; replays a queue of responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.posts: list[tuple[str, object]] = []
        self.gets: list[tuple[str, object]] = []

    def _next(self):
        if not self._responses:
            raise AssertionError("FakeSession ran out of scripted responses")
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def post(self, url, json=None, timeout=None):
        self.posts.append((url, json))
        return self._next()

    def get(self, url, params=None, timeout=None):
        self.gets.append((url, params))
        return self._next()


# --------------------------------------------------------------------------- book_top
def test_best_prices_ignore_payload_order():
    top = collector.book_top(_book())
    assert top["best_bid"] == 0.48      # max bid, NOT bids[0]
    assert top["best_ask"] == 0.52      # min ask, NOT asks[0]
    assert top["mid"] == pytest.approx(0.50)
    assert top["spread"] == pytest.approx(0.04)


def test_depth_is_summed_over_best_k_levels():
    top = collector.book_top(_book())
    assert top["bid_depth_1"] == 30.0                 # 0.48
    assert top["bid_depth_5"] == 60.0                 # all three levels exist
    assert top["bid_depth_10"] == 60.0                # fewer than k -> what exists
    assert top["ask_depth_1"] == 25.0                 # 0.52
    assert top["ask_depth_5"] == 175.0


def test_imbalance_sign_and_range():
    top = collector.book_top(_book())
    b, a = top["bid_depth_10"], top["ask_depth_10"]
    assert top["imbalance"] == pytest.approx((b - a) / (b + a))
    assert -1.0 <= top["imbalance"] <= 1.0
    assert top["imbalance"] < 0                       # ask-heavy book


def test_empty_book_is_an_observation_not_an_error():
    top = collector.book_top(_book(bids=[], asks=[]))
    assert top["best_bid"] is None and top["best_ask"] is None
    assert top["mid"] is None and top["spread"] is None
    assert top["imbalance"] is None                   # 0/0 -> NULL, not 0.0
    assert top["bid_depth_1"] == 0.0                  # depth of an empty side is 0


def test_one_sided_book_has_no_mid_or_spread():
    top = collector.book_top(_book(bids=[]))
    assert top["best_bid"] is None
    assert top["best_ask"] == 0.52
    assert top["mid"] is None and top["spread"] is None
    assert top["imbalance"] == pytest.approx(-1.0)    # all depth on the ask side


def test_unparseable_levels_are_dropped_not_coerced():
    book = _book(bids=[{"price": "abc", "size": "1"}, {"price": "0.30", "size": "5"},
                       {"price": "0.31"}, "garbage"])
    top = collector.book_top(book)
    assert top["best_bid"] == 0.30
    assert top["bid_depth_10"] == 5.0
    assert top["n_bid_levels"] == 1


# --------------------------------------------------------------------------- rows
def test_snapshot_row_keys_the_row_on_our_clock_not_the_exchange():
    t0 = datetime(2026, 9, 9, 7, 0, tzinfo=timezone.utc)
    row = collector.book_snapshot_row(
        _book(), collected_at=t0, collector_session_id="cyc1",
        collector_started_at=t0, dataset_version="ds1",
    )
    assert row["timestamp"] == t0.isoformat()
    assert row["book_snapshot"]["exchange_timestamp_ms"] == 1788937456569
    assert row["book_snapshot"]["hash"] == "h1"
    assert row["collector_session_id"] == "cyc1"
    assert row["source"] == collector.SOURCE_BOOK


def test_snapshot_row_accepts_an_explicit_market_id_override():
    t0 = datetime(2026, 9, 9, 7, 0, tzinfo=timezone.utc)
    row = collector.book_snapshot_row(
        _book(), collected_at=t0, collector_session_id="c", collector_started_at=t0,
        dataset_version="ds1", market_id="gamma-123",
    )
    assert row["market_id"] == "gamma-123"


def test_trade_fingerprint_is_stable_and_discriminating():
    tr = {"transactionHash": "0xabc", "asset": "TOK", "proxyWallet": "0xw",
          "side": "BUY", "size": 12.02, "price": 0.999, "timestamp": 1788936388}
    assert collector.trade_fingerprint(tr) == collector.trade_fingerprint(dict(tr))
    other = dict(tr, size=12.03)
    assert collector.trade_fingerprint(other) != collector.trade_fingerprint(tr)
    # two fills in ONE transaction must not collapse
    same_tx = dict(tr, price=0.998)
    assert collector.trade_fingerprint(same_tx) != collector.trade_fingerprint(tr)


def test_trade_row_drops_unusable_payloads():
    base = {"transactionHash": "0x1", "asset": "T", "proxyWallet": "0xw",
            "side": "BUY", "size": 1, "price": 0.5, "timestamp": 1788936388,
            "conditionId": "0xc"}
    t0 = datetime(2026, 9, 9, 7, 0, tzinfo=timezone.utc)
    kw = dict(fetched_at=t0, collector_session_id="c", collector_started_at=t0,
              dataset_version="ds1")
    assert collector.trade_row(base, **kw) is not None
    assert collector.trade_row(dict(base, side="LONG"), **kw) is None
    assert collector.trade_row(dict(base, timestamp=None), **kw) is None
    assert collector.trade_row(dict(base, price="n/a"), **kw) is None


# --------------------------------------------------------------------------- fetching
def test_fetch_books_chunks_the_request():
    resp = FakeResp(200, [_book("A"), _book("B")])
    s = FakeSession([resp, FakeResp(200, [_book("C")])])
    res = collector.fetch_books(s, ["A", "B", "C"], chunk_size=2, delay_s=0,
                                sleep=lambda _s: None)
    assert res["requests"] == 2 and res["stopped"] is False
    assert [len(p[1]) for p in s.posts] == [2, 1]
    assert s.posts[0][1] == [{"token_id": "A"}, {"token_id": "B"}]
    assert len(res["books"]) == 3


def test_fetch_books_stops_on_429_and_keeps_what_it_had():
    s = FakeSession([FakeResp(200, [_book("A")]), FakeResp(429, None)])
    res = collector.fetch_books(s, ["A", "B"], chunk_size=1, delay_s=0,
                               sleep=lambda _s: None)
    assert res["stopped"] is True
    assert res["error"] == "http_429_rate_limited"
    assert len(res["books"]) == 1               # partial result is preserved
    assert res["requests"] == 2                 # and it did NOT retry the 429


def test_fetch_books_stops_on_transport_error():
    s = FakeSession([ConnectionError("boom")])
    res = collector.fetch_books(s, ["A"], delay_s=0, sleep=lambda _s: None)
    assert res["stopped"] is True and "transport" in res["error"]


def test_fetch_books_rejects_an_unexpected_payload_shape():
    s = FakeSession([FakeResp(200, "not-a-list")])
    res = collector.fetch_books(s, ["A"], delay_s=0, sleep=lambda _s: None)
    assert res["stopped"] is True and res["error"] == "unexpected_payload_shape"


def test_fetch_trades_stops_on_429():
    s = FakeSession([FakeResp(429, None)])
    res = collector.fetch_trades(s, "0xc")
    assert res["stopped"] is True and res["error"] == "http_429_rate_limited"


# --------------------------------------------------------------------------- cycles
def test_collect_books_persists_rows(con):
    s = FakeSession([FakeResp(200, [_book("A"), _book("B")])])
    out = collector.collect_books(
        con, ["A", "B"], dataset_version="ds1", collector_session_id="cyc1",
        session=s, delay_s=0,
    )
    assert out["rows_written"] == 2 and out["stopped"] is False
    rows = con.execute("SELECT token_id, best_bid, best_ask, collector_session_id "
                       "FROM orderbook_snapshots ORDER BY token_id").fetchall()
    assert [r[0] for r in rows] == ["A", "B"]
    assert rows[0][1] == 0.48 and rows[0][2] == 0.52
    assert rows[0][3] == "cyc1"


def test_cycle_resumes_where_it_stopped(con):
    """R22's resumption criterion: a cancelled cycle finishes on the next run and
    does NOT re-collect what it already has."""
    s1 = FakeSession([FakeResp(200, [_book("A")]), FakeResp(429, None)])
    first = collector.collect_books(
        con, ["A", "B"], dataset_version="ds1", collector_session_id="cyc1",
        session=s1, chunk_size=1, delay_s=0,
    )
    assert first["stopped"] is True and first["rows_written"] == 1

    s2 = FakeSession([FakeResp(200, [_book("B")])])
    second = collector.collect_books(
        con, ["A", "B"], dataset_version="ds1", collector_session_id="cyc1",
        session=s2, chunk_size=10, delay_s=0,
    )
    assert second["tokens_pending"] == 1                 # A is already stored
    assert s2.posts[0][1] == [{"token_id": "B"}]         # only B was requested
    assert second["rows_written"] == 1
    n = con.execute("SELECT count(*) FROM orderbook_snapshots").fetchone()[0]
    assert n == 2


def test_completed_cycle_is_a_noop_on_re_run(con):
    s1 = FakeSession([FakeResp(200, [_book("A")])])
    collector.collect_books(con, ["A"], dataset_version="ds1",
                            collector_session_id="cyc1", session=s1, delay_s=0)
    s2 = FakeSession([])                                  # any request would blow up
    out = collector.collect_books(con, ["A"], dataset_version="ds1",
                                  collector_session_id="cyc1", session=s2, delay_s=0)
    assert out["tokens_pending"] == 0 and out["rows_written"] == 0
    assert s2.posts == []


def test_a_new_cycle_id_collects_again(con):
    """Resumption must not become deduplication: the same token in a LATER cycle
    is a new observation of the market and has to be stored."""
    s1 = FakeSession([FakeResp(200, [_book("A")])])
    collector.collect_books(con, ["A"], dataset_version="ds1",
                            collector_session_id="cyc1", session=s1, delay_s=0)
    s2 = FakeSession([FakeResp(200, [_book("A", hash_="h2")])])
    out = collector.collect_books(con, ["A"], dataset_version="ds1",
                                  collector_session_id="cyc2", session=s2, delay_s=0)
    assert out["rows_written"] == 1
    n = con.execute("SELECT count(DISTINCT collector_session_id) "
                    "FROM orderbook_snapshots").fetchone()[0]
    assert n == 2


def test_duplicate_tokens_in_the_request_are_polled_once(con):
    s = FakeSession([FakeResp(200, [_book("A")])])
    out = collector.collect_books(con, ["A", "A", "A"], dataset_version="ds1",
                                  collector_session_id="cyc1", session=s, delay_s=0)
    assert out["tokens_pending"] == 1
    assert s.posts[0][1] == [{"token_id": "A"}]


def test_collect_trades_is_idempotent(con):
    tr = {"transactionHash": "0x1", "asset": "T", "proxyWallet": "0xw", "side": "BUY",
          "size": 1, "price": 0.5, "timestamp": 1788936388, "conditionId": "0xc"}
    for _ in range(2):
        s = FakeSession([FakeResp(200, [tr])])
        collector.collect_trades(con, ["0xc"], dataset_version="ds1",
                                 collector_session_id="cyc1", session=s, delay_s=0)
    n = con.execute("SELECT count(*) FROM trades").fetchone()[0]
    assert n == 1                                   # same fingerprint -> one row


def test_collect_trades_stops_on_rate_limit(con):
    s = FakeSession([FakeResp(200, []), FakeResp(429, None)])
    out = collector.collect_trades(con, ["0xa", "0xb", "0xc"], dataset_version="ds1",
                                   collector_session_id="cyc1", session=s, delay_s=0)
    assert out["stopped"] is True and out["markets_done"] == 1


def test_session_ids_are_unique_and_time_stamped():
    now = datetime(2026, 9, 9, 7, 30, tzinfo=timezone.utc)
    a = collector.new_session_id(now=now)
    b = collector.new_session_id(now=now)
    assert a.startswith("col_20260909T073000Z_") and a != b
    later = collector.new_session_id(now=now + timedelta(hours=1))
    assert later.startswith("col_20260909T083000Z_")


def test_module_holds_no_credentials_and_no_order_path():
    """Standing gate D0: paper mode must be incapable of signing or ordering."""
    src = (__import__("pathlib").Path(collector.__file__)).read_text(encoding="utf-8")
    for forbidden in ("private_key", "PRIVATE_KEY", "api_secret", "API_SECRET",
                      "sign(", "post_order", "/order"):
        assert forbidden not in src, f"collector.py must not reference {forbidden!r}"


# --------------------------------------------------------------------------- truncation
def _deep_book(n_bids=25, n_asks=30):
    return _book(
        bids=[{"price": f"{0.50 - i * 0.001:.3f}", "size": "10"} for i in range(n_bids)],
        asks=[{"price": f"{0.51 + i * 0.001:.3f}", "size": "10"} for i in range(n_asks)],
    )


def test_stored_ladder_is_truncated_but_the_measures_are_not():
    t0 = datetime(2026, 9, 9, 7, 0, tzinfo=timezone.utc)
    row = collector.book_snapshot_row(
        _deep_book(), collected_at=t0, collector_session_id="c",
        collector_started_at=t0, dataset_version="ds1", keep_levels=10,
    )
    snap = row["book_snapshot"]
    assert len(snap["bids"]) == 10 and len(snap["asks"]) == 10
    assert snap["n_bid_levels"] == 25 and snap["n_ask_levels"] == 30   # true counts
    assert snap["truncated"] is True
    # the depth columns are computed on the FULL book, so k=10 is unaffected
    assert row["bid_depth_10"] == 100.0
    assert row["best_bid"] == 0.50 and row["best_ask"] == 0.51


def test_stored_ladder_is_sorted_best_first_so_consumers_need_no_re_sort():
    t0 = datetime(2026, 9, 9, 7, 0, tzinfo=timezone.utc)
    row = collector.book_snapshot_row(
        _book(), collected_at=t0, collector_session_id="c",
        collector_started_at=t0, dataset_version="ds1",
    )
    snap = row["book_snapshot"]
    assert [lvl["price"] for lvl in snap["bids"]] == [0.48, 0.45, 0.40]
    assert [lvl["price"] for lvl in snap["asks"]] == [0.52, 0.60, 0.70]


def test_a_shallow_book_is_not_flagged_truncated():
    t0 = datetime(2026, 9, 9, 7, 0, tzinfo=timezone.utc)
    row = collector.book_snapshot_row(
        _book(), collected_at=t0, collector_session_id="c",
        collector_started_at=t0, dataset_version="ds1",
    )
    assert row["book_snapshot"]["truncated"] is False


# --------------------------------------------------------------------------- prices
def test_a_book_yields_the_matching_indicative_price():
    """The gap that made the whole cycle unable to trade: build_feature reads
    `price_history`, and nothing in the paper pipeline wrote it."""
    t0 = datetime(2026, 9, 9, 7, 0, tzinfo=timezone.utc)
    row = collector.price_row_from_book(_book(), collected_at=t0,
                                        dataset_version="ds1")
    assert row["indicative_price"] == pytest.approx(0.50)   # mid of 0.48 / 0.52
    assert row["observation_time"] == t0.isoformat()
    assert row["price_semantics"] == "MIDPOINT_ESTIMATED"
    assert row["price_semantics"] != "EXECUTABLE"           # build_feature rejects that
    assert row["price_source"] == collector.SOURCE_BOOK_MID
    assert row["fidelity"] is None                          # a point, not a 1-min series


def test_a_one_sided_book_yields_no_price_rather_than_half_a_market():
    t0 = datetime(2026, 9, 9, 7, 0, tzinfo=timezone.utc)
    assert collector.price_row_from_book(_book(bids=[]), collected_at=t0,
                                         dataset_version="ds1") is None
    assert collector.price_row_from_book(_book(asks=[]), collected_at=t0,
                                         dataset_version="ds1") is None


def test_collect_books_writes_price_history_alongside_the_book(con):
    s = FakeSession([FakeResp(200, [_book("A"), _book("B")])])
    out = collector.collect_books(con, ["A", "B"], dataset_version="ds1",
                                  collector_session_id="cyc1", session=s, delay_s=0)
    assert out["prices_written"] == 2 and out["prices_skipped_one_sided"] == 0
    rows = con.execute("SELECT token_id, indicative_price, price_semantics "
                       "FROM price_history ORDER BY token_id").fetchall()
    assert rows == [("A", 0.5, "MIDPOINT_ESTIMATED"), ("B", 0.5, "MIDPOINT_ESTIMATED")]


def test_the_price_and_the_book_come_from_the_same_observation(con):
    """They must never disagree: a decision priced off one and filled against the
    other would be measuring two different markets."""
    s = FakeSession([FakeResp(200, [_book("A")])])
    collector.collect_books(con, ["A"], dataset_version="ds1",
                            collector_session_id="cyc1", session=s, delay_s=0)
    ts_book = con.execute('SELECT "timestamp" FROM orderbook_snapshots').fetchone()[0]
    ts_price = con.execute("SELECT observation_time FROM price_history").fetchone()[0]
    assert ts_book == ts_price
    mid = con.execute("SELECT mid FROM orderbook_snapshots").fetchone()[0]
    px = con.execute("SELECT indicative_price FROM price_history").fetchone()[0]
    assert mid == px


def test_a_one_sided_book_is_counted_not_silently_dropped(con):
    s = FakeSession([FakeResp(200, [_book("A", bids=[])])])
    out = collector.collect_books(con, ["A"], dataset_version="ds1",
                                  collector_session_id="cyc1", session=s, delay_s=0)
    assert out["rows_written"] == 1          # the book IS recorded
    assert out["prices_written"] == 0
    assert out["prices_skipped_one_sided"] == 1
