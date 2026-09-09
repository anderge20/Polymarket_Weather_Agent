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
                   group_item_title, lo, hi
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
                "condition_id": r.get("condition_id"),
                "event_id": str(r.get("event_id")) if r.get("event_id") else None,
                "slug": r.get("slug"),
                "question": r.get("question"),
                "city": r.get("city"),
                "station": r.get("station"),
                "station_identifier": r.get("station_identifier"),
                "resolution_source": r.get("resolution_source"),
                "unit": unit,
                "rounding_rule": r.get("rounding_rule"),
                "close_time": str(r["closedTime"]) if r.get("closedTime") else None,
                "winning_outcome": r.get("winning_outcome"),
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
        for idx, tok in enumerate(tokens):
            # Band applies to the YES token. The NO token is its complement and
            # carries no band of its own; writing the same lo/hi on it would make
            # band_probability answer the YES question for a NO position.
            db.upsert(
                con,
                "outcomes",
                {
                    "market_id": str(r["market_id"]),
                    "token_id": str(tok),
                    "band_label": r.get("group_item_title") if idx == 0 else None,
                    "lo": float(lo) if idx == 0 and lo is not None else None,
                    "hi": float(hi) if idx == 0 and hi is not None else None,
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
    u = db.query(con, "SELECT unit, count(*) n FROM markets GROUP BY 1 ORDER BY 2 DESC")
    print("  unidades:", {r["unit"]: r["n"] for r in u}, flush=True)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
