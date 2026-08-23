"""
weather_agent.polymarket — Phase 2B Market Discovery package
============================================================
STATUS: IMPLEMENTED (authored without Python execution — NOT tested/validated
here). Scope 2B = market discovery + resolution discovery + catalog
normalization ONLY. NO feature builder, NO Strategy A, NO models/backtest/paper/
execution/L2 strategy (those are later subphases).

Modules:
  * discovery.py  — temperature-market discovery via gamma /events; writes
                    markets + outcomes (+ market_fee_schedule) with provenance.
  * resolution.py — per-market resolution rule parsing (station, ICAO, source,
                    unit, rounding_rule, measurement_rule, resolution_timestamp,
                    winning_outcome). Ported from phase1_5/resolution_discovery.py.
  * fees.py       — map gamma fee / tick / min fields -> market_fee_schedule
                    (fee_status KNOWN where read, UNKNOWN if absent).

NOTE (migration): this package supersedes the legacy flat module
`weather_agent/polymarket.py`. On a Python runtime the package shadows the flat
module of the same name; the flat module is reference-only and should be removed
in a cleanup step once 2B is validated on Hetzner.
"""
