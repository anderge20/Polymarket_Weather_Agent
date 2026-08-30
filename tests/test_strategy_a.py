"""
test_strategy_a.py — Phase 2D: Strategy A V1 signal generator (unit + adversarial).

Authoritative design: PHASE_2D_STRATEGY_A_DESIGN.md. These tests exercise the V1
contracts WITHOUT reopening any 2A/2B/2C decision. STATUS: IMPLEMENTED, USER-RUN.
"""
from __future__ import annotations

import pytest

from weather_agent import database
from weather_agent import database as db
from weather_agent.features import FORBIDDEN_FEATURE_FIELDS
from weather_agent.probability import quantiles_to_distribution, band_probability
from weather_agent.strategy import generate_event_signals
from weather_agent.strategy.strategy_a import signal_for

DSV = "ds_stratA_test"
STATION = "TEST_STN"
MODEL = "test_model"
TARGET = "2026-08-20"
T = "2026-08-19T12:00:00+00:00"
OBS = "2026-08-19T11:00:00+00:00"
ISSUE = "2026-08-19T00:00:00+00:00"
AVAIL = "2026-08-19T00:30:00+00:00"
EVENT = "EVT1"
Q = dict(p10=24.0, p25=25.0, p50=25.0, p75=26.0, p90=27.0)

# A clean partition over the forecast support 24..27.
BANDS = [
    ("m1", "24°C or below", None, 24.0, "y1", "n1"),
    ("m2", "25°C", 25.0, 25.0, "y2", "n2"),
    ("m3", "26°C", 26.0, 26.0, "y3", "n3"),
    ("m4", "27°C or higher", 27.0, None, "y4", "n4"),
]
_DIST = quantiles_to_distribution(**Q)
PW = {b[0]: band_probability(_DIST, lo=b[2], hi=b[3]) for b in BANDS}

# Prices engineered to guarantee at least one BUY, one FADE and one HOLD.
_ORDER = sorted(PW, key=lambda k: PW[k])
_BUY_MID, _FADE_MID = _ORDER[-1], _ORDER[0]
PRICES = {}
for _mid in PW:
    if _mid == _BUY_MID:
        PRICES[_mid] = 0.0                       # edge = pw (large) -> BUY
    elif _mid == _FADE_MID:
        PRICES[_mid] = min(1.0, PW[_mid] + 0.5)  # edge <= -0.5 -> FADE
    else:
        PRICES[_mid] = PW[_mid]                   # edge = 0 -> HOLD

TAU = 0.05
TOL = dict(weather_sum_tolerance=1e-6, market_sum_min=0.0, market_sum_max=5.0)


# --------------------------------------------------------------------- seeding
def _seed_forecast(con, available_at=AVAIL, dsv=DSV):
    db.insert(con, "weather_forecasts", {
        "issue_time": ISSUE, "forecast_run": "00z", "target_date": TARGET,
        "city": "Testville", "station": STATION, "model": MODEL,
        "forecast_tmax": 25.5, "forecast_p10": Q["p10"], "forecast_p25": Q["p25"],
        "forecast_p50": Q["p50"], "forecast_p75": Q["p75"], "forecast_p90": Q["p90"],
        "available_at": available_at, "fetched_at": ISSUE, "source": "test",
        "ingestion_timestamp": ISSUE, "dataset_version": dsv, "record_version": 1,
    })


def _seed_band(con, market_id, band_label, lo, hi, yes_token, no_token, yes_price,
               yes_index=0, dsv=DSV, no_price=None):
    db.insert(con, "markets", {
        "market_id": market_id, "event_id": EVENT, "station": STATION, "unit": "C",
        "source": "test", "ingestion_timestamp": ISSUE,
        "dataset_version": dsv, "record_version": 1,
    })
    no_index = 1 - yes_index
    db.insert(con, "outcomes", {
        "market_id": market_id, "token_id": yes_token, "band_label": band_label,
        "lo": lo, "hi": hi, "outcome_index": yes_index, "outcome_label": "Yes",
        "source": "test", "ingestion_timestamp": ISSUE,
        "dataset_version": dsv, "record_version": 1,
    })
    db.insert(con, "outcomes", {
        "market_id": market_id, "token_id": no_token, "band_label": band_label,
        "lo": lo, "hi": hi, "outcome_index": no_index, "outcome_label": "No",
        "source": "test", "ingestion_timestamp": ISSUE,
        "dataset_version": dsv, "record_version": 1,
    })

    def _price(token, price):
        db.insert(con, "price_history", {
            "observation_time": OBS, "market_id": market_id, "token_id": token,
            "indicative_price": price, "price_semantics": "MIDPOINT_ESTIMATED",
            "price_source": "CLOB_PRICES_HISTORY", "fidelity": 1, "source_window": "DIRECT",
            "fetched_at": OBS, "source": "test", "ingestion_timestamp": ISSUE,
            "dataset_version": dsv, "record_version": 1,
        })
    if yes_price is not None:
        _price(yes_token, yes_price)
    if no_price is not None:
        _price(no_token, no_price)


def _seed_full(con, prices=None, yes_index=0, available_at=AVAIL):
    _seed_forecast(con, available_at=available_at)
    prices = prices or PRICES
    for (mid, label, lo, hi, y, n) in BANDS:
        _seed_band(con, mid, label, lo, hi, y, n, prices.get(mid), yes_index=yes_index)


def _run(con, **over):
    kw = dict(event_id=EVENT, prediction_time=T, model=MODEL, target_date=TARGET,
              dataset_version=DSV, tau=TAU, **TOL)
    kw.update(over)
    return generate_event_signals(con, **kw)


def _preds(con):
    return db.query(con, "SELECT * FROM predictions ORDER BY market_id")


def _sigs(con):
    return db.query(con, "SELECT * FROM signals ORDER BY market_id")


def _excl(con):
    return db.query(con, "SELECT * FROM markets_excluded ORDER BY market_id")


# --------------------------------------------------------------- eligible path
def test_eligible_event_writes_predictions_and_signals(con):
    _seed_full(con)
    s = _run(con)
    assert s["eligible"] is True
    assert s["predictions_written"] == 4
    assert s["signals_written"] == 4
    assert s["excluded_written"] == 0
    assert _excl(con) == []

    preds = {p["market_id"]: p for p in _preds(con)}
    sigs = {g["market_id"]: g for g in _sigs(con)}
    assert set(preds) == set(PW)
    seen = set()
    for mid in PW:
        p, g = preds[mid], sigs[mid]
        pw, price = PW[mid], PRICES[mid]
        edge = pw - price
        # contract relationships
        assert p["p_market"] == pytest.approx(price)
        assert p["p_weather"] == pytest.approx(pw)
        assert p["p_model"] == pytest.approx(pw)          # p_model = p_weather
        assert p["fair_value"] == pytest.approx(pw)       # fair_value = p_model
        assert p["edge_gross"] == pytest.approx(edge)     # edge = fair_value - p_market
        assert p["edge_net"] is None                      # net BLOCKED
        assert p["confidence"] is None                    # NULL in V1
        assert p["model_version"] == "stratA_pmodel_v1"
        assert str(p["timestamp"])[:19] == "2026-08-19 12:00:00"   # = prediction_time
        assert g["strategy"] == "strategy_a_v1"
        assert g["price_assumption"] == pytest.approx(price)
        assert g["edge"] == pytest.approx(edge)
        assert g["net_edge"] is None
        assert g["confidence"] is None
        assert str(g["timestamp"])[:19] == "2026-08-19 12:00:00"
        assert g["signal"] == signal_for(edge, TAU)
        assert g["signal"] != "SELL"
        seen.add(g["signal"])
    assert {"BUY", "FADE", "HOLD"} <= seen                 # coverage around tau


def test_signal_mapping_around_tau():
    tau = 0.1
    assert signal_for(0.2, tau) == "BUY"
    assert signal_for(0.1, tau) == "BUY"      # boundary edge >= +tau
    assert signal_for(0.05, tau) == "HOLD"
    assert signal_for(0.0, tau) == "HOLD"
    assert signal_for(-0.05, tau) == "HOLD"
    assert signal_for(-0.1, tau) == "FADE"    # boundary edge <= -tau
    assert signal_for(-0.2, tau) == "FADE"
    assert "SELL" not in {signal_for(e, tau) for e in (-1.0, -0.1, 0.0, 0.1, 1.0)}


def test_no_sell_ever_emitted(con):
    _seed_full(con)
    _run(con)
    assert all(g["signal"] != "SELL" for g in _sigs(con))
    assert {g["signal"] for g in _sigs(con)} <= {"BUY", "FADE", "HOLD"}


def test_yes_identified_by_outcome_label_not_index(con):
    # YES token stored at outcome_index = 1 (reversed); identity must use outcome_label.
    _seed_full(con, prices={mid: PW[mid] for mid in PW}, yes_index=1)
    s = _run(con)
    assert s["eligible"] is True
    preds = {p["market_id"]: p for p in _preds(con)}
    for (mid, _, _, _, y, _n) in BANDS:
        assert preds[mid]["token_id"] == y   # the outcome_label=="Yes" token (index 1)


# ------------------------------------------------------------- exclusion paths
def test_event_not_partition_excluded(con):
    _seed_forecast(con)
    # gap: 25 is missing between "24 or below" and "26 or higher"
    _seed_band(con, "g1", "24°C or below", None, 24.0, "gy1", "gn1", 0.3)
    _seed_band(con, "g2", "26°C or higher", 26.0, None, "gy2", "gn2", 0.3)
    s = _run(con)
    assert s["eligible"] is False
    assert s["reason"] == "event_not_partition"
    assert _preds(con) == [] and _sigs(con) == []
    excl = _excl(con)
    assert {e["market_id"] for e in excl} == {"g1", "g2"}
    assert all(e["stage"] == "feature" for e in excl)


def test_market_sum_out_of_tolerance_excluded(con):
    _seed_full(con, prices={mid: 0.5 for mid in PW})   # sum(p_market) = 2.0
    s = _run(con, market_sum_max=0.1)                  # 2.0 > 0.1 -> excluded
    assert s["eligible"] is False
    assert s["reason"] == "sum_pmarket_out_of_tolerance"
    assert _preds(con) == [] and _sigs(con) == []
    assert len(_excl(con)) == 4


def test_forecast_available_after_prediction_time_excluded(con):
    # forecast becomes available AFTER T -> build_feature returns None -> excluded.
    _seed_full(con, available_at="2026-08-19T18:00:00+00:00")
    s = _run(con)
    assert s["eligible"] is False
    assert s["reason"] == "missing_feature"
    assert _preds(con) == [] and _sigs(con) == []
    assert len(_excl(con)) == 4


def test_missing_yes_no_structure_excluded(con):
    _seed_forecast(con)
    # A band-market whose outcomes are not exactly one Yes + one No.
    _seed_band(con, "m1", "24°C or below", None, 24.0, "y1", "n1", 0.3)
    db.insert(con, "outcomes", {
        "market_id": "m1", "token_id": "y1b", "band_label": "24°C or below",
        "lo": None, "hi": 24.0, "outcome_index": 2, "outcome_label": "Yes",
        "source": "test", "ingestion_timestamp": ISSUE,
        "dataset_version": DSV, "record_version": 1,
    })  # now two "Yes" -> invalid structure
    s = _run(con)
    assert s["eligible"] is False
    assert s["reason"] == "invalid_yes_no_structure"
    assert _preds(con) == [] and _sigs(con) == []


# ----------------------------------------------------------- fail-closed params
def test_obligatory_params_fail_closed(con):
    _seed_full(con)
    base = dict(event_id=EVENT, prediction_time=T, model=MODEL, target_date=TARGET,
                dataset_version=DSV, tau=TAU, **TOL)
    for p in ("model", "target_date", "tau",
              "weather_sum_tolerance", "market_sum_min", "market_sum_max"):
        bad = dict(base)
        bad[p] = None
        with pytest.raises(ValueError):
            generate_event_signals(con, **bad)
    with pytest.raises(ValueError):
        generate_event_signals(con, **{**base, "tau": 0.0})    # tau must be > 0
    with pytest.raises(ValueError):
        generate_event_signals(con, **{**base, "tau": -0.1})


# --------------------------------------------------------------- no leakage etc
def test_no_resolution_fields_in_output_tables(con):
    # Resolution fields are never columns of the output tables (nor written).
    for t in ("predictions", "signals"):
        cols = set(db.column_names(con, t))
        assert FORBIDDEN_FEATURE_FIELDS.isdisjoint(cols), f"{t} exposes a resolution field"


def test_edge_net_and_net_edge_are_null(con):
    _seed_full(con)
    _run(con)
    assert all(p["edge_net"] is None for p in _preds(con))
    assert all(g["net_edge"] is None for g in _sigs(con))


def _normalize(rows):
    """Deterministic fingerprint: drop the volatile ingestion_timestamp; stringify."""
    out = []
    for r in rows:
        out.append(tuple(sorted(
            (k, str(v)) for k, v in r.items() if k != "ingestion_timestamp"
        )))
    return sorted(out)


def test_determinism_same_inputs_same_outputs(con):
    _seed_full(con)
    _run(con)
    fp1 = _normalize(_preds(con)) + _normalize(_sigs(con))

    c2 = database.init_db(database.connect(":memory:"))
    try:
        _seed_full(c2)
        _run(c2)
        fp2 = _normalize(_preds(c2)) + _normalize(_sigs(c2))
    finally:
        c2.close()
    assert fp1 == fp2


def test_rerun_is_idempotent(con):
    _seed_full(con)
    _run(con)
    _run(con)   # upsert on full PK -> no duplicates
    assert len(_preds(con)) == 4
    assert len(_sigs(con)) == 4


# ------------------------------------------------------- price-lineage guard
def test_yes_only_behaviour_preserved(con):
    # Only the YES token is priced -> unchanged behaviour: eligible, p_market == YES price.
    _seed_full(con)
    s = _run(con)
    assert s["eligible"] is True
    for p in _preds(con):
        assert p["p_market"] == pytest.approx(PRICES[p["market_id"]])


def test_both_tokens_priced_never_uses_no(con):
    # Both YES and NO priced (distinct). Either the event is eligible and EVERY p_market is
    # the YES price (never NO), or it is excluded for ambiguous_or_wrong_token_price.
    _seed_forecast(con)
    for (mid, label, lo, hi, y, n) in BANDS:
        _seed_band(con, mid, label, lo, hi, y, n, PRICES[mid],
                   no_price=round((PRICES[mid] + 0.3) % 1.0, 9))
    s = _run(con)
    if s["eligible"]:
        for p in _preds(con):
            assert p["p_market"] == pytest.approx(PRICES[p["market_id"]])   # YES, never NO
    else:
        assert s["reason"] == "ambiguous_or_wrong_token_price"
        assert _preds(con) == [] and _sigs(con) == []


def test_reversed_index_both_priced_never_uses_no(con):
    # YES at outcome_index=1, both priced -> YES identity by label; NO price never used.
    _seed_forecast(con)
    for (mid, label, lo, hi, y, n) in BANDS:
        _seed_band(con, mid, label, lo, hi, y, n, PW[mid],
                   yes_index=1, no_price=round((PW[mid] + 0.3) % 1.0, 9))
    s = _run(con)
    if s["eligible"]:
        preds = {p["market_id"]: p for p in _preds(con)}
        for (mid, _, _, _, yv, _n) in BANDS:
            assert preds[mid]["token_id"] == yv                     # YES token (index 1)
            assert preds[mid]["p_market"] == pytest.approx(PW[mid])  # YES price
    else:
        assert s["reason"] == "ambiguous_or_wrong_token_price"


def test_yes_price_missing_fail_closed(con):
    # No YES price anywhere (only NO priced) -> build_feature returns the NO price ->
    # guard finds no YES price -> fail-closed for the whole event.
    _seed_forecast(con)
    for (mid, label, lo, hi, y, n) in BANDS:
        _seed_band(con, mid, label, lo, hi, y, n, None, no_price=0.3)
    s = _run(con)
    assert s["eligible"] is False
    assert s["reason"] == "ambiguous_or_wrong_token_price"
    assert _preds(con) == [] and _sigs(con) == []
    assert len(_excl(con)) == 4


def test_single_price_belongs_to_no_fail_closed(con):
    # One band-market's ONLY price belongs to the NO token -> event excluded (whole-event).
    _seed_forecast(con)
    for i, (mid, label, lo, hi, y, n) in enumerate(BANDS):
        if i == 0:
            _seed_band(con, mid, label, lo, hi, y, n, None, no_price=0.3)  # only NO priced
        else:
            _seed_band(con, mid, label, lo, hi, y, n, PW[mid])
    s = _run(con)
    assert s["eligible"] is False
    assert s["reason"] == "ambiguous_or_wrong_token_price"
    assert _preds(con) == [] and _sigs(con) == []
