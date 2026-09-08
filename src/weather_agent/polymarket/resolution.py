"""
weather_agent.polymarket.resolution — per-market resolution discovery (Phase 2B)
================================================================================
STATUS: IMPLEMENTED + TESTED (tests/test_resolution.py, offline fixtures). NOT
VALIDATED against live gamma from this tree. Pure parsing (no network, no DB).
Ported + extended from the pre-2A
resolution-discovery probe (legacy repo, not in this tree), grounded in the REAL
gamma description template
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

R29 — CONTRACT SOURCE / MEASUREMENT RULE FROM THE PRIMARY CLAUSE (refutation R12):
  The pre-R29 parser classified `measurement_rule` by the MERE PRESENCE of phrases
  ('Daily Observations', 'by the Forecast', 'Day High & Low') anywhere in the
  description. NOAA-sourced markets carry a FALLBACK clause ("If NOAA data for the
  observation date is unavailable by 11:59 PM ET ..., the Weather Underground
  Daily Observations table will be used as the resolution source.") and were
  therefore mislabelled as Wunderground 'Daily Observations' (3 333 markets in
  CATALOG_V2, same defect fixed in the catalogue's v3.primary_rule in round 9).
  Now:
    * the description is split into the PRIMARY clause (the first sentence
      "information from <source>, specifically ..." / "according to <source>")
      and the FALLBACK sentence(s) ("If <source> data ... unavailable/missing ...
      <other source> will be used ...");
    * `contract_source` in {WU, NOAA, HKO, CWA, UNKNOWN} is read from the primary
      clause ONLY; `fallback_source` (same enum, or None) from the fallback clause;
    * `measurement_rule_code` (P_* label, identical to v3.primary_rule of the
      catalogue) + the human `measurement_rule` string are derived from the primary
      source + the non-fallback text (the 'Daily Observations' preamble of the
      recent WU template is NOT a fallback and still qualifies WU markets).
  `measurement_rule` for NOAA markets therefore CHANGES value with respect to the
  pre-R29 parser (they were "'Daily Observations' table ..." — that was the bug);
  WU markets keep the exact pre-R29 strings. Markets with the generic WU clause
  (no table qualifier), NOAA, HKO and CWA markets — pre-R29 measurement_rule None —
  now carry a rule string; their P_* code makes the epoch explicit.
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

# R29 — contract-source enum (v3.primary_source of CATALOG_V2 uses the same labels,
# except that v3 has 'SIN_CLAUSULA' where this parser says CWA: see
# scripts/validate_r29_catalog.py for the explained residual).
SRC_WU = "WU"          # Weather Underground / wunderground.com history page
SRC_NOAA = "NOAA"      # weather.gov/wrh/timeseries "Temp" column
SRC_HKO = "HKO"        # Hong Kong Observatory "Absolute Daily Max"
SRC_CWA = "CWA"        # Taipei Central Weather Administration "Temperature" column
SRC_UNKNOWN = "UNKNOWN"
CONTRACT_SOURCES = (SRC_WU, SRC_NOAA, SRC_HKO, SRC_CWA, SRC_UNKNOWN)

# R29 — measurement-rule codes. The first six are BYTE-IDENTICAL to the catalogue's
# v3.primary_rule labels; P_CWA_TemperatureColumn is new (v3 says P_UNKNOWN for the
# 77 CWA markets because their SOURCE is inaccessible, not because the clause lacks
# a rule — the clause names the "Temperature" column explicitly).
P_WU_DAILYOBS = "P_WU_DailyObservations"
P_BY_FORECAST = "P_byForecast"
P_WU_GENERIC = "P_WU_GENERIC_sin_calificador"
P_NOAA_TEMPCOL = "P_NOAA_TempColumn"
P_NOAA_HOURLY = "P_NOAA_HourlyData"
P_HKO_ABSMAX = "P_HKO_AbsDailyMax"
P_CWA_TEMPCOL = "P_CWA_TemperatureColumn"
P_WU_DAYHIGHLOW = "P_WU_DayHighLow"     # defensive: never seen in CATALOG_V2
P_UNKNOWN = "P_UNKNOWN"

# Human strings. The WU ones are the pre-R29 strings, verbatim (stored in
# markets.measurement_rule since 2B — DO NOT reword without a migration note).
MEASUREMENT_RULE_TEXT = {
    P_WU_DAILYOBS: "highest temperature in the 'Daily Observations' table (not Day High & Low)",
    P_BY_FORECAST: "highest temperature 'by the Forecast', once data finalized (legacy template)",
    P_WU_DAYHIGHLOW: "Day High & Low summary value",
    P_WU_GENERIC: "highest temperature recorded for all times on this day (Wunderground, no table qualifier)",
    P_NOAA_TEMPCOL: "highest reading under the NOAA 'Temp' column for all times on this day (weather.gov timeseries)",
    P_NOAA_HOURLY: "highest reading under the NOAA 'Temp' column, Hourly Data only ('Show Hourly Data')",
    P_HKO_ABSMAX: "HKO 'Absolute Daily Max (deg. C)' from the Daily Extract",
    P_CWA_TEMPCOL: "highest reading under the CWA 'Temperature' column for all hours on that date",
}

# A FALLBACK sentence: starts with 'If', says some data is unavailable/missing, and
# ends at the next sentence boundary (a period followed by whitespace/end, or a
# newline). The '11:59 PM ET' inside the NOAA sentence carries no period, and URLs
# never occur in fallback sentences, so this boundary is safe on the whole catalogue.
_FALLBACK_RE = re.compile(
    r"\bIf\b[^\n.]*?\b(?:unavailable|missing|not available)\b[^\n]*?(?:\.(?=\s|$)|(?=\n)|$)",
    re.I,
)
# The PRIMARY clause: first "information from <X> ..." / "according to <X> ..."
# sentence (searched on the text with fallback sentences removed). group(1) starts
# with the source name; the sentence ends at a period followed by whitespace/end
# (so 'wunderground.com/...' inside the URL does not end it) or at a newline.
_PRIMARY_RE = re.compile(
    r"\b(?:information from|according to)\s+(.+?)(?:\.(?=\s|$)|(?=\n)|$)",
    re.I | re.S,
)
# Source name -> enum, tried IN ORDER against the HEAD of the primary clause (up to
# the first comma), so "from Wunderground, ... for the Hong Kong International
# Airport Station" is WU, never HKO.
# Order matters: the more specific host wins. `weather.gov.hk` (HKO) is a suffix
# of the NOAA pattern `weather.gov`, so HKO is tried first AND the NOAA pattern
# carries a negative lookahead. Either guard alone would do; both are kept so a
# future reordering cannot silently reintroduce the misclassification.
_SOURCE_NAME_RES: tuple[tuple[str, re.Pattern], ...] = (
    (SRC_WU, re.compile(r"Wunderground|Weather\s+Underground|wunderground\.com", re.I)),
    (SRC_HKO, re.compile(r"Hong\s+Kong\s+Observatory|weather\.gov\.hk", re.I)),
    (SRC_CWA, re.compile(r"Central\s+Weather\s+Administration|\bCWA\b|cwa\.gov\.tw", re.I)),
    (SRC_NOAA, re.compile(r"\bNOAA\b|weather\.gov(?!\.hk)", re.I)),
)


@dataclass
class ResolutionRule:
    """The parsed resolution chain for ONE market, with per-field confidence."""
    city: str | None = None
    resolution_source: str | None = None       # Wunderground history URL
    station: str | None = None                  # station NAME (e.g. 'Esenboğa Intl Airport')
    station_identifier: str | None = None       # ICAO tail of the URL (e.g. 'LTAC')
    measurement_rule: str | None = None         # human string (MEASUREMENT_RULE_TEXT)
    measurement_rule_code: str | None = None    # R29 P_* code (== v3.primary_rule)
    contract_source: str | None = None          # R29 primary-clause source (CONTRACT_SOURCES)
    fallback_source: str | None = None          # R29 fallback-clause source, or None
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


def split_fallback_clauses(desc: str) -> tuple[str, list[str]]:
    """Split a description into (text WITHOUT fallback sentences, [fallback sentences]).
    A fallback sentence is an "If <source> data ... unavailable/missing ..." sentence
    (see _FALLBACK_RE). Pure. Both catalogue variants are captured:
      "If NOAA data for the observation date is unavailable by 11:59 PM ET on the day
       following the observation date, the Weather Underground Daily Observations
       table will be used as the resolution source."            (3 333 markets)
      "If NOAA data is unavailable or missing for the observation period, Weather
       Underground will be used as the secondary resolution source." (1 584 markets)"""
    d = desc or ""
    fallbacks = [m.group(0).strip() for m in _FALLBACK_RE.finditer(d)]
    return _FALLBACK_RE.sub(" ", d), fallbacks


def primary_clause(desc: str) -> str | None:
    """The PRIMARY resolution clause: the first "information from <source> ..." /
    "according to <source> ..." sentence, searched AFTER removing the fallback
    sentences (so a fallback that itself says 'information from' can never win).
    Returns the sentence text from the source name onward, or None when the
    description has no such clause (truncated excerpts, non-template markets)."""
    body, _ = split_fallback_clauses(desc)
    m = _PRIMARY_RE.search(body)
    return m.group(1).strip() if m else None


def classify_source(text: str | None, *, head_only: bool = True) -> str:
    """Map a clause to a CONTRACT_SOURCES label. With head_only (default) only the
    text UP TO THE FIRST COMMA is inspected — the source name is the first thing after
    'information from'; what follows the comma ("specifically ... for the Hong Kong
    International Airport Station") names the station, not the source. With
    head_only=False the whole text is searched in _SOURCE_NAME_RES order (used for
    fallback sentences and for descriptions lacking a primary clause)."""
    t = text or ""
    if head_only:
        t = t.split(",", 1)[0]
    for label, rx in _SOURCE_NAME_RES:
        if rx.search(t):
            return label
    return SRC_UNKNOWN


def classify_fallback_source(fallbacks: list[str], primary: str) -> str | None:
    """Source named by the fallback sentence(s) as the SECONDARY source: the first
    source mentioned in a fallback sentence that differs from `primary`
    ("If NOAA data ... the Weather Underground ... will be used" -> WU). None when
    there is no fallback sentence or it names no other known source."""
    for sent in fallbacks:
        for label, rx in _SOURCE_NAME_RES:
            if label != primary and rx.search(sent):
                return label
    return None


def classify_measurement_rule(desc: str) -> dict:
    """R29 classifier. Returns a dict with keys
        contract_source        CONTRACT_SOURCES label from the PRIMARY clause
        measurement_rule_code  P_* code (== CATALOG_V2 v3.primary_rule, except CWA)
        measurement_rule       human string (MEASUREMENT_RULE_TEXT) or None
        fallback_source        CONTRACT_SOURCES label from the fallback clause, or None
        fallback_clauses       the verbatim fallback sentence(s) (list, maybe empty)
        primary_clause         the verbatim primary clause, or None
        source_confidence      VERIFIED (primary clause found) | INFERRED (source named
                               elsewhere in the non-fallback text) | UNKNOWN
    Decision table (source first, then the qualifier in the NON-fallback text):
      WU   : 'by the Forecast' in the primary clause -> P_byForecast (legacy template)
             'Daily Observations' anywhere outside fallback -> P_WU_DailyObservations
             'Day High & Low' only (defensive)             -> P_WU_DayHighLow
             otherwise                                     -> P_WU_GENERIC_sin_calificador
      NOAA : 'Hourly Data' outside fallback -> P_NOAA_HourlyData ; "Temp" column ->
             P_NOAA_TempColumn
      HKO  : 'Absolute Daily Max' -> P_HKO_AbsDailyMax
      CWA  : "Temperature" column -> P_CWA_TemperatureColumn
      any other combination -> P_UNKNOWN (measurement_rule None: never guessed).
    Fallback sentences NEVER contribute a qualifier: that is the R12 defect."""
    d = desc or ""
    body, fallbacks = split_fallback_clauses(d)
    pc = primary_clause(d)
    if pc is not None:
        source = classify_source(pc)
        src_conf = VERIFIED if source != SRC_UNKNOWN else UNKNOWN
    else:
        source = classify_source(body, head_only=False)
        src_conf = INFERRED if source != SRC_UNKNOWN else UNKNOWN
    scope = pc if pc is not None else body      # where 'by the Forecast' is looked for

    code = P_UNKNOWN
    if source == SRC_WU:
        if re.search(r"by the Forecast", scope, re.I):
            code = P_BY_FORECAST
        elif re.search(r"Daily Observations", body, re.I):
            code = P_WU_DAILYOBS
        elif re.search(r"Day High\s*&\s*Low", body, re.I):
            code = P_WU_DAYHIGHLOW
        else:
            code = P_WU_GENERIC
    elif source == SRC_NOAA:
        if re.search(r"Hourly Data", body, re.I):
            code = P_NOAA_HOURLY
        elif re.search(r"[\"\u201c']Temp[\"\u201d']\s+column", body, re.I):
            code = P_NOAA_TEMPCOL
    elif source == SRC_HKO:
        if re.search(r"Absolute Daily Max", body, re.I):
            code = P_HKO_ABSMAX
    elif source == SRC_CWA:
        if re.search(r"[\"\u201c']Temperature[\"\u201d']\s+column", body, re.I):
            code = P_CWA_TEMPCOL

    return {
        "contract_source": source,
        "measurement_rule_code": code,
        "measurement_rule": MEASUREMENT_RULE_TEXT.get(code),
        "fallback_source": classify_fallback_source(fallbacks, source),
        "fallback_clauses": fallbacks,
        "primary_clause": pc,
        "source_confidence": src_conf,
    }


def parse_measurement_rule(desc: str) -> str | None:
    """The measurement rule stated in the PRIMARY clause of the description (#2/#8),
    as a human string (MEASUREMENT_RULE_TEXT) or None. Kept for API compatibility;
    since R29 it is classify_measurement_rule(desc)['measurement_rule'] — i.e. it
    no longer fires on the 'Daily Observations' wording of a NOAA market's FALLBACK
    sentence. The template CHANGED over time: recent WU markets cite the 'Daily
    Observations' table; legacy markets (e.g. NYC Dec 2025) cite 'the Forecast ...
    once information is finalized'. Both are captured so the epoch difference is
    visible and never conflated."""
    return classify_measurement_rule(desc)["measurement_rule"]


def parse_resolution_text(desc: str) -> dict:
    """Extract station / source / unit / rounding_rule / measurement_rule from a
    market description. Values are VERIFIED (explicitly stated) when found.
    R29 adds (always present): measurement_rule_code (P_*), contract_source
    (CONTRACT_SOURCES), fallback_source (label or None), primary_clause (verbatim
    or None), contract_source_confidence (VERIFIED/INFERRED/UNKNOWN)."""
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
    # R29: contract source / rule from the PRIMARY clause (fallback clause ignored).
    # New keys are ADDED; every pre-R29 key keeps its name. `measurement_rule` is
    # still only set when a rule was classified (None -> key absent, as before).
    cls = classify_measurement_rule(d)
    if cls["measurement_rule"]:
        out["measurement_rule"] = cls["measurement_rule"]
    out["measurement_rule_code"] = cls["measurement_rule_code"]
    out["contract_source"] = cls["contract_source"]
    out["fallback_source"] = cls["fallback_source"]
    out["primary_clause"] = cls["primary_clause"]
    out["contract_source_confidence"] = cls["source_confidence"]
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
    r.measurement_rule_code = p.get("measurement_rule_code")
    r.contract_source = p.get("contract_source")
    r.fallback_source = p.get("fallback_source")
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
        # R29: VERIFIED only when the primary clause itself named the source
        # (INFERRED when the source was found elsewhere in the non-fallback text).
        "contract_source": (UNKNOWN if p.get("contract_source_confidence") == UNKNOWN
                            else (INFERRED if (used_event_desc or
                                               p.get("contract_source_confidence") == INFERRED)
                                  else VERIFIED)),
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
            # excerpt has NO 'information from' clause -> source INFERRED from the
            # non-fallback text ('Weather Underground'), still WU / DailyObservations
            "contract_source": "WU",
            "measurement_rule_code": "P_WU_DailyObservations",
            "fallback_source": None,
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
