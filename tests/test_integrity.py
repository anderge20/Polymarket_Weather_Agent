"""
test_integrity.py — Phase 2B token & catalog integrity (#5)
===========================================================
STATUS: IMPLEMENTED, NOT EXECUTED here. Runnable on Hetzner.

Within a dataset_version a token_id must map to EXACTLY one market_id. The
`outcomes` PK (token_id, dataset_version, record_version) ENFORCES one row per
token per dataset — but a differing market_id would silently OVERWRITE, so the
violation is only visible BEFORE the write. These tests therefore check the
BUILT records (pre-upsert) for the conflict, plus a post-ingest sanity check on
the real sample.
"""
from __future__ import annotations

from weather_agent import database as db
from weather_agent.polymarket import discovery
from gamma_fixtures import NYC_EVENT, ANKARA_EVENT


def _token_market_map(records):
    tm: dict = {}
    for rec in records:
        mid = rec["market"]["market_id"]
        for o in rec["outcomes"]:
            tm.setdefault(o["token_id"], set()).add(mid)
    return tm


def test_token_maps_to_one_market_in_build():
    tm = _token_market_map(discovery.build_market_records(NYC_EVENT))
    tm2 = _token_market_map(discovery.build_market_records(ANKARA_EVENT))
    assert all(len(v) == 1 for v in tm.values())
    assert all(len(v) == 1 for v in tm2.values())


def test_duplicate_token_across_markets_is_detected_in_build():
    # craft an event whose two markets SHARE a clobTokenId -> DATA_ERROR (a token
    # in >1 market_id). Detected at BUILD time, before the outcomes PK overwrites.
    ev = {
        "id": "evX", "title": "Highest temperature in Testville on August 20?",
        "tags": [{"id": "104596"}],
        "markets": [
            dict(NYC_EVENT["markets"][0], id="mA",
                 clobTokenIds="[\"DUPTOKEN\", \"tokA2\"]"),
            dict(NYC_EVENT["markets"][1], id="mB",
                 clobTokenIds="[\"DUPTOKEN\", \"tokB2\"]"),
        ],
    }
    tm = _token_market_map(discovery.build_market_records(ev))
    assert tm["DUPTOKEN"] == {"mA", "mB"}          # conflict surfaced
    assert any(len(v) > 1 for v in tm.values())    # -> DATA_ERROR condition


def test_real_sample_has_no_token_conflict_after_ingest(con):
    discovery.ingest_event(con, NYC_EVENT, "ds_int")
    discovery.ingest_event(con, ANKARA_EVENT, "ds_int")
    bad = db.query(con, (
        "SELECT token_id FROM outcomes WHERE dataset_version = 'ds_int' "
        "GROUP BY token_id HAVING COUNT(DISTINCT market_id) > 1"
    ))
    assert bad == []
