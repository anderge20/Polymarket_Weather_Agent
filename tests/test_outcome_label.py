"""
test_outcome_label.py — Phase 2D: explicit YES/NO identity contract.

Contract: the YES token of a band-market is identified EXCLUSIVELY by
outcomes.outcome_label == "Yes" (captured verbatim from gamma outcomes[i]),
NEVER by outcome_index and NEVER by is_winner. Pre-v3 rows have outcome_label
NULL and must fail closed downstream.

STATUS: IMPLEMENTED, USER-RUN (no Python in the authoring env).
"""
from __future__ import annotations

import json

from weather_agent import database as db
from weather_agent.polymarket import discovery
from gamma_fixtures import NYC_EVENT, ANKARA_EVENT


def _yes_tokens(rows):
    return [o for o in rows if o.get("outcome_label") == "Yes"]


def _mk_event(outcomes, prices, tokens, eid="999", mid="999m"):
    """Synthetic event built from a REAL fixture market so all fee/tick/desc
    fields are present; only the outcome arrays are overridden."""
    m = dict(NYC_EVENT["markets"][0])
    m["id"] = mid
    m["outcomes"] = outcomes
    m["outcomePrices"] = prices
    m["clobTokenIds"] = tokens
    ev = dict(NYC_EVENT)
    ev["id"] = eid
    ev["markets"] = [m]
    return ev


def test_outcome_label_populated_from_gamma_verbatim():
    for rec in discovery.build_market_records(NYC_EVENT):
        outs = rec["outcomes"]
        assert len(outs) == 2
        assert outs[0]["outcome_label"] == "Yes"   # gamma order ["Yes","No"]
        assert outs[1]["outcome_label"] == "No"


def test_outcome_label_aligned_with_clob_token_ids():
    # Contract: outcomes[i] <-> clobTokenIds[i] <-> outcome_label.
    m = NYC_EVENT["markets"][0]
    outs = json.loads(m["outcomes"])
    tokens = json.loads(m["clobTokenIds"])
    rec0 = discovery.build_market_records(NYC_EVENT)[0]["outcomes"]
    by_token = {o["token_id"]: o["outcome_label"] for o in rec0}
    for i, tok in enumerate(tokens):
        assert by_token[str(tok)] == outs[i]


def test_outcome_label_persisted(con):
    discovery.ingest_event(con, ANKARA_EVENT, "ds_ol")
    rows = db.query(con, "SELECT outcome_label FROM outcomes "
                         "WHERE dataset_version='ds_ol' ORDER BY outcome_index")
    assert [r["outcome_label"] for r in rows] == ["Yes", "No"]


def test_yes_contract_uses_label_not_index():
    # gamma order REVERSED: outcomes=["No","Yes"] -> YES is at index 1.
    ev = _mk_event('["No", "Yes"]', '["1", "0"]', '["tokNO", "tokYES"]')
    outs = discovery.build_market_records(ev)[0]["outcomes"]
    yes = _yes_tokens(outs)
    assert len(yes) == 1
    assert yes[0]["token_id"] == "tokYES"     # index 1, NOT 0
    assert yes[0]["outcome_index"] == 1


def test_unexpected_structure_no_yes_fails_closed():
    # No "Yes" among outcomes -> zero YES tokens -> consumer MUST fail closed.
    ev = _mk_event('["Maybe", "No"]', '["0", "1"]', '["tokA", "tokB"]')
    outs = discovery.build_market_records(ev)[0]["outcomes"]
    assert _yes_tokens(outs) == []
    assert {o["outcome_label"] for o in outs} == {"Maybe", "No"}   # verbatim, no guess


def test_unexpected_length_not_two_fails_closed():
    # A clean binary band-market must have EXACTLY 2 outcomes. Length != 2 is an
    # anomaly the consumer MUST detect (fail closed), even if a "Yes" exists.
    ev = _mk_event('["Yes", "No", "Maybe"]', '["0", "1", "0"]',
                   '["tokY", "tokN", "tokM"]')
    outs = discovery.build_market_records(ev)[0]["outcomes"]
    assert len(outs) == 3                       # anomaly is visible to the consumer
    assert [o["outcome_label"] for o in outs] == ["Yes", "No", "Maybe"]
    # exactly-one-"Yes" is necessary but NOT sufficient; a consumer requires len==2.


def test_yes_can_be_loser_independent_of_is_winner():
    # Yes present but LOST (prices ["0","1"]) -> label still "Yes", is_winner False.
    ev = _mk_event('["Yes", "No"]', '["0", "1"]', '["tokYES", "tokNO"]')
    outs = discovery.build_market_records(ev)[0]["outcomes"]
    yes = _yes_tokens(outs)[0]
    assert yes["token_id"] == "tokYES"
    assert yes["outcome_label"] == "Yes"
    assert yes["is_winner"] is False          # lost, but still the YES token
