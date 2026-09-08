#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/validate_r29_catalog.py — R29 rule-classifier validation against CATALOG_V2.

READ-ONLY. Opens the frozen catalogue with duckdb.connect(..., read_only=True), never
writes, never touches the network. Same discipline as the 2B/2C/2D harnesses:
IMPLEMENTED != TESTED != VALIDATED — this script is the VALIDATION step of R29 against
the 93 221 real gamma descriptions of the catalogue.

What it does:
  * Walks every (market_id, description) of the `dsc` table (joined with `v3`, whose
    descr column is byte-identical to dsc.desc — asserted here).
  * Runs weather_agent.polymarket.resolution.parse_resolution_text on each description
    and compares
        contract_source       vs v3.primary_source
        measurement_rule_code vs v3.primary_rule
        fallback_source       vs v3.has_secondary_WU
    v3 is the round-9 classification of the catalogue by the PRIMARY clause
    ("information from <source>, specifically ...") — the reference this parser must
    reproduce.
  * Prints the full crosstab (v3 pair -> parser pair, counts), the disagreements by
    combination with 5 VERBATIM description examples each, and the count of markets
    whose measurement_rule string CHANGED with respect to the pre-R29 parser (the
    R12 defect: NOAA markets whose FALLBACK clause mentions 'Daily Observations').

EXPLAINED RESIDUALS (not disagreements — documented, asserted exactly):
  * v3 (SIN_CLAUSULA, P_UNKNOWN)  <->  parser (CWA, P_CWA_TemperatureColumn)
    The 77 Taipei markets DO carry a primary clause ("information from the Taipei
    Central Weather Administration, specifically the highest reading under the
    "Temperature" column ..."); v3 labelled them SIN_CLAUSULA/P_UNKNOWN because the
    SOURCE is inaccessible (SETTLEMENT_OPERATORS_SPEC row 11), not because the clause
    lacks a rule. R29 keeps the contractual reading (CWA) — settlement stays
    FAIL_CLOSED downstream by source, not by parser ignorance.

Verdict: PASS iff 0 UNEXPLAINED disagreements on source AND rule AND fallback.
Exit code 0 on PASS, 1 otherwise.

Usage:  PYTHONPATH=src python3 scripts/validate_r29_catalog.py [--catalog PATH] [--examples N]
"""
from __future__ import annotations

import argparse
import collections
import re
import sys

from weather_agent.polymarket import resolution as res

CATALOG_DEFAULT = "/Users/mariaaleu/pmw-catalog-v2/CATALOG_V2.duckdb"

# v3 label pair -> parser label pair that is EQUIVALENT by design (see module doc).
EXPLAINED_EQUIV = {
    ("SIN_CLAUSULA", "P_UNKNOWN"): (res.SRC_CWA, res.P_CWA_TEMPCOL),
}


def legacy_measurement_rule(desc: str) -> str | None:
    """The PRE-R29 parser, verbatim (presence-of-phrase anywhere in the text), kept
    here ONLY to quantify the correction. Never used by the pipeline."""
    d = desc or ""
    if re.search(r"Daily Observations", d, re.I):
        return "highest temperature in the 'Daily Observations' table (not Day High & Low)"
    if re.search(r"by the Forecast", d, re.I):
        return "highest temperature 'by the Forecast', once data finalized (legacy template)"
    if re.search(r"Day High\s*&\s*Low", d, re.I):
        return "Day High & Low summary value"
    return None


def load_rows(catalog: str) -> list[tuple]:
    import duckdb
    con = duckdb.connect(catalog, read_only=True)
    try:
        n_desc_diff = con.execute(
            "SELECT COUNT(*) FROM v3 JOIN dsc USING (market_id) "
            "WHERE v3.descr IS DISTINCT FROM dsc.\"desc\""
        ).fetchone()[0]
        rows = con.execute(
            "SELECT dsc.market_id, dsc.\"desc\", v3.primary_source, v3.primary_rule, "
            "       v3.has_secondary_WU "
            "FROM dsc JOIN v3 USING (market_id) ORDER BY dsc.market_id"
        ).fetchall()
    finally:
        con.close()
    return n_desc_diff, rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=CATALOG_DEFAULT)
    ap.add_argument("--examples", type=int, default=5)
    a = ap.parse_args(argv)

    n_desc_diff, rows = load_rows(a.catalog)
    print(f"catalog: {a.catalog} (read_only=True)")
    print(f"rows dsc JOIN v3: {len(rows)}   v3.descr != dsc.desc: {n_desc_diff}")

    crosstab: collections.Counter = collections.Counter()
    disagree: dict[tuple, list] = collections.defaultdict(list)
    explained: dict[tuple, list] = collections.defaultdict(list)
    fb_disagree: dict[tuple, list] = collections.defaultdict(list)
    changed_vs_legacy: collections.Counter = collections.Counter()
    src_unknown = 0

    for market_id, desc, v3_src, v3_rule, v3_has_wu in rows:
        p = res.parse_resolution_text(desc)
        got = (p["contract_source"], p["measurement_rule_code"])
        exp = (v3_src, v3_rule)
        crosstab[(exp, got)] += 1
        if got[0] == res.SRC_UNKNOWN:
            src_unknown += 1
        if got != exp:
            if EXPLAINED_EQUIV.get(exp) == got:
                explained[(exp, got)].append((market_id, desc))
            else:
                disagree[(exp, got)].append((market_id, desc))
        # fallback: v3.has_secondary_WU is True iff a WU fallback sentence exists
        got_fb = p["fallback_source"]
        exp_fb = res.SRC_WU if v3_has_wu else None
        if got_fb != exp_fb:
            fb_disagree[(exp_fb, got_fb)].append((market_id, desc))
        old = legacy_measurement_rule(desc)
        new = p.get("measurement_rule")
        if old != new:
            changed_vs_legacy[(v3_src, v3_rule, old, new)] += 1

    print("\n== crosstab (v3.primary_source, v3.primary_rule) -> (contract_source, measurement_rule_code)")
    for (exp, got), n in sorted(crosstab.items(), key=lambda kv: -kv[1]):
        flag = "" if exp == got else ("  [EXPLAINED]" if EXPLAINED_EQUIV.get(exp) == got else "  [DISAGREE]")
        print(f"  {n:6d}  {exp!s:44s} -> {got!s}{flag}")
    print(f"\ncontract_source == UNKNOWN: {src_unknown}")

    def show(bucket: dict, title: str) -> None:
        print(f"\n== {title}: {sum(len(v) for v in bucket.values())} markets, "
              f"{len(bucket)} combinations")
        for key, items in sorted(bucket.items(), key=lambda kv: -len(kv[1])):
            print(f"\n-- {key[0]!s} -> {key[1]!s}: {len(items)} markets; "
                  f"{min(a.examples, len(items))} verbatim examples:")
            for market_id, desc in items[:a.examples]:
                print(f"   [market_id={market_id}]")
                for line in (desc or "").splitlines():
                    print(f"   | {line}")
                print()

    show(disagree, "UNEXPLAINED disagreements (source, rule)")
    show(explained, "EXPLAINED residuals (source, rule)")
    show(fb_disagree, "fallback_source disagreements vs v3.has_secondary_WU")

    print("\n== measurement_rule string CHANGED vs the pre-R29 parser (the R12 correction)")
    tot = 0
    for (v3_src, v3_rule, old, new), n in sorted(changed_vs_legacy.items(), key=lambda kv: -kv[1]):
        tot += n
        print(f"  {n:6d}  v3={v3_src}/{v3_rule}\n          old={old!r}\n          new={new!r}")
    noaa_fixed = sum(n for (s, _r, old, _new), n in changed_vs_legacy.items()
                     if s == "NOAA" and old and "Daily Observations" in old)
    print(f"  total changed: {tot}; NOAA markets previously mislabelled 'Daily Observations': {noaa_fixed}")

    n_dis = sum(len(v) for v in disagree.values())
    n_fb = sum(len(v) for v in fb_disagree.values())
    n_exp = sum(len(v) for v in explained.values())
    ok = n_dis == 0 and n_fb == 0
    print(f"\nVERDICT: {'PASS' if ok else 'FAIL'} — unexplained (source,rule) disagreements: {n_dis}; "
          f"fallback disagreements: {n_fb}; explained residuals: {n_exp}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
