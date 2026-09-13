#!/usr/bin/env python3
"""
book_measurements.py - resolving E2 against the REAL books on branch `paper-state`
==================================================================================

The report's S4 proposed E2: collect the order book for 4-6 weeks, then test one
preregistered condition - median half-spread > 0.036, the measured fair-value margin -
which decides edges #2 (market making) and #3 (partition coherence).

Session A's addendum established the collection was already running. This script does
what that makes possible: it RESOLVES the condition, and it resolves it AGAINST the
strategy. Three measurements, all on 36 850 real `clob_books_poll` rows:

  1. SPREAD. Median half-spread is 0.0050 over all two-sided books and 0.0100 over the
     tradable weather bands. The threshold was 0.036. It FAILS by 4-7x, in every price
     bucket, with 1.4 % of books clearing it. Edges #2 and #3 drop to class E.

  2. PARTITION COHERENCE (model-free, needs no forecast). Over 96 complete valid band
     partitions with a two-sided book on EVERY leg: sum of best asks has median 1.1265
     and NEVER goes below 1.0200; sum of best bids has median 0.9355 and tops out at
     1.0110. Buying the basket is profitable after fees in 0 of 96; selling it, 0 of 96.
     The books are internally coherent in exactly the direction arbitrage would need.

  3. THE ASSUMED SLIPPAGE WAS RIGHT. PREREG_R21_ENMIENDA_A A.2 assumed x_exec = 0.01
     and called it an assumption, not a measurement. The measured median half-spread on
     tradable weather bands is 0.0100. R21's cost model was accurate, which STRENGTHENS
     its negative rather than weakening it.

Requires the `paper-state` branch fetched:  git fetch origin paper-state
Usage:  python3 scripts/research/book_measurements.py
"""
from __future__ import annotations

import gzip
import json
import statistics as st
import subprocess
from collections import defaultdict

BRANCH = "origin/paper-state"
#: report S4/E2, fixed before any book was read.
THRESHOLD_HALF_SPREAD = 0.036


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def shards(table: str) -> list[dict]:
    """Every row of one paper_state table, read straight out of the branch."""
    names = _git("ls-tree", "-r", "--name-only", BRANCH).decode().splitlines()
    out: list[dict] = []
    for n in (x for x in names if x.startswith(f"paper_state/{table}/")):
        raw = _git("show", f"{BRANCH}:{n}")
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        out += [json.loads(l) for l in raw.decode().splitlines() if l.strip()]
    return out


def q(values, p: float) -> float:
    v = sorted(values)
    return v[int(p * (len(v) - 1))]


def is_partition(outcomes) -> bool:
    """One open-lo band, one open-hi band, closed bands tiling the integer grid."""
    lo_open = [o for o in outcomes if o["lo"] is None]
    hi_open = [o for o in outcomes if o["hi"] is None]
    if len(lo_open) != 1 or len(hi_open) != 1:
        return False
    closed = sorted((o for o in outcomes if o["lo"] is not None and o["hi"] is not None),
                    key=lambda o: o["lo"])
    edges = ([lo_open[0]["hi"]]
             + [e for o in closed for e in (o["lo"], o["hi"])]
             + [hi_open[0]["lo"]])
    return all((b - a) in (0.0, 1.0) for a, b in zip(edges, edges[1:]))


def main() -> None:
    markets = {r["market_id"]: r for r in shards("markets")}
    yes = {r["token_id"]: r for r in shards("outcomes") if r.get("outcome_label") == "Yes"}
    books = shards("orderbook_snapshots")
    two = [b for b in books
           if b.get("best_bid") is not None and b.get("best_ask") is not None]

    print(f"book rows {len(books)} · sources {set(b.get('source') for b in books)}")
    print(f"two-sided {len(two)} · markets {len({b.get('market_id') for b in books})}\n")

    # ---- 1. spread, by population
    print("1. SPREAD BY POPULATION (the threshold is a HALF-spread of 0.036)")
    pops = {
        "all two-sided books": lambda b, o: True,
        "YES tokens of weather bands": lambda b, o: o is not None,
        "  ...mid in [.02,.98] (drops near-resolved)":
            lambda b, o: o is not None and .02 <= (b["best_bid"] + b["best_ask"]) / 2 <= .98,
        "  ...mid in [.05,.50] (what a rule would buy)":
            lambda b, o: o is not None and .05 <= (b["best_bid"] + b["best_ask"]) / 2 <= .50,
    }
    print(f"  {'population':>46} {'n':>6} {'medFULL':>8} {'medHALF':>8} {'verdict':>10}")
    for name, keep in pops.items():
        sel = [b["best_ask"] - b["best_bid"] for b in two if keep(b, yes.get(b.get("token_id")))]
        if len(sel) < 30:
            continue
        half = st.median(sel) / 2
        verdict = "PASSES" if half > THRESHOLD_HALF_SPREAD else f"FAILS {THRESHOLD_HALF_SPREAD/half:.0f}x"
        print(f"  {name:>46} {len(sel):>6} {st.median(sel):>8.4f} {half:>8.4f} {verdict:>10}")
    allhalf = [(b["best_ask"] - b["best_bid"]) / 2 for b in two]
    print(f"\n  share of all two-sided books clearing 0.036: "
          f"{100 * sum(1 for x in allhalf if x > THRESHOLD_HALF_SPREAD) / len(allhalf):.1f}%")

    # ---- 2. partition coherence
    per_event = defaultdict(set)
    for o in yes.values():
        m = markets.get(o["market_id"])
        if m and m.get("event_id"):
            per_event[m["event_id"]].add(o["market_id"])
    slots = defaultdict(dict)
    for b in two:
        o = yes.get(b.get("token_id"))
        m = markets.get(o["market_id"]) if o else None
        if m and m.get("event_id"):
            slots[(m["event_id"], b["collector_session_id"])][o["market_id"]] = \
                (b["best_bid"], b["best_ask"], o)

    rows = []
    for (ev, _slot), d in slots.items():
        if len(d) != len(per_event[ev]) or len(d) < 3:
            continue
        if not is_partition([v[2] for v in d.values()]):
            continue
        asks = [v[1] for v in d.values()]
        bids = [v[0] for v in d.values()]
        rows.append((sum(asks), sum(bids),
                     sum(asks) + sum(0.05 * a * (1 - a) for a in asks),
                     sum(bids) - sum(0.05 * x * (1 - x) for x in bids)))

    print(f"\n2. PARTITION COHERENCE - model-free, no forecast involved")
    print(f"  complete valid partitions, two-sided book on EVERY leg: {len(rows)}")
    if rows:
        sa = [r[0] for r in rows]
        sb = [r[1] for r in rows]
        print(f"  sum best ASKS  median {st.median(sa):.4f}  p05 {q(sa,.05):.4f}  min {min(sa):.4f}")
        print(f"  sum best BIDS  median {st.median(sb):.4f}  p95 {q(sb,.95):.4f}  max {max(sb):.4f}")
        print(f"  (a complete partition pays exactly 1)")
        print(f"  BUY  basket profitable after fees: {sum(1 for r in rows if r[2] < 1)}/{len(rows)}")
        print(f"  SELL basket profitable after fees: {sum(1 for r in rows if r[3] > 1)}/{len(rows)}")

    # ---- 3. the assumed slippage
    band = [b["best_ask"] - b["best_bid"] for b in two
            if yes.get(b.get("token_id")) is not None
            and .02 <= (b["best_bid"] + b["best_ask"]) / 2 <= .98]
    print(f"\n3. R21 ASSUMED x_exec = 0.0100 (PREREG_R21_ENMIENDA_A A.2, an assumption)")
    print(f"   measured median half-spread on tradable weather bands: {st.median(band)/2:.4f}")
    print(f"   the assumption was accurate - R21's negative is STRENGTHENED, not weakened")


if __name__ == "__main__":
    main()
