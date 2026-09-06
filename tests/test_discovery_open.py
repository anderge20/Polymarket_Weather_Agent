"""
test_discovery_open.py — R26: discovery of OPEN markets (paper-mode feed)
=========================================================================
Exercises discover(closed=False) / fetch_events_page(closed=...) / ingest_event(
observed_at=...) against an OFFLINE stub session (no Gamma/CLOB/Open-Meteo calls)
serving the real closed fixtures + OPEN_EVENT (derived from ANKARA_EVENT).

Contract under test (docs/DISCOVERY_OPEN_MARKETS.md):
  (a) closed=False persists the open market with available_at NOT NULL and
      available_at_confidence == 'OBSERVED_AT_DISCOVERY'; the value is the
      instant the page request was issued (bounded by the test's own clock).
  (b) closed=True (default) keeps available_at NULL / 'UNKNOWN' (2B policy).
  (c) the two modes use DISTINCT checkpoint keys (dsv vs dsv + ':open').
  (d) as-of: latest_asof('markets', asof=T) does NOT return an open market
      observed after T (and closed-mode rows with NULL available_at are never
      returned by an as-of read).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from weather_agent import database as db
from weather_agent.polymarket import discovery
from gamma_fixtures import ANKARA_EVENT, NYC_EVENT, OPEN_EVENT

OBS = discovery.AVAILABLE_AT_OBSERVED


class _Resp:
    def __init__(self, payload, status=200):
        self.status_code = status
        self.headers = {}
        self._payload = payload

    def json(self):
        return self._payload


class _Session:
    """Offline gamma stub. Dispatches on params['closed'] (so the test proves the
    parameter is actually SENT): 'true' -> the real closed fixtures, 'false' ->
    the open fixture. First page only; empty afterwards. Records every call."""
    def __init__(self, closed_events=None, open_events=None):
        self.headers = {}
        self.calls: list[dict] = []
        self.closed_events = closed_events if closed_events is not None else [NYC_EVENT, ANKARA_EVENT]
        self.open_events = open_events if open_events is not None else [OPEN_EVENT]

    def get(self, url, params=None, timeout=None):
        p = dict(params or {})
        self.calls.append(p)
        if p.get("offset", 0) != 0:
            return _Resp([])
        if str(p.get("closed")).lower() == "false":
            return _Resp(self.open_events)
        return _Resp(self.closed_events)


def _market(con, market_id, dsv):
    rows = db.query(con, "SELECT * FROM markets WHERE market_id = ? AND dataset_version = ?",
                    [market_id, dsv])
    assert len(rows) == 1
    return rows[0]


def _utc(dt) -> datetime:
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc)


# ------------------------------------------------------------------ fixture sanity
def test_open_fixture_is_open_and_unresolved():
    recs = discovery.build_market_records(OPEN_EVENT)
    assert len(recs) == 1
    m = recs[0]["market"]
    assert m["winning_outcome"] is None                 # unresolved
    assert m["close_time"] is None                      # no closedTime yet
    assert m["resolution_timestamp"] is None            # no umaEndDate yet
    assert m["station_identifier"] == "LTAC"            # real chain preserved
    assert m["fee_regime"] == "weather_fees"
    assert _utc(m["source_timestamps"]["endDate"]) > datetime.now(timezone.utc)
    assert all(o["is_winner"] is False for o in recs[0]["outcomes"])
    # pure builder never sets availability (policy is applied by ingest_event)
    assert m["available_at"] is None and m["available_at_confidence"] == "UNKNOWN"
    assert ANKARA_EVENT["markets"][0]["id"] != OPEN_EVENT["markets"][0]["id"]


# ------------------------------------------------------------------ (a) open mode
def test_discover_open_sets_available_at_observed(con):
    sess = _Session()
    t0 = datetime.now(timezone.utc)
    summary = discovery.discover(con, "ds_open", session=sess, page_limit=100,
                                 max_pages=2, closed=False)
    t1 = datetime.now(timezone.utc)
    assert summary["status"] == "OK" and summary["events"] == 1
    assert summary["closed"] is False
    assert summary["checkpoint_key"] == "ds_open:open"
    # the query actually asked gamma for closed=false
    assert all(c["closed"] == "false" for c in sess.calls)

    m = _market(con, "9990101", "ds_open")
    assert m["available_at"] is not None
    assert m["available_at_confidence"] == OBS
    # prospective capture: bounded by the request window of THIS run, and never
    # equal to a gamma timestamp (createdAt/startDate are in 2030 here)
    assert t0 <= _utc(m["available_at"]) <= t1
    assert _utc(m["available_at"]) != _utc(m["source_timestamp"])
    # ingestion_timestamp stays a separate clock (not asserted equal)
    assert m["ingestion_timestamp"] is not None
    assert m["winning_outcome"] is None

    # dataset_versions records the population the version was built from
    dv = db.query(con, "SELECT query_parameters FROM dataset_versions WHERE version='ds_open'")[0]
    import json
    qp = dv["query_parameters"]
    qp = json.loads(qp) if isinstance(qp, str) else qp
    assert qp["closed"] == "false"

    # evidence row documents the policy and moves available_at out of unknown_fields
    dq = db.query(con, "SELECT market_data_quality FROM data_quality WHERE ref='9990101'")[0]
    mdq = dq["market_data_quality"]
    mdq = json.loads(mdq) if isinstance(mdq, str) else mdq
    assert mdq["available_at_policy"] == OBS
    assert "available_at" not in mdq["unknown_fields"]
    assert mdq["observed_fields"] == ["available_at"]
    assert mdq["observed_at"] is not None


def test_open_rediscovery_keeps_earliest_available_at(con):
    """Re-ingesting the SAME open market later must not push available_at
    forward: availability = first instant we could have known it."""
    early = "2026-09-06T08:00:00+00:00"
    later = "2026-09-06T09:00:00+00:00"
    discovery.ingest_event(con, OPEN_EVENT, "ds_re", observed_at=early)
    discovery.ingest_event(con, OPEN_EVENT, "ds_re", observed_at=later)
    m = _market(con, "9990101", "ds_re")
    assert _utc(m["available_at"]) == _utc(early)
    assert m["available_at_confidence"] == OBS
    # and an EARLIER re-observation (e.g. a replayed page) does move it back
    earlier = "2026-09-06T07:30:00+00:00"
    discovery.ingest_event(con, OPEN_EVENT, "ds_re", observed_at=earlier)
    assert _utc(_market(con, "9990101", "ds_re")["available_at"]) == _utc(earlier)
    assert db.query(con, "SELECT COUNT(*) c FROM markets WHERE dataset_version='ds_re'")[0]["c"] == 1


def test_closed_rerun_same_dsv_preserves_open_available_at(con):
    """H1 (R26 review): the paper flow. A market discovered OPEN (available_at
    observed) is re-processed from the CLOSED catalogue under the SAME
    dataset_version once it resolves (separate checkpoint keys => it is NOT
    skipped). The closed payload must refresh the resolution but a NULL must
    never destroy the first-hand observation of available_at."""
    import copy
    import json
    dsv = "ds_h1"
    resolved = copy.deepcopy(OPEN_EVENT)          # same market, now closed/resolved
    resolved["closed"] = True
    resolved["markets"][0]["closed"] = True
    resolved["markets"][0]["outcomePrices"] = "[\"1\", \"0\"]"
    resolved["markets"][0]["closedTime"] = "2030-08-20 15:00:00+00"

    s1 = discovery.discover(con, dsv, session=_Session(open_events=[OPEN_EVENT]), closed=False)
    assert s1["events"] == 1
    before = _market(con, "9990101", dsv)
    assert before["available_at"] is not None and before["available_at_confidence"] == OBS
    assert before["winning_outcome"] is None

    s2 = discovery.discover(con, dsv, session=_Session(closed_events=[resolved]), closed=True)
    assert s2["events"] == 1                       # re-processed (separate checkpoint)
    after = _market(con, "9990101", dsv)
    assert after["winning_outcome"] is not None    # resolution DID arrive
    assert after["close_time"] is not None
    # INVARIANT: NULL never overwrites an observation
    assert after["available_at"] is not None
    assert _utc(after["available_at"]) == _utc(before["available_at"])
    assert after["available_at_confidence"] == OBS
    # evidence says the value was preserved, not re-observed and not unknown
    mdq = db.query(con, "SELECT market_data_quality FROM data_quality WHERE ref='9990101' "
                        "AND dataset_version=?", [dsv])[0]["market_data_quality"]
    mdq = json.loads(mdq) if isinstance(mdq, str) else mdq
    assert mdq["available_at_policy"] == discovery.AVAILABLE_AT_PRESERVED
    assert "available_at" not in mdq["unknown_fields"]
    assert mdq["observed_fields"] == ["available_at"]
    # and the as-of read still returns the market after its discovery instant
    got = db.latest_asof(con, "markets", asof=_utc(before["available_at"]) + timedelta(days=1),
                         partition_cols=["market_id"])
    assert [g["market_id"] for g in got] == ["9990101"]
    assert got[0]["winning_outcome"] == after["winning_outcome"]
    # both checkpoint keys hold the event
    assert db.checkpoint_load(con, dsv) == {"9990001"}
    assert db.checkpoint_load(con, dsv + ":open") == {"9990001"}


def test_discovered_at_is_first_discovery_across_reingests(con):
    """database.py documents discovered_at as 'first discovery': daily paper
    polling re-ingests the same row and must not push it forward."""
    import time
    discovery.ingest_event(con, OPEN_EVENT, "ds_disc", observed_at="2026-09-06T08:00:00+00:00")
    first = _market(con, "9990101", "ds_disc")["discovered_at"]
    time.sleep(0.01)
    discovery.ingest_event(con, OPEN_EVENT, "ds_disc", observed_at="2026-09-06T09:00:00+00:00")
    time.sleep(0.01)
    discovery.ingest_event(con, OPEN_EVENT, "ds_disc")                  # closed-mode re-ingest
    row = _market(con, "9990101", "ds_disc")
    assert _utc(row["discovered_at"]) == _utc(first)
    assert _utc(row["ingestion_timestamp"]) > _utc(first)               # write clock DOES advance


# ------------------------------------------------------------------ (b) closed mode
def test_discover_closed_default_keeps_available_at_null(con):
    sess = _Session()
    summary = discovery.discover(con, "ds_closed", session=sess, page_limit=100, max_pages=2)
    assert summary["status"] == "OK" and summary["events"] == 2
    assert summary["closed"] is True
    assert summary["checkpoint_key"] == "ds_closed"      # byte-identical to pre-R26
    assert all(c["closed"] == "true" for c in sess.calls)
    rows = db.query(con, "SELECT available_at, available_at_confidence FROM markets "
                         "WHERE dataset_version = 'ds_closed'")
    assert len(rows) == 4
    assert all(r["available_at"] is None and r["available_at_confidence"] == "UNKNOWN"
               for r in rows)
    # the open fixture was NOT ingested in closed mode
    assert db.query(con, "SELECT COUNT(*) c FROM markets WHERE market_id='9990101'")[0]["c"] == 0


def test_ingest_event_default_observed_at_none_is_2b_policy(con):
    discovery.ingest_event(con, OPEN_EVENT, "ds_plain")        # no observed_at
    m = _market(con, "9990101", "ds_plain")
    assert m["available_at"] is None and m["available_at_confidence"] == "UNKNOWN"


# ------------------------------------------------------------------ (c) checkpoints
def test_checkpoint_keys_are_separate_per_mode(con):
    assert discovery.checkpoint_key("dsv") == "dsv"
    assert discovery.checkpoint_key("dsv", closed=True) == "dsv"
    assert discovery.checkpoint_key("dsv", closed=False) == "dsv:open"

    sess = _Session()
    s1 = discovery.discover(con, "ds_ck", session=sess, page_limit=100, max_pages=2, closed=True)
    assert s1["events"] == 2
    assert db.checkpoint_load(con, "ds_ck") == {"128661", "869074"}
    assert db.checkpoint_load(con, "ds_ck:open") == set()

    s2 = discovery.discover(con, "ds_ck", session=sess, page_limit=100, max_pages=2, closed=False)
    assert s2["events"] == 1
    assert db.checkpoint_load(con, "ds_ck:open") == {"9990001"}
    assert db.checkpoint_load(con, "ds_ck") == {"128661", "869074"}   # untouched

    # cross-contamination check: an event id already checkpointed as CLOSED is
    # still processed when it appears OPEN (and vice versa). Serve ANKARA (closed
    # checkpoint) on the open feed under the same dsv and prove it is ingested.
    sess2 = _Session(open_events=[ANKARA_EVENT])
    s3 = discovery.discover(con, "ds_ck", session=sess2, page_limit=100, max_pages=2, closed=False)
    assert s3["events"] == 1
    assert db.checkpoint_load(con, "ds_ck:open") == {"9990001", "869074"}
    # resume within a mode still skips
    s4 = discovery.discover(con, "ds_ck", session=sess, page_limit=100, max_pages=2, closed=False)
    assert s4["events"] == 0


def test_open_checkpoint_persists_and_resumes(con):
    sess = _Session()
    discovery.discover(con, "ds_res", session=sess, page_limit=100, max_pages=2, closed=False)
    rows = db.query(con, "SELECT dataset_version, event_id FROM discovery_checkpoint "
                         "WHERE dataset_version = 'ds_res:open'")
    assert [(r["dataset_version"], r["event_id"]) for r in rows] == [("ds_res:open", "9990001")]
    again = discovery.discover(con, "ds_res", session=sess, page_limit=100, max_pages=2, closed=False)
    assert again["events"] == 0                       # resumed from the persisted mark
    assert db.query(con, "SELECT COUNT(*) c FROM markets WHERE dataset_version='ds_res'")[0]["c"] == 1


# ------------------------------------------------------------------ (d) as-of
def test_asof_excludes_open_market_observed_after_T(con):
    assert db.AS_OF_COLUMNS["markets"] == "available_at"
    observed = "2026-09-06T10:00:00+00:00"
    discovery.ingest_event(con, OPEN_EVENT, "ds_asof", observed_at=observed)
    discovery.ingest_event(con, ANKARA_EVENT, "ds_asof")          # closed policy: NULL

    before = _utc(observed) - timedelta(hours=1)
    after = _utc(observed) + timedelta(hours=1)
    # T before the observation: the open market is NOT knowable -> not returned
    assert db.latest_asof(con, "markets", asof=before, partition_cols=["market_id"]) == []
    assert db.query_asof(con, "markets", asof=before) == []
    # T after: returned, exactly once, with the observed instant
    got = db.latest_asof(con, "markets", asof=after, partition_cols=["market_id"])
    assert [g["market_id"] for g in got] == ["9990101"]
    assert _utc(got[0]["available_at"]) == _utc(observed)
    # the closed-mode row (available_at NULL) is NEVER returned by an as-of read,
    # however late T is: we do not invent retrospective availability
    far = _utc(observed) + timedelta(days=3650)
    assert [g["market_id"] for g in db.query_asof(con, "markets", asof=far)] == ["9990101"]
    # boundary: exactly T == available_at is knowable (<=)
    assert len(db.latest_asof(con, "markets", asof=_utc(observed))) == 1


# ------------------------------------------------------------------ fetch_events_page
def test_fetch_events_page_closed_param_and_meta():
    sess = _Session()
    meta: dict = {}
    t0 = datetime.now(timezone.utc)
    status, events = discovery.fetch_events_page(sess, {"tag_id": 1, "limit": 5},
                                                 closed=False, meta=meta, max_retries=0)
    t1 = datetime.now(timezone.utc)
    assert status == "OK" and [e["id"] for e in events] == ["9990001"]
    assert sess.calls[-1]["closed"] == "false"
    assert meta["attempts"] == 1 and meta["params"]["closed"] == "false"
    assert t0 <= _utc(meta["requested_at"]) <= _utc(meta["responded_at"]) <= t1
    # default closed=True -> closed=true, 2B behaviour; caller's params not mutated
    p = {"tag_id": 1, "limit": 5}
    status, events = discovery.fetch_events_page(sess, p, max_retries=0)
    assert status == "OK" and sess.calls[-1]["closed"] == "true" and "closed" not in p
    # explicit params['closed'] consistent with the flag is accepted verbatim
    status, _ = discovery.fetch_events_page(sess, {"closed": "false"}, closed=False, max_retries=0)
    assert status == "OK"
    # contradiction is refused (never silently query the wrong population)
    with pytest.raises(ValueError):
        discovery.fetch_events_page(sess, {"closed": "true"}, closed=False, max_retries=0)
    with pytest.raises(ValueError):
        discovery.fetch_events_page(sess, {"closed": "false"}, max_retries=0)


def test_fetch_events_page_meta_on_error_status():
    class _Err(_Session):
        def get(self, url, params=None, timeout=None):
            self.calls.append(dict(params or {}))
            return _Resp(None, status=500)
    meta: dict = {}
    status, events = discovery.fetch_events_page(_Err(), {}, closed=False, meta=meta, max_retries=0)
    assert status == "HTTP_ERROR" and events == []
    assert meta["requested_at"] is not None and meta["attempts"] == 1


def test_discover_open_stops_on_error_without_inference(con):
    class _Err(_Session):
        def get(self, url, params=None, timeout=None):
            self.calls.append(dict(params or {}))
            return _Resp(None, status=429)
    s = discovery.discover(con, "ds_err", session=_Err(), page_limit=5, max_pages=1, closed=False)
    assert s["status"] == "RATE_LIMITED" and s["stopped_early"] is True and s["events"] == 0
    assert db.query(con, "SELECT COUNT(*) c FROM markets WHERE dataset_version='ds_err'")[0]["c"] == 0
