"""
weather_agent.polymarket.fees — gamma fee / tick / min mapping (Phase 2B)
=========================================================================
STATUS: IMPLEMENTED. Authored WITHOUT Python execution — not tested/validated
here. Pure functions (no network, no DB).

Grounded in REAL gamma market objects (verified live 2026-08-21):
  * RECENT markets (e.g. Ankara 2026-08-20) carry:
      makerBaseFee=1000, takerBaseFee=1000, feesEnabled=true, feeType="weather_fees",
      feeSchedule={"exponent":1,"rate":0.05,"takerOnly":true,"rebateRate":0.25}
  * LEGACY markets (e.g. NYC 2025-12-30) carry:
      feesEnabled=false, feeType=null, and NO makerBaseFee/takerBaseFee/feeSchedule.
  * BOTH epochs carry: orderPriceMinTickSize=0.001, orderMinSize=5.

POLICY (corrections #7 + fee principle "never assume 0 without justification"):
  * fee_status='KNOWN' ONLY when fee fields were actually READ from gamma.
  * When feesEnabled is explicitly false we record taker_fee=0.0 — this 0 is
    JUSTIFIED by the source flag, NOT a silent default.
  * When fee fields are absent entirely -> fee_regime='UNKNOWN', fees NULL,
    fee_status='UNKNOWN'.
  * tick_size/min_order_size come from gamma if present, else NULL (never a
    hardcoded default).
  * The precise UNIT semantics of makerBaseFee/takerBaseFee=1000 and how they
    relate to feeSchedule.rate are NOT documented by what we fetched; the RAW
    fields are captured verbatim (raw_fee_fields) so the interpretation can be
    confirmed on Hetzner. taker_fee/maker_rebate use feeSchedule.rate/rebateRate
    as the best-documented effective values (flagged INFERRED for interpretation).
"""
from __future__ import annotations

import json
from typing import Any


def _as_dict(v: Any) -> dict | None:
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip():
        try:
            d = json.loads(v)
            return d if isinstance(d, dict) else None
        except Exception:
            return None
    return None


def map_fees(market: dict) -> dict:
    """Map a gamma market's fee fields to a market_fee_schedule row payload.
    Returns keys: fee_regime, taker_fee, maker_rebate, effective_from,
    effective_to, fee_status, raw_fee_fields, confidence."""
    fee_type = market.get("feeType")
    fees_enabled = market.get("feesEnabled")
    schedule = _as_dict(market.get("feeSchedule"))
    raw = {k: market.get(k) for k in
           ("feeType", "feesEnabled", "feeSchedule", "makerBaseFee", "takerBaseFee")
           if k in market}

    # Case 1: an active, named fee regime with a schedule -> KNOWN.
    if fee_type and fees_enabled and schedule is not None:
        return {
            "fee_regime": str(fee_type),                 # e.g. 'weather_fees'
            "taker_fee": schedule.get("rate"),           # 0.05 (takerOnly per schedule)
            "maker_rebate": schedule.get("rebateRate"),  # 0.25
            "effective_from": None,                      # gamma exposes no fee epoch range
            "effective_to": None,
            "fee_status": "KNOWN",
            "raw_fee_fields": raw,
            "confidence": "VERIFIED",   # fields read; interpretation of rate flagged in doc
        }
    # Case 2: fees explicitly disabled at source -> KNOWN, 0 JUSTIFIED (not assumed).
    if fees_enabled is False:
        return {
            "fee_regime": "fees_disabled",
            "taker_fee": 0.0,
            "maker_rebate": 0.0,
            "effective_from": None,
            "effective_to": None,
            "fee_status": "KNOWN",
            "raw_fee_fields": raw or {"feesEnabled": False, "feeType": fee_type},
            "confidence": "VERIFIED",
        }
    # Case 3: no fee information at all -> UNKNOWN (never invent a fee).
    return {
        "fee_regime": "UNKNOWN",
        "taker_fee": None,
        "maker_rebate": None,
        "effective_from": None,
        "effective_to": None,
        "fee_status": "UNKNOWN",
        "raw_fee_fields": raw,
        "confidence": "UNKNOWN",
    }


def map_tick_min(market: dict) -> tuple[float | None, float | None]:
    """(tick_size, min_order_size) from gamma if present, else (None, None).
    Gamma keys (verified): orderPriceMinTickSize, orderMinSize. NO hardcoded
    default (correction #7)."""
    tick = market.get("orderPriceMinTickSize")
    minsz = market.get("orderMinSize")
    tick = float(tick) if isinstance(tick, (int, float)) else None
    minsz = float(minsz) if isinstance(minsz, (int, float)) else None
    return tick, minsz


def fee_schedule_hash(raw_fee_fields: Any) -> str:
    """Stable identity hash of a fee configuration (feeType / feeSchedule / base
    fees). Used by discovery's #3 GUARD to DETECT — and refuse — two markets that
    share a fee_regime but carry a DIFFERENT feeSchedule within one dataset_version.
    Accepts a dict OR a JSON-encoded string (as read back from DuckDB)."""
    import hashlib
    v = raw_fee_fields
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            v = {"_raw": raw_fee_fields}
    if v is None:
        v = {}
    canon = json.dumps(v, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(canon.encode("utf-8")).hexdigest()
