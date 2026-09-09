#!/usr/bin/env python3
"""
replay_cycle.py — rebuild a paper cycle from shards and re-evaluate its decisions.
==================================================================================
This is the instrument R24's criterion C3 ("reproducibility: 100 % of the
operations") invokes. C3 without it would be a criterion that names a tool nobody
wrote — which is precisely the class of defect the hostile refutations keep
finding, so it exists before the criterion is frozen rather than after.

WHAT REPRODUCIBILITY MEANS HERE, EXACTLY
----------------------------------------
Re-running `paper_cycle.py` would NOT reproduce anything: it would re-query gamma
and the CLOB and get a different, later market. A cycle is reproducible in the
only sense that matters for an audit — given the data that was persisted and the
parameters that were recorded, the same decisions come out.

So the replay:
  * rebuilds a DuckDB from the shard store (the shards are the source of truth),
  * reads the `cycle_params` shard the cycle wrote, and takes `prediction_time`,
    `tau`, the sizing parameters and the model FROM IT — never from the clock and
    never from today's defaults,
  * re-derives the EXECUTION layer over that state — admissible book, fill price,
    size, fee — and diffs it against the `paper_trades` persisted at the time.

WHAT IT DOES NOT AUDIT, stated so the criterion cannot overclaim: it does NOT
recompute the signal. `signal` and `fair_value` are read from the persisted
`signals` rows and taken as given, so an irreproducible SIGNAL would not be
caught here. Re-deriving `p_weather` means re-deriving M2's quantiles, which is
another session's lane. R24's C3 is written against this boundary rather than
against the broader claim.

Any disagreement is reported per row. A silent "looks fine" is not an outcome:
the exit code is non-zero when anything differs, so this can gate a run.

KNOWN SOURCES OF NON-DETERMINISM, and what is done about each
-------------------------------------------------------------
  * `_utcnow()` in `prediction_time` -> pinned from `cycle_params`.
  * `ingestion_timestamp` on every row -> excluded from every comparison; it
    records when a row was written, not what was decided.
  * dict/set iteration order -> the cycle sorts its universe and its signals, so
    ordering is already fixed upstream.
  * the live book -> never re-fetched; the replay reads the stored snapshot.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from weather_agent import database as db, paper, store  # noqa: E402

#: Fields compared for a signal. `ingestion_timestamp` is deliberately absent.
SIGNAL_FIELDS = ("market_id", "token_id", "strategy", "signal", "fair_value",
                 "price_assumption", "edge")
#: Fields compared for a paper trade. Floats are compared with a tolerance.
TRADE_FIELDS = ("market_id", "token_id", "entry_price", "size", "fees",
                "price_layer")

TOL = 1e-9


def load_params(root: str, session_id: str) -> dict | None:
    """Read the parameters the cycle recorded for itself."""
    for path in store.iter_shards(root, "cycle_params"):
        for row in store.read_shard(path):
            if row.get("session_id") == session_id:
                return row
    return None


def rebuild(root: str, tables=None):
    """Reconstruct a DuckDB from the shard store."""
    con = db.init_db(db.connect(":memory:"))
    loaded = {}
    for table in (tables or store.CONFLICT_COLS):
        if table == "cycle_params":
            continue
        try:
            out = store.load_shards(con, table=table, root=root)
        except ValueError:
            continue
        if out["rows_written"]:
            loaded[table] = out["rows_written"]
    return con, loaded


def _close(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= TOL
    return a == b


def compare(persisted: list[dict], recomputed: list[dict], fields, key) -> dict:
    """Diff two decision sets by natural key. Returns counts and the first
    disagreements, never a bare boolean — an audit needs to see what differed."""
    pa = {key(r): r for r in persisted}
    re_ = {key(r): r for r in recomputed}
    only_persisted = sorted(set(pa) - set(re_))
    only_recomputed = sorted(set(re_) - set(pa))
    mismatches = []
    for k in sorted(set(pa) & set(re_)):
        diffs = {f: (pa[k].get(f), re_[k].get(f))
                 for f in fields if not _close(pa[k].get(f), re_[k].get(f))}
        if diffs:
            mismatches.append({"key": k, "diffs": diffs})
    return {
        "persisted": len(pa), "recomputed": len(re_),
        "matched": len(set(pa) & set(re_)) - len(mismatches),
        "mismatched": len(mismatches),
        "only_persisted": only_persisted[:20],
        "only_recomputed": only_recomputed[:20],
        "examples": mismatches[:10],
    }


def replay(root: str, session_id: str) -> dict:
    params = load_params(root, session_id)
    if params is None:
        return {"ok": False, "error": f"no cycle_params recorded for {session_id!r}",
                "hint": "a cycle written before stage_params existed cannot be replayed"}

    con, loaded = rebuild(root)
    dsv = params["dataset_version"]
    prediction_time = params["prediction_time"]

    result = {"session_id": session_id, "params": params, "tables_loaded": loaded}

    persisted_signals = db.query(
        con,
        "SELECT market_id, token_id, strategy, signal, fair_value, price_assumption, "
        "edge FROM signals WHERE dataset_version = ? AND \"timestamp\" = ?",
        [dsv, prediction_time],
    )
    persisted_trades = db.query(
        con,
        "SELECT market_id, token_id, entry_price, size, fees, price_layer "
        "FROM paper_trades WHERE dataset_version = ? AND entry_time = ?",
        [dsv, prediction_time],
    )

    # Re-derive the fills from the persisted signals and the stored books, using
    # the RECORDED parameters. This is the part C3 actually checks: that the same
    # book and the same parameters produce the same price and the same size.
    if params.get("tau") is None:
        result["trades"] = {"skipped": "cycle ran without tau (collect-only)"}
        result["signals"] = {"persisted": len(persisted_signals)}
        result["ok"] = not persisted_trades
        con.close()
        return result

    pp = paper.PaperParams(
        bankroll=float(params["bankroll"]),
        fixed_fraction=float(params["fixed_fraction"]),
        size_cap=float(params["size_cap"]),
        tau=float(params["tau"]),
        exit_mode=params["exit_mode"],
        x_exec=float(params["x_exec"]),
    )

    recomputed: list[dict] = []
    bankroll = pp.bankroll
    for sig in sorted(persisted_signals, key=lambda r: (r["market_id"], r["token_id"])):
        if sig["signal"] not in ("BUY", "FADE"):
            continue
        exec_token = str(sig["token_id"])
        if sig["signal"] == "FADE":
            comp = db.query(
                con,
                "SELECT token_id FROM outcomes WHERE market_id = ? "
                "AND dataset_version = ? AND token_id <> ? LIMIT 1",
                [sig["market_id"], dsv, exec_token],
            )
            if not comp:
                continue
            exec_token = str(comp[0]["token_id"])
        # The SAME selector the cycle used. When these differed, the replay could
        # report NOT REPRODUCIBLE for a perfectly correct cycle.
        snap = paper.select_book(con, token_id=exec_token, dataset_version=dsv,
                                 asof=prediction_time)
        if snap is None:
            continue
        fee_rows = db.query(
            con,
            "SELECT f.fee_regime, f.taker_fee, f.fee_status, f.raw_fee_fields "
            "FROM markets m JOIN market_fee_schedule f "
            "  ON f.fee_regime = m.fee_regime AND f.dataset_version = m.dataset_version "
            "WHERE m.market_id = ? AND m.dataset_version = ? LIMIT 1",
            [sig["market_id"], dsv],
        )
        fee_row = dict(fee_rows[0]) if fee_rows else {}
        if isinstance(fee_row.get("raw_fee_fields"), str):
            try:
                fee_row["raw_fee_fields"] = json.loads(fee_row["raw_fee_fields"])
            except ValueError:
                fee_row["raw_fee_fields"] = {}
        decision = paper.decide_and_fill(
            signal=sig["signal"], p_model=float(sig["fair_value"]),
            book_snapshot=snap, fee=paper.resolve_fee_params(fee_row),
            params=pp, bankroll=bankroll,
        )
        if not decision["open"]:
            continue
        fill = decision["fill"]
        bankroll -= fill.outlay
        recomputed.append({
            "market_id": sig["market_id"], "token_id": exec_token,
            "entry_price": fill.vwap, "size": fill.shares, "fees": fill.fee,
            "price_layer": paper.PRICE_LAYER,
        })

    result["trades"] = compare(
        persisted_trades, recomputed, TRADE_FIELDS,
        key=lambda r: (r["market_id"], r["token_id"]),
    )
    result["signals"] = {"persisted": len(persisted_signals)}
    result["ok"] = (result["trades"]["mismatched"] == 0
                    and not result["trades"]["only_persisted"]
                    and not result["trades"]["only_recomputed"])
    con.close()
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay a paper cycle from shards.")
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--store-root", default=store.DEFAULT_ROOT)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    out = replay(args.store_root, args.session_id)
    if args.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print(f"replay session={args.session_id}")
        if not out.get("ok") and "error" in out:
            print(f"  ERROR: {out['error']}")
            return 2
        tr = out.get("trades", {})
        if "skipped" in tr:
            print(f"  trades: {tr['skipped']}")
        else:
            print(f"  trades persisted={tr.get('persisted')} "
                  f"recomputed={tr.get('recomputed')} "
                  f"matched={tr.get('matched')} mismatched={tr.get('mismatched')}")
            for ex in tr.get("examples", []):
                print(f"    MISMATCH {ex['key']}: {ex['diffs']}")
            for k in tr.get("only_persisted", []):
                print(f"    ONLY PERSISTED: {k}")
            for k in tr.get("only_recomputed", []):
                print(f"    ONLY RECOMPUTED: {k}")
        print(f"  VERDICT: {'REPRODUCIBLE' if out.get('ok') else 'NOT REPRODUCIBLE'}")
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
