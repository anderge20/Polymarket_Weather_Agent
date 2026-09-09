#!/usr/bin/env python3
"""
backfill_markets.py — populate `markets` and `outcomes` from the catalogue
===========================================================================

`build_feature` needs the band (`outcomes.lo/hi`) and, since B-7, the market's
contractual unit (`markets.unit`). Both tables were empty, which is why the unit
defect went unnoticed for so long: the feature builder had never run on real data.

UNITS (B-7): `lo`/`hi` are written **exactly as the catalogue has them**, in the
contractual unit. They are NOT converted. The distribution is what moves to the
band's unit at feature time, because the contract's resolution grid is whole
degrees in its own unit and converting a 1 F band to Celsius would leave it
0.56 C wide, misaligned with the integer grid the distribution is indexed by.

EXCLUDED (preregistration §9): markets with `rounding_rule = 'tenths'` are written
but flagged, since an integer-keyed distribution cannot represent them. They are
counted, not silently dropped.

Usage:
    python3 scripts/backfill_markets.py --db data/pmw.duckdb
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import duckdb  # noqa: E402

from weather_agent import database as db  # noqa: E402

CATALOG = os.path.expanduser("~/pmw-catalog-v2/CATALOG_V2.duckdb")


def _s(v):
    """Catalogue text field -> str or None.

    `.to_dict("records")` on a pandas frame turns a missing text value into the
    FLOAT nan, and `str(nan)` is the four-character string "nan". Written into a
    VARCHAR that is exactly what the column holds: 422 markets carried the literal
    'nan' in `station_identifier`, which is not NULL, passes every IS NOT NULL
    check, and joins to nothing. A column that looks populated and is garbage —
    the same shape as `outcome_label` being NULL in 4 450/4 450, only louder,
    because here the substrate certifies presence rather than absence.
    """
    if v is None or v != v:
        return None
    t = str(v).strip()
    return None if t in ("", "nan", "None", "NaN", "<NA>") else t


def _fee_fields(raw) -> dict:
    """D19: the fee parameters are per market, read from `feeSchedule`, and are
    NEVER inferred from a date — activation was by batch, so the 30-mar cohort is
    mixed (275 with / 143 without). An unparseable schedule leaves the columns
    NULL, and `costs.taker_fee` fails closed on NULL rather than assuming 0.05.
    """
    out = {"fee_rate": None, "fee_exponent": None, "fee_taker_only": None}
    if raw is None or raw != raw:
        return out
    try:
        sched = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return out
    if isinstance(sched, list):
        sched = sched[0] if sched else None
    if not isinstance(sched, dict):
        return out
    for key, col in (("rate", "fee_rate"), ("exponent", "fee_exponent")):
        v = sched.get(key)
        if v is not None and v == v:
            out[col] = float(v)
    to = sched.get("takerOnly")
    if to is None:
        to = sched.get("taker_only")
    if to is not None:
        out["fee_taker_only"] = bool(to)
    return out
DATASET_VERSION = "backfill_2b_v1"
UNSUPPORTED_ROUNDING = "tenths"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--catalog", default=CATALOG)
    args = ap.parse_args()

    con = db.init_db(db.connect(args.db))
    priced = {
        r["market_id"]
        for r in db.query(con, "SELECT DISTINCT market_id FROM price_history")
    }
    print(f"mercados con precios: {len(priced)}", flush=True)
    if not priced:
        return 1

    cat = duckdb.connect(args.catalog, read_only=True)
    ids = ",".join(f"'{m}'" for m in priced)
    rows = cat.execute(
        f"""SELECT market_id, condition_id, event_id, slug, question, city,
                   station, station_identifier, resolution_source, unit,
                   rounding_rule, endDate, closedTime, winning_outcome,
                   clobTokenIds, outcomes, tick_size, min_order_size,
                   group_item_title, lo, hi, umaResolutionStatus,
                   feesEnabled, feeSchedule
            FROM mk WHERE market_id IN ({ids})"""
    ).fetchdf().to_dict("records")
    cat.close()
    print(f"filas del catálogo: {len(rows)}", flush=True)

    n_mk = n_out = skipped_unit = tenths = 0
    for r in rows:
        unit = (r.get("unit") or "").strip().upper()
        if unit not in ("C", "F"):
            # Without a unit the band cannot be compared to anything (B-6/B-7).
            # Skip and count rather than write a market that will raise later.
            skipped_unit += 1
            continue
        rounding = (r.get("rounding_rule") or "").strip().lower()
        if rounding == UNSUPPORTED_ROUNDING:
            tenths += 1

        db.upsert(
            con,
            "markets",
            {
                "market_id": str(r["market_id"]),
                "condition_id": _s(r.get("condition_id")),
                "event_id": str(r.get("event_id")) if r.get("event_id") else None,
                "slug": _s(r.get("slug")),
                "question": _s(r.get("question")),
                "city": _s(r.get("city")),
                # `station` is the airport NAME, `station_identifier` the ICAO.
                # Everything downstream joins on the ICAO; the name is metadata.
                "station": _s(r.get("station")),
                "station_identifier": _s(r.get("station_identifier")),
                "resolution_source": _s(r.get("resolution_source")),
                "unit": unit,
                "rounding_rule": _s(r.get("rounding_rule")),
                "close_time": _s(r.get("closedTime")),
                # R8: endDate is the contract's declared end, target_date 12:00Z.
                # It drives the R19 universe FILTER. `closedTime` is when the
                # market actually stopped trading and is a different fact.
                "end_date": _s(r.get("endDate")),
                "uma_resolution_status": _s(r.get("umaResolutionStatus")),
                "fees_enabled": (None if r.get("feesEnabled") is None
                                 or r.get("feesEnabled") != r.get("feesEnabled")
                                 else bool(r["feesEnabled"])),
                **_fee_fields(r.get("feeSchedule")),
                "winning_outcome": _s(r.get("winning_outcome")),
                "tick_size": float(r["tick_size"]) if r.get("tick_size") == r.get("tick_size") and r.get("tick_size") is not None else None,
                "min_order_size": float(r["min_order_size"]) if r.get("min_order_size") == r.get("min_order_size") and r.get("min_order_size") is not None else None,
                "source": "CATALOG_V2",
                "dataset_version": DATASET_VERSION,
                "record_version": 1,
            },
            conflict_cols=("market_id", "dataset_version", "record_version"),
        )
        n_mk += 1

        try:
            tokens = json.loads(r["clobTokenIds"])
            labels = json.loads(r["outcomes"]) if r.get("outcomes") else ["Yes", "No"]
        except Exception:
            continue
        lo, hi = r.get("lo"), r.get("hi")
        lo = None if lo != lo else lo   # NaN -> None (open-ended low)
        hi = None if hi != hi else hi
        # `labels` was parsed and then thrown away: the INSERT carried
        # outcome_index and no outcome_label. Everything downstream identifies the
        # YES token by outcome_label == "Yes" (2D, strategy_a.py:9 — NEVER by
        # index), so a NULL column meant NO token was ever Yes and Strategy A
        # produced zero signals over the entire substrate, deterministically and
        # without an error.
        for idx, tok in enumerate(tokens):
            label = labels[idx] if idx < len(labels) else None
            is_yes = (str(label).strip().lower() == "yes")
            # Band applies to the YES token. The NO token is its complement and
            # carries no band of its own; writing the same lo/hi on it would make
            # band_probability answer the YES question for a NO position.
            db.upsert(
                con,
                "outcomes",
                {
                    "market_id": str(r["market_id"]),
                    "token_id": str(tok),
                    "outcome_label": label,
                    # The band belongs to the YES token, identified by its LABEL.
                    # The NO token is the complement and carries no band of its
                    # own; giving it the same lo/hi would make band_probability
                    # answer the YES question for a NO position.
                    "band_label": _s(r.get("group_item_title")) if is_yes else None,
                    "lo": float(lo) if is_yes and lo is not None else None,
                    "hi": float(hi) if is_yes and hi is not None else None,
                    "outcome_index": idx,
                    "is_winner": None,   # a LABEL: never written from here
                    "source": "CATALOG_V2",
                    "dataset_version": DATASET_VERSION,
                    "record_version": 1,
                },
                conflict_cols=("token_id", "dataset_version", "record_version"),
            )
            n_out += 1

    print(
        f"LISTO markets={n_mk} outcomes={n_out} sin_unidad_saltados={skipped_unit} "
        f"redondeo_decimas={tenths}",
        flush=True,
    )
    for label, sql in (
        ("ICAO", "SELECT count(*) n FROM markets WHERE station_identifier IS NOT NULL"),
        ("cadena 'nan'", "SELECT count(*) n FROM markets WHERE station_identifier = 'nan'"),
        ("end_date", "SELECT count(*) n FROM markets WHERE end_date IS NOT NULL"),
        ("resueltos", "SELECT count(*) n FROM markets WHERE uma_resolution_status = 'resolved'"),
        ("con fee", "SELECT count(*) n FROM markets WHERE fees_enabled"),
        ("fee_rate nulo y fees on",
         "SELECT count(*) n FROM markets WHERE fees_enabled AND fee_rate IS NULL"),
    ):
        print(f"  {label:22s} {db.query(con, sql)[0]['n']}", flush=True)
    u = db.query(con, "SELECT unit, count(*) n FROM markets GROUP BY 1 ORDER BY 2 DESC")
    print("  unidades:", {r["unit"]: r["n"] for r in u}, flush=True)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
