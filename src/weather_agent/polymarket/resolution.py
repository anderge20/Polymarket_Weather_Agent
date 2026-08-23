"""
weather_agent.polymarket.resolution — per-market resolution discovery (Phase 2B)
================================================================================
STATUS: IMPLEMENTED. Authored WITHOUT Python execution — not tested/validated
here. Pure parsing (no network, no DB). Ported + extended from
phase1_5/resolution_discovery.py, grounded in the REAL gamma description template
(verified live 2026-08-21 for Ankara/Wellington markets).

WHAT IT EXTRACTS, MARKET-SPECIFICALLY (the unambiguous resolution chain #2):
  market -> token/outcome -> resolution_source -> station -> station_identifier
        -> measurement_rule -> unit -> rounding_rule -> resolution_timestamp
        -> winning_outcome

Each field is parsed from THAT market's own gamma fields (its `description`,
`resolutionSource`, `umaEndDate`, `outcomes`/`outcomePrices`) — never an
approximate city/station lookup. Every field carries a confidence flag
(VERIFIED / INFERRED / UNKNOWN).

GROUND-TRUTH SEPARATION (#3): `winning_outcome` is the FINAL RESOLVED OUTCOME as
settled by Polymarket/UMA (from `outcomePrices`). It is NOT an observed weather
value. `measurement_rule` records HOW the outcome was measured (the Daily
Observations table high at the station) but 2B stores NO observed temperature;
observed weather is a separate subphase and must not be conflated with the
resolved outcome.

REAL description template (verbatim excerpt, Ankara 2026-08-20):
  "This market will resolve based on the highest temperature recorded in the
   'Daily Observations' table on Weather Underground, not the figure displayed in
   the 'Day High & Low' summary section ... resolve to the temperature range that
   contains the highest temperature recorded at the Esenboğa Intl Airport Station
   in degrees Celsius on 20 Aug '26 ... available here:
   https://www.wunderground.com/history/daily/tr/%C3%A7ubuk/LTAC ... measures
   temperatures to whole degrees Celsius (eg, 9°C)."
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

VERIFIED = "VERIFIED"   # value read/parsed directly from an explicit source field
INFERRED = "INFERRED"   # derived by heuristic (not explicit in the source)
UNKNOWN = "UNKNOWN"     # not present / could not be determined
DATA_ERROR = "DATA_ERROR"  # inconsistent source data (e.g. >1 winning band)


# --------------------------------------------------------------------------- regexes
# ICAO is the last path segment of the Wunderground history URL, e.g.
# .../history/daily/tr/%C3%A7ubuk/LTAC -> LTAC ; .../nz/wellington/NZWN -> NZWN.
_ICAO_RE = re.compile(r"wunderground\.com/history/daily/[a-z]{2}/[^/]+/([A-Za-z0-9]{3,5})", re.I)
_URL_RE = re.compile(r"https://www\.wunderground\.com/history/daily/\S+", re.I)
# "recorded at the <Station Name> Station in degrees ..." (non-greedy, unicode-safe)
_STATION_RE = re.compile(r"recorded at the (.+?) Station", re.I)
_CITY_TITLE_RE = re.compile(r"temperature in ([A-Za-z .,'\-]+?) on ", re.I)
_CITY_SLUG_RE = re.compile(r"temperature-in-([a-z0-9\-]+?)-on-", re.I)


@dataclass
class ResolutionRule:
    """The parsed resolution chain for ONE market, with per-field confidence."""
    city: str | None = None
    resolution_source: str | None = None       # Wunderground history URL
    station: str | None = None                  # station NAME (e.g. 'Esenboğa Intl Airport')
    station_identifier: str | None = None       # ICAO tail of the URL (e.g. 'LTAC')
    measurement_rule: str | None = None         # e.g. 'Daily Observations table high'
    unit: str | None = None                     # 'C' | 'F'
    rounding_rule: str | None = None            # 'whole degree' | 'tenths'
    resolution_timestamp: str | None = None     # ISO-8601 UTC (from umaEndDate)
    winning_outcome: str | None = None          # 'Yes' | 'No' (this market's resolved side)
    confidence: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- helpers
def jf(x: Any) -> list:
    """gamma returns outcomes/outcomePrices/clobTokenIds as JSON-encoded strings;
    normalise to a list."""
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        try:
            out = json.loads(x)
            return out if isinstance(out, list) else []
        except Exception:
            return []
    return []


def parse_band(label: str, unit: str | None = None) -> tuple[float | None, float | None]:
    """Inclusive (lo, hi) from a band label. Open-ended sides -> None.
        '25°C or below' -> (None, 25) ; '31°C' -> (31, 31) ;
        '76-77°F' -> (76, 77)        ; '35°C or higher' -> (35, None)
    NB: the hyphen in '76-77' is a SEPARATOR, not a minus sign."""
    ll = (label or "").lower()
    s = (label or "").replace("°", "").replace("C", "").replace("F", "").strip()
    if "or below" in ll or "or lower" in ll:
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return (None, float(m.group())) if m else (None, None)
    if "or higher" in ll or "or above" in ll:
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return (float(m.group()), None) if m else (None, None)
    rng = re.search(r"(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)", s)
    if rng:
        return (float(rng.group(1)), float(rng.group(2)))
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if m:
        n = float(m.group())
        return (n, n)
    return (None, None)


def parse_city(title: str | None, slug: str | None) -> str | None:
    """City from the event/market title, falling back to the slug."""
    m = _CITY_TITLE_RE.search(title or "")
    if m:
        return m.group(1).strip()
    m = _CITY_SLUG_RE.search((slug or "").lower())
    if m:
        return m.group(1).replace("-", " ").title()
    return None


def parse_measurement_rule(desc: str) -> str | None:
    """The measurement rule stated in the description (#2/#8). The template CHANGED
    over time: recent markets cite the 'Daily Observations' table; legacy markets
    (e.g. NYC Dec 2025) cite 'the Forecast ... once information is finalized'. Both
    are captured so the epoch difference is visible and never conflated."""
    d = desc or ""
    if re.search(r"Daily Observations", d, re.I):
        return "highest temperature in the 'Daily Observations' table (not Day High & Low)"
    if re.search(r"by the Forecast", d, re.I):
        return "highest temperature 'by the Forecast', once data finalized (legacy template)"
    if re.search(r"Day High\s*&\s*Low", d, re.I):
        return "Day High & Low summary value"
    return None


def parse_resolution_text(desc: str) -> dict:
    """Extract station / source / unit / rounding_rule / measurement_rule from a
    market description. Values are VERIFIED (explicitly stated) when found."""
    out: dict = {}
    d = desc or ""
    m = _STATION_RE.search(d)
    if m:
        out["station"] = m.group(1).strip()
    m = _URL_RE.search(d)
    if m:
        url = m.group(0).rstrip('.,")\\')
        out["resolution_source"] = url
        # ICAO is the LAST path segment of the Wunderground URL. US URLs carry an
        # extra state segment (us/ny/new-york-city/KLGA) vs non-US (tr/%C3%A7ubuk/
        # LTAC), so take the tail rather than a fixed position.
        tail = url.rstrip("/").split("/")[-1]
        if re.fullmatch(r"[A-Za-z0-9]{3,5}", tail):
            out["station_identifier"] = tail.upper()
    # Rely on the explicit "degrees Celsius/Fahrenheit" wording in the resolution
    # sentence — NOT bare °C/°F, which BOTH appear in the toggle boilerplate
    # ("switch ... between °F and °C") and would misclassify every market.
    if re.search(r"degrees?\s+Celsius", d, re.I):
        out["unit"] = "C"
    elif re.search(r"degrees?\s+Fahrenheit", d, re.I):
        out["unit"] = "F"
    if re.search(r"whole degrees?", d, re.I):
        out["rounding_rule"] = "whole degree"
    elif re.search(r"tenths|one decimal", d, re.I):
        out["rounding_rule"] = "tenths"
    mr = parse_measurement_rule(d)
    if mr:
        out["measurement_rule"] = mr
    return out


def resolved_outcome(market: dict) -> str | None:
    """This market's FINAL RESOLVED OUTCOME. RESOLVED iff EXACTLY ONE outcome price
    == 1 and EVERY other == 0 (exact NUMERIC compare — never startswith). Any other
    combination (no 1, two 1s, fractional, unparsable) -> None
    (UNKNOWN / INVALID_RESOLUTION). Settlement ground truth — NOT an observed
    weather value (#3)."""
    outs = jf(market.get("outcomes"))
    prices = jf(market.get("outcomePrices"))
    if not outs or not prices or len(outs) != len(prices):
        return None
    nums: list[float] = []
    for p in prices:
        try:
            nums.append(float(str(p).strip()))
        except (TypeError, ValueError):
            return None
    ones = [i for i, x in enumerate(nums) if x == 1.0]
    zeros = [i for i, x in enumerate(nums) if x == 0.0]
    if len(ones) == 1 and len(zeros) == len(nums) - 1:
        return str(outs[ones[0]]).strip()
    return None


def event_winning_band(markets: list[dict]) -> dict:
    """Determine the event's winning BAND with an explicit STATUS — never 'first
    match'. A band is a winner iff its own resolved_outcome() == 'Yes' (exactly
    one price 1, rest 0). Then:
      * exactly ONE winner  -> status VERIFIED
      * ZERO winners        -> status UNKNOWN  (unresolved / not fully settled)
      * MORE THAN ONE       -> status DATA_ERROR (inconsistent_resolution)
    Returns {'status', 'winning_band', 'n_winners', 'winning_bands'}."""
    winners = [
        (m.get("groupItemTitle") or m.get("question"))
        for m in (markets or [])
        if resolved_outcome(m) == "Yes"
    ]
    n = len(winners)
    if n == 1:
        return {"status": VERIFIED, "winning_band": winners[0],
                "n_winners": 1, "winning_bands": winners}
    if n == 0:
        return {"status": UNKNOWN, "winning_band": None,
                "n_winners": 0, "winning_bands": []}
    return {"status": DATA_ERROR, "winning_band": None,
            "n_winners": n, "winning_bands": winners}


def band_integrity(labels: list[str], unit: str | None = None) -> dict:
    """Analyse a set of band labels as a probability partition (critical for the
    future P(max_temp = band) with sum(prob) ~= 1). Does NOT assume gamma gives a
    perfect partition. Returns:
      ordered       band labels sorted by (lo, hi) [open-low first, open-high last]
      lower_open    the single open-ended LOW band ('or below'), or None / list if !=1
      upper_open    the single open-ended HIGH band ('or higher'), or None / list if !=1
      n_lower_open / n_upper_open   counts (must each be 1 for a clean partition)
      overlaps      list of (label_a, label_b) that overlap
      gaps          list of (after_label, before_label, (hi, next_lo)) integer-temp gaps
      is_partition  True iff exactly one lower_open + one upper_open + no overlaps + no gaps
    """
    NEG, POS = float("-inf"), float("inf")
    rows = []
    for lbl in labels:
        lo, hi = parse_band(lbl, unit)
        rows.append({"label": lbl, "lo": lo, "hi": hi,
                     "nlo": lo if lo is not None else NEG,
                     "nhi": hi if hi is not None else POS})
    lower_open = [r["label"] for r in rows if r["lo"] is None]
    upper_open = [r["label"] for r in rows if r["hi"] is None and r["lo"] is not None]
    ordered = sorted(rows, key=lambda r: (r["nlo"], r["nhi"]))

    overlaps: list[tuple] = []
    gaps: list[tuple] = []
    for i in range(1, len(ordered)):
        prev, cur = ordered[i - 1], ordered[i]
        if cur["nlo"] <= prev["nhi"]:
            overlaps.append((prev["label"], cur["label"]))
        elif cur["nlo"] > prev["nhi"] + 1:     # integer-temperature gap
            gaps.append((prev["label"], cur["label"], (prev["nhi"], cur["nlo"])))

    is_partition = (len(lower_open) == 1 and len(upper_open) == 1
                    and not overlaps and not gaps)
    return {
        "ordered": [r["label"] for r in ordered],
        "lower_open": lower_open[0] if len(lower_open) == 1 else (lower_open or None),
        "upper_open": upper_open[0] if len(upper_open) == 1 else (upper_open or None),
        "n_lower_open": len(lower_open),
        "n_upper_open": len(upper_open),
        "overlaps": overlaps,
        "gaps": gaps,
        "is_partition": is_partition,
    }


def discover_rule(market: dict, event: dict, resolution_timestamp: str | None = None) -> ResolutionRule:
    """Build the market-specific ResolutionRule. Prefers the MARKET's own
    description/resolutionSource; falls back to the event's only if the market
    lacks them (and flags that as INFERRED)."""
    r = ResolutionRule()
    desc = market.get("description") or ""
    used_event_desc = False
    if not desc:
        desc = event.get("description") or ""
        used_event_desc = bool(desc)

    p = parse_resolution_text(desc)
    r.station = p.get("station")
    r.station_identifier = p.get("station_identifier")
    r.resolution_source = p.get("resolution_source") or market.get("resolutionSource") \
        or event.get("resolutionSource")
    r.unit = p.get("unit")
    r.rounding_rule = p.get("rounding_rule")
    r.measurement_rule = p.get("measurement_rule")
    r.city = parse_city(event.get("title") or market.get("question"),
                        event.get("slug") or market.get("slug"))
    r.resolution_timestamp = resolution_timestamp
    r.winning_outcome = resolved_outcome(market)

    # per-field confidence
    base = INFERRED if used_event_desc else VERIFIED
    r.confidence = {
        "station": base if r.station else UNKNOWN,
        "station_identifier": base if r.station_identifier else UNKNOWN,
        "resolution_source": VERIFIED if (market.get("resolutionSource") or p.get("resolution_source")) else (INFERRED if r.resolution_source else UNKNOWN),
        "measurement_rule": base if r.measurement_rule else UNKNOWN,
        "unit": base if r.unit else UNKNOWN,
        "rounding_rule": base if r.rounding_rule else UNKNOWN,
        "resolution_timestamp": VERIFIED if r.resolution_timestamp else UNKNOWN,
        "winning_outcome": VERIFIED if r.winning_outcome else UNKNOWN,
        "city": VERIFIED if r.city else UNKNOWN,
    }
    if used_event_desc:
        r.warnings.append("market had no own description; parsed from EVENT description (INFERRED)")
    if not r.station_identifier:
        r.warnings.append("no ICAO parsed from description/URL")
    if not r.unit:
        r.warnings.append("unit not stated explicitly")
    return r


# --------------------------------------------------------------------------- ground truth
# REAL fixtures (verified live via gamma this session). Extend on Hetzner with the
# full sample. The test lives in tests/test_resolution.py (marked authored-not-run).
GROUND_TRUTH_FIXTURES = [
    {
        "city": "Ankara",
        "description": (
            "This market will resolve based on the highest temperature recorded in the "
            "'Daily Observations' table on Weather Underground, not the figure displayed in "
            "the 'Day High & Low' summary section ... recorded at the Esenboğa Intl Airport "
            "Station in degrees Celsius on 20 Aug '26 ... available here: "
            "https://www.wunderground.com/history/daily/tr/%C3%A7ubuk/LTAC ... measures "
            "temperatures to whole degrees Celsius (eg, 9°C)."
        ),
        "expect": {
            "station": "Esenboğa Intl Airport",
            "station_identifier": "LTAC",
            "unit": "C",
            "rounding_rule": "whole degree",
            "measurement_rule": "highest temperature in the 'Daily Observations' table (not Day High & Low)",
        },
    },
    {
        "city": "Wellington",
        "description": (
            "This market will resolve to the temperature range that contains the highest "
            "temperature recorded at the Wellington Station in degrees Celsius on 20 Aug '26 "
            "... https://www.wunderground.com/history/daily/nz/wellington/NZWN ... measures "
            "temperatures to whole degrees Celsius."
        ),
        "expect": {"station_identifier": "NZWN", "unit": "C", "rounding_rule": "whole degree"},
    },
]
