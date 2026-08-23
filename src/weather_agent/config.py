"""
weather_agent.config  —  central settings for the MVP 3.0 platform (Phase 2A)
=============================================================================
STATUS: IMPLEMENTED (authored without Python execution — NOT tested/validated
here). Stdlib-only so BOTH the pipeline tier and the thin dashboard tier can
import it cheaply.

WHAT CHANGED vs the legacy config (deliberate, per the 2A spec):
  * The hardcoded `STATIONS` dict (4 US airports) is RETIRED. Resolution station,
    coordinates, unit and rounding rule are per-market facts DISCOVERED at
    ingestion (see phase1_5/resolution_discovery.py) and stored in the `markets`
    table — never hand-typed here. `city_registry` below only lists the *target
    city universe* (configurable / expandable) plus civil hints for matching.
  * Endpoints are DOCUMENTED (not assumed). Each entry carries a `status` flag so
    an unverified host/path is never silently trusted.

BACKWARD-COMPAT: the base URL names GAMMA / CLOB / HIST_FORECAST are kept so any
code that imported them keeps resolving. (The legacy flat modules that imported
`STATIONS` will need porting in 2B+ — that is expected by the migration plan.)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# --------------------------------------------------------------------------- paths
# src/weather_agent/config.py -> parents[2] == repository root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# DuckDB file location. Override with WEATHER_AGENT_DB_PATH (absolute path).
DB_PATH: str = os.environ.get(
    "WEATHER_AGENT_DB_PATH",
    str(PROJECT_ROOT / "data" / "processed" / "weather_agent.duckdb"),
)

# --------------------------------------------------------------------------- API base URLs
# Verified in the legacy code and/or the phase 1.5 probes (read-only GET only).
GAMMA = "https://gamma-api.polymarket.com"          # market/event catalog
CLOB = "https://clob.polymarket.com"                # prices-history (indicative)
DATA_API = "https://data-api.polymarket.com"        # trades / activity / holders
HIST_FORECAST = "https://historical-forecast-api.open-meteo.com/v1/forecast"

# CLOB websocket base — NOT exercised in any code we have. Do NOT assume the exact
# path; fill it from docs.polymarket.com before building the forward collector (2B+).
CLOB_WS_URL: str | None = os.environ.get("WEATHER_AGENT_CLOB_WS_URL")  # e.g. wss://...

# Polymarket "Highest temperature" tag (verified live in the legacy code).
TEMP_TAG_ID = 104596

# --------------------------------------------------------------------------- documented endpoints
# `status` legend:
#   VERIFIED_IN_CODE  — exercised by legacy code or a phase 1.5 probe this project ran.
#   UNVERIFIED        — named in the spec but NOT independently confirmed here; verify
#                        against docs.polymarket.com before relying on it.
ENDPOINTS: dict[str, dict] = {
    "gamma_events": {
        "method": "GET",
        "url": f"{GAMMA}/events",
        "status": "VERIFIED_IN_CODE",
        "params": "tag_id, closed, order, ascending, limit, offset",
        "notes": "Event catalog; each event carries markets[] with groupItemTitle, "
                 "outcomes, outcomePrices, clobTokenIds, umaResolutionStatus, liquidity, volume.",
    },
    "gamma_markets": {
        "method": "GET",
        "url": f"{GAMMA}/markets",
        "status": "VERIFIED_IN_CODE",
        "params": "tag_id, closed, order, ascending, end_date_min, end_date_max, limit, offset",
        "notes": "Market-level catalog used by the phase 1.5 discovery probe.",
    },
    "clob_prices_history": {
        "method": "GET",
        "url": f"{CLOB}/prices-history",
        "status": "VERIFIED_IN_CODE",
        "params": "market(=clobTokenId), startTs, endTs, fidelity(minutes), interval",
        "notes": "BACKFILL RULE (phase 1.5B): use startTs+endTs+fidelity=1 in windows "
                 "<=48h and STITCH locally. NEVER use interval=max (it aggregates -> the "
                 "false '12h floor'). Returned p is INDICATIVE (midpoint/estimated), NEVER "
                 "an executable price. Response: {'history':[{'t':<unix s>,'p':<0..1>}]}.",
    },
    "data_api_trades": {
        "method": "GET",
        "url": f"{DATA_API}/trades",
        "status": "VERIFIED_IN_CODE",
        "params": "market(=conditionId), limit, offset",
        "notes": "Executed trades (forward-only for our store). Used by the phase 1.5B "
                 "p-semantics cross-check.",
    },
    "clob_websocket": {
        "method": "WSS",
        "url": CLOB_WS_URL,  # None until set from official docs
        "status": "UNVERIFIED",
        "params": "subscribe: book / price_change (per asset/market)",
        "notes": "Live order-book + trade stream for the FORWARD-ONLY collector (2B+). "
                 "Historical L2 does not exist. Exact wss URL must be filled from "
                 "docs.polymarket.com — do not assume it.",
    },
    "open_meteo_historical_forecast": {
        "method": "GET",
        "url": HIST_FORECAST,
        "status": "VERIFIED_IN_CODE",
        "params": "latitude, longitude, start_date, end_date, hourly=temperature_2m, "
                  "temperature_unit, timezone, models",
        "notes": "Archived issued forecasts. Pin the forecast issue_time strictly before "
                 "the lead to avoid look-ahead (stored as weather_forecasts.issue_time).",
    },
}

# --------------------------------------------------------------------------- city registry
# CONFIGURABLE target-city universe (initial 6, expandable). This is NOT the
# resolution mapping: the authoritative station / ICAO / unit / rounding_rule are
# discovered per-market and written to `markets`. Fields here are only:
#   aliases          — lowercase tokens to match a market title/slug to a city
#   civil_tz         — IANA civil timezone (a hint; confirm vs the resolved station)
#   civil_unit_hint  — the civil unit of the country ('F' US / 'C' EU); the market's
#                      actual resolution unit is discovered per-market (may differ)
#   country, enabled
# Aliases seeded from phase1_5/phase1_5b_probe.py CITY_PATTERNS (not invented).
DEFAULT_CITY_REGISTRY: dict[str, dict] = {
    "New York": {
        "aliases": ["new-york", "new york", "nyc"],
        "civil_tz": "America/New_York",
        "civil_unit_hint": "F",
        "country": "US",
        "enabled": True,
    },
    "London": {
        "aliases": ["london"],
        "civil_tz": "Europe/London",
        "civil_unit_hint": "C",
        "country": "GB",
        "enabled": True,
    },
    "Paris": {
        "aliases": ["paris"],
        "civil_tz": "Europe/Paris",
        "civil_unit_hint": "C",
        "country": "FR",
        "enabled": True,
    },
    "Madrid": {
        "aliases": ["madrid"],
        "civil_tz": "Europe/Madrid",
        "civil_unit_hint": "C",
        "country": "ES",
        "enabled": True,
    },
    "Chicago": {
        "aliases": ["chicago"],
        "civil_tz": "America/Chicago",
        "civil_unit_hint": "F",
        "country": "US",
        "enabled": True,
    },
    "Los Angeles": {
        "aliases": ["los-angeles", "los angeles"],
        "civil_tz": "America/Los_Angeles",
        "civil_unit_hint": "F",
        "country": "US",
        "enabled": True,
    },
}


def get_city_registry() -> dict[str, dict]:
    """Return the city registry, allowing a full JSON override via the env var
    WEATHER_AGENT_CITY_REGISTRY (path to a JSON file with the same shape).
    Falls back to DEFAULT_CITY_REGISTRY. Keeps the universe CONFIGURABLE without
    code edits."""
    path = os.environ.get("WEATHER_AGENT_CITY_REGISTRY")
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and data:
                return data
        except Exception:
            # Malformed override must never crash config import; fall back.
            pass
    return dict(DEFAULT_CITY_REGISTRY)


# --------------------------------------------------------------------------- fee config
# FEE placeholder. NEVER assume a single fee (esp. NOT 0). Fees are epoch-dependent
# and live in the `market_fee_schedule` table (fee_status may be UNKNOWN). The
# values below are ONLY conservative defaults/labels for the effective-cost model;
# they are not authoritative and must be replaced by discovered per-regime rows.
FEE_CONFIG: dict[str, object] = {
    "assume_zero_fee": False,               # explicit: do NOT assume zero
    "default_fee_status": "UNKNOWN",        # until a regime is discovered
    "default_fee_regime": "UNKNOWN",
    "effective_cost_components": [           # modelled as "effective fees" (execution)
        "taker_fee", "maker_rebate", "spread_cost", "slippage", "gas_cost",
    ],
    "notes": "Populate market_fee_schedule per fee_regime with effective_from/"
             "effective_to. Historical price is INDICATIVE, so execution cost must be "
             "modelled, never read from the indicative price.",
}

# --------------------------------------------------------------------------- backtest / sizing defaults
DEFAULTS: dict[str, object] = {
    "bankroll": 10_000.0,
    "position_sizing": "fixed_fraction",    # fixed_fraction | kelly | edge
    "fixed_fraction": 0.02,                 # 2% of bankroll per position
    "min_edge_grid": [0.02, 0.03, 0.05, 0.08, 0.10],  # swept in the backtest grid
    "kelly_fraction": 0.25,                 # if position_sizing == 'kelly'
    "size_cap": 0.02,                       # hard cap on any single position fraction
    "price_layer": "INDICATIVE",            # price assumption layer (see PRICE_LAYERS; never executable)
    "random_seed": 42,                      # default seed for reproducible runs
}

# Controlled vocabularies encoded in the schema (kept here for callers/tests).
PRICE_SEMANTICS = (
    "MIDPOINT_ESTIMATED", "INDICATIVE", "LAST_TRADE_INDICATIVE",
    "NEAREST_TRADE_INDICATIVE", "UNKNOWN",
)
SOURCE_WINDOWS = ("DIRECT", "DERIVED")
FEE_STATUSES = ("KNOWN", "UNKNOWN", "ESTIMATED", "DEPRECATED")
AVAILABLE_RESOLUTIONS = ("native_1min", "coarse", "none", "unknown")
# paper_trades.price_layer vocabulary (mirrors the schema CHECK):
#   INDICATIVE           = prices-history midpoint/indicative; NO real fill
#   SIMULATED_EXECUTABLE = simulated fill via spread/depth/slippage/fees
#   EXECUTABLE           = a real, observed fill
PRICE_LAYERS = ("INDICATIVE", "SIMULATED_EXECUTABLE", "EXECUTABLE")
