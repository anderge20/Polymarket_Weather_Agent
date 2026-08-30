"""
weather_agent.strategy.strategy_a — Strategy A V1 (weather-vs-market signal generator).

Authoritative design: PHASE_2D_STRATEGY_A_DESIGN.md (baseline 8162b9c / 5816095).
This module ONLY generates signals; it does NOT size, execute, compute net/fees, or
backtest. Nothing here reopens or modifies any 2A/2B/2C LOCKED decision.

V1 contracts (all taken from the versioned design; none invented here):
  * YES token  <=>  outcomes.outcome_label == "Yes"   (NEVER outcome_index, NEVER is_winner).
  * Inputs come from features.build_feature() — its as-of / no-look-ahead guards (2C)
    are reused verbatim; resolution is NEVER read at prediction_time.
  * target_date, model, tau, weather_sum_tolerance, market_sum_min, market_sum_max are
    OBLIGATORY caller parameters with NO defaults; a missing/invalid one -> fail-closed.
  * p_model = p_weather ; fair_value = p_model ; edge = fair_value - p_market.
  * Eligible band signal:  BUY if edge >= +tau ; FADE if edge <= -tau ; HOLD if |edge| < tau.
    NONE is reserved for ineligibility and is NOT emitted in V1 (option A). Ineligible
    events are recorded in markets_excluded only.
  * Event-level: an event = all band-markets sharing event_id; eligibility is per EVENT.
    The event is EXCLUDED (fail-closed -> markets_excluded, stage="feature"; NO predictions,
    NO signals) when ANY of:
      - a band-market does not have exactly one valid "Yes" + one "No" outcome;
      - build_feature returns None, or rejects the price (EXECUTABLE / invalid), for any band;
      - the YES token's price (re-queried directly) is missing or does not exactly match the
        market_prob returned by build_feature (price-lineage guard; no fallback to the No token);
      - the band labels are not a valid partition (resolution.band_integrity.is_partition);
      - |sum(p_weather) - 1| > weather_sum_tolerance;
      - sum(p_market) is outside [market_sum_min, market_sum_max].
    Whole-event exclusion (rather than partial per-band signals) is forced by the LOCKED
    constraints: build_feature returns None when a band's price is missing and probabilities
    are NEVER recomputed outside build_feature, so an event-level sum can only be taken over
    a COMPLETE band set — a partial sum would be a silent normalization, which the design
    forbids (W.6).
  * edge_net / net_edge = NULL ; confidence = NULL ; timestamp = prediction_time.
  * Deterministic: identical inputs -> identical rows (ingestion_timestamp aside).

STATUS: IMPLEMENTED (authored without Python execution). TESTED/VALIDATED are USER-RUN.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .. import database as db
from ..features import build_feature
from ..polymarket import resolution as res

MODEL_VERSION = "stratA_pmodel_v1"   # predictions.model_version (p_model = p_weather)
STRATEGY = "strategy_a_v1"           # signals.strategy
SOURCE = "strategy_a_v1"             # provenance source
STAGE = "feature"                    # markets_excluded.stage (documented 2A value)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _latest_by(rows: list[dict], key: str) -> list[dict]:
    """Current view: keep, per natural `key`, the row with the highest record_version."""
    best: dict[Any, dict] = {}
    for r in rows:
        k = r[key]
        rv = r.get("record_version") or 0
        if k not in best or rv > (best[k].get("record_version") or 0):
            best[k] = r
    return list(best.values())


def _require(name: str, value: Any) -> Any:
    """Fail-closed: an obligatory parameter must not be None (no invented default)."""
    if value is None:
        raise ValueError(
            f"strategy_a: obligatory parameter {name!r} is missing (no default; fail-closed)"
        )
    return value


def signal_for(edge: float, tau: float) -> str:
    """Map an edge to a V1 signal (option A): BUY / FADE / HOLD. NONE is not emitted."""
    if edge >= tau:
        return "BUY"
    if edge <= -tau:
        return "FADE"
    return "HOLD"


def generate_event_signals(
    con,
    *,
    event_id: str,
    prediction_time: Any,
    model: str,
    target_date: Any,
    dataset_version: str,
    tau: float,
    weather_sum_tolerance: float,
    market_sum_min: float,
    market_sum_max: float,
) -> dict:
    """Generate Strategy A V1 signals for ONE event, as-of prediction_time.

    ELIGIBLE event  -> writes predictions + signals (BUY/FADE/HOLD) per band.
    INELIGIBLE event -> writes markets_excluded (per band-market, stage='feature'),
                        and NO predictions / NO signals (fail-closed).
    All parameters are obligatory (no defaults); a missing/invalid one raises.
    Returns a summary dict (deterministic, no volatile timestamps).
    """
    # ---- fail-closed parameter validation (NO invented defaults) --------------
    _require("event_id", event_id)
    _require("prediction_time", prediction_time)
    _require("model", model)
    _require("target_date", target_date)
    _require("dataset_version", dataset_version)
    _require("tau", tau)
    _require("weather_sum_tolerance", weather_sum_tolerance)
    _require("market_sum_min", market_sum_min)
    _require("market_sum_max", market_sum_max)
    if not tau > 0:
        raise ValueError("strategy_a: tau must be > 0 (design W.4/W.12)")
    if weather_sum_tolerance < 0:
        raise ValueError("strategy_a: weather_sum_tolerance must be >= 0")
    if market_sum_min > market_sum_max:
        raise ValueError("strategy_a: market_sum_min must be <= market_sum_max")

    # Normalize the as-of cutoff exactly as features.build_feature does, so the price-lineage
    # guard below queries price_history with the SAME temporal convention.
    pt = prediction_time
    if isinstance(pt, str):
        pt = datetime.fromisoformat(pt.replace("Z", "+00:00"))

    now = _utcnow()
    summary = {
        "event_id": event_id, "dataset_version": dataset_version,
        "prediction_time": str(prediction_time),
        "eligible": None, "reason": None,
        "predictions_written": 0, "signals_written": 0, "excluded_written": 0,
    }

    # ---- 1. band-markets of the event (current record_version per market) -----
    markets = _latest_by(
        db.query(
            con,
            "SELECT market_id, event_id, station, unit, record_version "
            "FROM markets WHERE event_id = ? AND dataset_version = ?",
            [event_id, dataset_version],
        ),
        "market_id",
    )
    summary["n_markets"] = len(markets)
    if not markets:
        summary["eligible"] = False
        summary["reason"] = "no_markets_for_event"
        return summary

    unit = markets[0].get("unit")
    markets = sorted(markets, key=lambda r: str(r["market_id"]))  # deterministic order

    # ---- 2/3. per band-market: identify YES token, then build_feature ---------
    bands: list[dict] = []
    reason: str | None = None
    for m in markets:
        market_id = m["market_id"]
        outs = _latest_by(
            db.query(
                con,
                "SELECT token_id, band_label, outcome_label, record_version "
                "FROM outcomes WHERE market_id = ? AND dataset_version = ?",
                [market_id, dataset_version],
            ),
            "token_id",
        )
        yes = [o for o in outs if o.get("outcome_label") == "Yes"]
        no = [o for o in outs if o.get("outcome_label") == "No"]
        if len(yes) != 1 or len(no) != 1:
            reason = reason or "invalid_yes_no_structure"
            continue
        token_id = yes[0]["token_id"]
        band_label = yes[0].get("band_label")
        try:
            feat = build_feature(
                con,
                prediction_time=prediction_time,
                market_id=market_id,
                token_id=token_id,
                station=m.get("station"),
                model=model,
                target_date=target_date,
                dataset_version=dataset_version,
            )
        except ValueError:
            # build_feature rejects EXECUTABLE / invalid price (contract E/L) -> exclude.
            # NOTE: AssertionError (its no-look-ahead guard) is intentionally NOT caught —
            # a guard failure signals a real leakage/data bug and must propagate (fail loud).
            reason = reason or "executable_or_invalid_price"
            continue
        if feat is None:
            reason = reason or "missing_feature"
            continue
        p_market = feat.get("market_prob")
        p_weather = feat.get("weather_prob")
        if p_market is None or p_weather is None or band_label is None:
            reason = reason or "missing_feature"
            continue
        # PRICE-LINEAGE GUARD: build_feature selects the price by market_id only and takes
        # prices[0], which is NOT guaranteed to be this YES token. Re-query the YES token's
        # price directly, reusing build_feature's own conventions (observation_time as-of pt,
        # partition by token_id, NO dataset_version filter — matching features.py), and require
        # an EXACT match. Missing YES price / mismatch -> fail-closed (no fallback, no arbitrary
        # pick, no tolerance).
        yes_rows = db.latest_asof(
            con, "price_history", time_col="observation_time", asof=pt,
            partition_cols=["token_id"],
            where="market_id = ? AND token_id = ?", params=[market_id, token_id],
        )
        yes_price = yes_rows[0].get("indicative_price") if yes_rows else None
        if yes_price is None or yes_price != p_market:
            reason = reason or "ambiguous_or_wrong_token_price"
            continue
        bands.append({
            "market_id": market_id, "token_id": token_id, "band_label": band_label,
            "p_market": float(p_market), "p_weather": float(p_weather),
        })

    event_ok = reason is None and len(bands) == len(markets)

    # ---- 4. event-level coherence gates (only if every band produced features) -
    if event_ok:
        labels = [b["band_label"] for b in bands]
        integ = res.band_integrity(labels, unit)
        sum_pw = sum(b["p_weather"] for b in bands)
        sum_pm = sum(b["p_market"] for b in bands)
        if not integ.get("is_partition"):
            reason, event_ok = "event_not_partition", False
        elif abs(sum_pw - 1.0) > weather_sum_tolerance:
            reason, event_ok = "sum_pweather_out_of_tolerance", False
        elif not (market_sum_min <= sum_pm <= market_sum_max):
            reason, event_ok = "sum_pmarket_out_of_tolerance", False

    # ---- 5/6. write outputs ---------------------------------------------------
    if event_ok:
        for b in bands:
            p_market, p_weather = b["p_market"], b["p_weather"]
            p_model = p_weather              # W.1
            fair_value = p_model             # W.2
            edge = fair_value - p_market     # W.3
            signal = signal_for(edge, tau)   # W.4 (option A): BUY / FADE / HOLD
            db.upsert(con, "predictions", {
                "timestamp": prediction_time,
                "market_id": b["market_id"], "token_id": b["token_id"],
                "p_market": p_market, "p_weather": p_weather,
                "p_model": p_model, "fair_value": fair_value,
                "edge_gross": edge, "edge_net": None,   # net BLOCKED (fees)
                "confidence": None,                     # NULL in V1
                "model_version": MODEL_VERSION,
                "source": SOURCE, "source_timestamp": prediction_time,
                "ingestion_timestamp": now,
                "dataset_version": dataset_version, "record_version": 1,
            }, ["market_id", "token_id", "model_version", "timestamp",
                "dataset_version", "record_version"])
            summary["predictions_written"] += 1
            db.upsert(con, "signals", {
                "timestamp": prediction_time,
                "market_id": b["market_id"], "token_id": b["token_id"],
                "strategy": STRATEGY, "signal": signal,
                "fair_value": fair_value, "price_assumption": p_market,
                "edge": edge, "net_edge": None,         # net BLOCKED (fees)
                "confidence": None,                     # NULL in V1
                "reason": f"p_model=p_weather;edge={edge!r};tau={tau!r};signal={signal}",
                "source": SOURCE, "source_timestamp": prediction_time,
                "ingestion_timestamp": now,
                "dataset_version": dataset_version, "record_version": 1,
            }, ["market_id", "token_id", "strategy", "timestamp",
                "dataset_version", "record_version"])
            summary["signals_written"] += 1
        summary["eligible"], summary["reason"] = True, None
    else:
        details = {
            "event_id": event_id, "reason": reason,
            "n_markets": len(markets), "n_bands_ok": len(bands),
            "prediction_time": str(prediction_time),
        }
        for m in markets:
            db.upsert(con, "markets_excluded", {
                "market_id": m["market_id"], "reason": reason,
                "excluded_at": prediction_time, "stage": STAGE, "details": details,
                "source": SOURCE, "ingestion_timestamp": now,
                "dataset_version": dataset_version, "record_version": 1,
            }, ["market_id", "reason", "dataset_version"])
            summary["excluded_written"] += 1
        summary["eligible"], summary["reason"] = False, reason
    return summary
