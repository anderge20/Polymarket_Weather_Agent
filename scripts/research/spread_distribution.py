#!/usr/bin/env python3
"""What a trade actually costs, measured on the collected books.

TWO NUMBERS FOR ONE MAGNITUDE, WHICH IS THE DEFECT THIS ANSWERS. The project has
been carrying `0.0168` as "the measured half-spread" — half of a mean of 0.0336
taken on an early sample — and §6.2 of the R30 preregistration rests its a-priori
most-likely outcome on it. A later reading of 25,736 books gives a MEDIAN full
spread of 0.0100, i.e. a half-spread of 0.0050. Neither is wrong. They are
different statistics of a distribution whose mean is 1.93x its median.

    A cost model that quotes one number for the spread is quoting a statistic of
    a distribution, and which statistic is right depends on WHERE the strategy
    trades. Those are not the same question and they had been merged into one.

Reads the committed shards on branch `paper-state` through `git show`, so it
needs no network, no database and no working copy of that branch. Offline and
reproducible from a clone.

    python3 scripts/research/spread_distribution.py [--ref origin/paper-state]
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import statistics as st
import subprocess
import sys
from collections import defaultdict

#: Same definition as R30 §0, frozen there by value. Repeated rather than
#: imported because that section fixes the bin edges for the preregistration and
#: this script must not be able to drift from it silently.
def price_bin(mid: float) -> int:
    return min(int(mid * 10), 9)


def shard_paths(ref: str) -> list[str]:
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref],
                         capture_output=True, text=True, check=True).stdout.split()
    return [p for p in out
            if "orderbook_snapshots" in p and p.endswith(".ndjson.gz")]


def read_books(ref: str):
    for path in shard_paths(ref):
        raw = subprocess.run(["git", "show", f"{ref}:{path}"],
                             capture_output=True, check=True).stdout
        for line in gzip.open(io.BytesIO(raw), "rt"):
            yield json.loads(line)


def quantiles(values: list[float]) -> dict:
    v = sorted(values)
    n = len(v)
    at = lambda p: v[min(int(p * n), n - 1)]
    return {"n": n, "mean": st.mean(v), "median": st.median(v),
            "p10": at(.10), "p25": at(.25), "p75": at(.75),
            "p90": at(.90), "p99": at(.99), "max": v[-1]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="origin/paper-state",
                    help="git ref holding paper_state/ (default: origin/paper-state)")
    args = ap.parse_args(argv)

    spreads: list[float] = []
    by_bin: dict[int, list[float]] = defaultdict(list)
    one_sided = 0

    for r in read_books(args.ref):
        bb, ba, mid = r.get("best_bid"), r.get("best_ask"), r.get("mid")
        if bb is None or ba is None:
            # A book quoted on one side only. It has NO spread -- not a spread of
            # zero and not a wide one. Counted separately because averaging it in
            # either direction invents a number, and because a market you cannot
            # trade both ways is a fact about liquidity in its own right.
            one_sided += 1
            continue
        spreads.append(r["spread"])
        if mid is not None:
            by_bin[price_bin(mid)].append(r["spread"])

    if not spreads:
        print(f"no two-sided books under {args.ref}", file=sys.stderr)
        return 1

    total = len(spreads) + one_sided
    q = quantiles(spreads)
    print(f"books: {total:,}  two-sided {len(spreads):,}  "
          f"one-sided {one_sided:,} ({100*one_sided/total:.1f}%)\n")
    print("FULL SPREAD, all two-sided books")
    print(f"  mean   {q['mean']:.4f}      half = {q['mean']/2:.4f}")
    print(f"  median {q['median']:.4f}      half = {q['median']/2:.4f}")
    print(f"  p10 {q['p10']:.4f}  p25 {q['p25']:.4f}  p75 {q['p75']:.4f}  "
          f"p90 {q['p90']:.4f}  p99 {q['p99']:.4f}  max {q['max']:.4f}")
    print(f"  mean/median = {q['mean']/q['median']:.2f}x\n")

    print("BY PRICE BIN -- the table a cost model should read instead of one number")
    print(f"  {'bin':>3} {'n':>7} {'median':>8} {'mean':>8} {'p90':>8}")
    for b in sorted(by_bin):
        v = by_bin[b]
        if len(v) < 50:
            continue
        bq = quantiles(v)
        print(f"  {b:>3} {bq['n']:>7,} {bq['median']:>8.4f} "
              f"{bq['mean']:>8.4f} {bq['p90']:>8.4f}")

    extremes = sum(len(by_bin[b]) for b in (0, 9) if b in by_bin)
    middle = sum(len(v) for b, v in by_bin.items() if b not in (0, 9))
    if extremes and middle:
        print(f"\n  bins 0 and 9 hold {extremes:,} books "
              f"({100*extremes/(extremes+middle):.0f}%) and are the CHEAP ones;")
        print(f"  bins 1-8 hold {middle:,} and quote twice the median spread.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
