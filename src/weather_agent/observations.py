"""
observations.py — realized station highs from IEM/METAR  (Phase 2B)
====================================================================

Fills `weather_observations` with the daily high actually observed at the
station, which is the label M2 needs to measure forecast error and the backtest
needs to settle a market.

SOURCE: IEM's ASOS archive of METAR reports
(`mesonet.agron.iastate.edu/cgi-bin/request/asos.py`), keyed by ICAO and working
for non-US stations too (verified against EGLC, RKSI, ZBAA). Adopted for the
historical label in D17 as `Y_final`, with the limitation that decision records:
revision impact was measured as negligible **only for IEM/METAR** (0 of 578
station-days change the maximum — REVISIONS, not report types: see
`REPORT_TYPES_ALL`); for Wunderground — the contractual source of
85.6 % of the catalogue — HKO and CWA it is UNKNOWN.

UNITS: IEM reports Fahrenheit (`tmpf`). Forecasts from Open-Meteo are Celsius.
Everything written here is **Celsius**, converted once, at the edge. Mixing the
two silently is the kind of error that produces a plausible-looking backtest with
a 17-degree bias, so the conversion lives in one place and the column meaning is
stated rather than assumed.

`available_at` AND WHY IT IS THE DOWNLOAD TIME
-----------------------------------------------
A daily high physically *occurs* during the day, but only becomes knowable when
the station reports it — and for a retrospective backfill we genuinely do not
know when that was. Rather than invent a plausible publication lag, `available_at`
is set to the instant WE downloaded the row. That is true by construction and
fails closed: the as-of engine can never hand this observation to a prediction
made before the backfill ran, so a retrospective label can never leak into a
feature. D17's prospective capture is what will eventually produce a real as-of
history; this is the honest placeholder until then, not a substitute for it.
"""

from __future__ import annotations

import csv
import io
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from . import database as db
from . import weather

IEM_ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
SOURCE = "IEM_ASOS_METAR"

#: Bounded retries for TRANSIENT failures only (timeout, 5xx). Never for 429.
RETRIES = 4
RETRY_BACKOFF_S = 2.0

#: WHICH IEM REPORT TYPES A SERIES IS BUILT FROM, and why it is no longer one constant.
#:
#: This used to be a single type-3 constant, commented "METAR routine reports only.
#: Specials (SPECI) are excluded so the series is the regular hourly record the
#: climate summaries are built from". The comment described an intention the filter
#: did not meet: IEM does not file every ROUTINE METAR as type 3. At EGLC the
#: half-hourly :20 reports come back only with type 4 — over 2026-04-13..05-20, types
#: 3+4 return 886 reports at :20 and 886 at :50 with none carrying "SPECI", while type 3
#: alone returns 886 at :50 and 1 at :20. So type 3 threw away half of the routine
#: record at half-hourly stations, and the daily high came out low whenever the peak
#: fell on a discarded report.
#:
#: Sized BEFORE changing anything (B-133: 55 stations, 2026-04-09..09-05): 578 of 7 968
#: labelable station-days change their maximum with types 3+4, 525 of them in the 28
#: half-hourly stations (13.0 % of their days). Checked against real settlement
#: (B-134): 247 Wunderground-resolved Celsius station-days with a closed winning band —
#: the full series matches 241, type 3 alone 223, and on the 18 days where the two
#: differ the full series is right 18 times and type 3 never.
#:
#: WHY ONLY CELSIUS. In the Celsius stations no added report sits off the 1 C grid.
#: In the ten US 1 F stations 387 added reports are off the whole-F grid, and on six
#: changed days the NEW maximum itself is — so adding type 4 there would turn a label
#: that is 1-4 F low into UNKNOWN, a refusal. What the resolver shows for such a SPECI
#: is something to MEASURE, not to decide here: Fahrenheit (and KBKF's tenths) keep
#: type 3, declared pending.
#:
#: STILL A PROXY. The Celsius operators are `*_PROXY_IEM`: the contract settles on a
#: Wunderground page and IEM METAR stands in for it. Types 3+4 make the proxy agree
#: more often; they do not make it the source. The 6 of those 247 days where both
#: series agree and the market does not are a separate UNKNOWN, not absorbed here.
REPORT_TYPES_ROUTINE = (3,)
REPORT_TYPES_ALL = (3, 4)


class ObservationError(RuntimeError):
    """Transport or protocol failure while fetching observations."""


class NoObservation(LookupError):
    """No observation covers the requested station-day."""


#: IEM always serves `tmpf`, but the GRID underneath differs by station: ten US
#: stations report whole degrees Fahrenheit, the rest whole Celsius (their C values
#: are integers, their F values are not). Settling a Fahrenheit market on a value
#: converted to Celsius settles it off its own grid, so the native grid and the
#: value on it are stored rather than left for the consumer to reconstruct (A-41).
SERIES = "IEM_ASOS_TMPF"
_EPS = 1e-6

#: Tolerance for "sits on the grid", in the unit of the reading. Loose enough to
#: survive a Fahrenheit round-trip through Celsius, tight enough that a genuine
#: off-grid value is still refused: the finest grid in use is 0.1 F.
_GRID_TOL = 1e-4


def _is_int(x: float) -> bool:
    return abs(x - round(x)) < _EPS


#: The station's SERIES: its scale and its resolution. Measured over 2026-04..09.
#:
#: Ten US stations report whole degrees Fahrenheit (267/267 values). KBKF reports
#: the SAME scale at a finer resolution — 24/24 of its values are tenths of a
#: degree Fahrenheit, only 9 of them whole (46.4, 69.6, 78.4, 83.5, 97.7...).
#: Calling it "mixed C/F" was wrong: there is no mixture of scales, only a finer
#: grid within one. Every other station reports whole Celsius (0 non-integer
#: Celsius values outside the US group).
#:
#: Resolution matters downstream in two different ways. For M2 it only changes the
#: granularity of the error and does not invalidate anything. For settlement it is
#: decisive: with a tenths series, quantisation NONE and FLOOR stop being the same
#: label for 97.7 F.
SERIES_1F = "IEM_ASOS_TMPF_1F"
SERIES_TENTH_F = "IEM_ASOS_TMPF_0.1F"
#: Kept and still mapped at the settlement boundary, but NEVER written for new rows:
#: every label already stored under it was built from type 3 only, and those rows
#: stay where they are — nothing is overwritten. New Celsius rows carry the series
#: below, whose name says what it is built from.
SERIES_1C = "IEM_ASOS_METAR_1C"
SERIES_1C_RT34 = "IEM_ASOS_METAR_1C_RT34"

STATION_SERIES = {
    **{s: (SERIES_1F, "F", 1.0) for s in
       ("KATL", "KAUS", "KDAL", "KHOU", "KLAX", "KLGA", "KMIA", "KORD", "KSEA", "KSFO")},
    "KBKF": (SERIES_TENTH_F, "F", 0.1),
}
DEFAULT_SERIES = (SERIES_1C_RT34, "C", 1.0)

#: The report types each series is fetched with. A series NAME is a promise about its
#: contents, so the types live with the name and not inside the fetcher: a series
#: missing from this map raises instead of silently falling back to some default.
SERIES_REPORT_TYPES = {
    SERIES_1C: REPORT_TYPES_ROUTINE,
    SERIES_1C_RT34: REPORT_TYPES_ALL,
    SERIES_1F: REPORT_TYPES_ROUTINE,
    SERIES_TENTH_F: REPORT_TYPES_ROUTINE,
}


#: THE `source` OF A ROW CARRIES ITS QUERY, because the primary key has no series.
#:
#: `weather_observations` is keyed on (station, source, observation_time,
#: dataset_version, record_version), and `store.py` replays on the same key. An old
#: type-3 label and a new 3+4 label whose highs fall on the SAME instant — a peak at
#: :50, which both series see — share every one of those columns, and the upsert
#: (`ON CONFLICT DO UPDATE`) replaced the old row with the new one. Measured, not
#: argued: one row left, carrying the new series. That is an overwrite, and labels
#: are never overwritten.
#:
#: So rows built from types 3+4 carry their own source name, and the two coexist in
#: the table and in the store. Not an invented label: `source` is the provenance,
#: and which report types were asked for is part of it. Rejected alternatives:
#: putting `series` in the key (a schema and store migration) and bumping
#: `record_version` (which means a METAR correction, D17-C).
SERIES_SOURCE = {
    SERIES_1C_RT34: "IEM_ASOS_METAR_RT34",
}


def source_for(series: str) -> str:
    """The `source` a row of this series is written under (see `SERIES_SOURCE`)."""
    return SERIES_SOURCE.get(series, SOURCE)


def station_series(station: str) -> tuple[str, str, float]:
    """(series, unit, resolution) for a station. Celsius at 1 degree by default."""
    return STATION_SERIES.get((station or "").upper(), DEFAULT_SERIES)


def report_types(station: str) -> tuple[int, ...]:
    """The IEM report types the station's current series is built from."""
    return SERIES_REPORT_TYPES[station_series(station)[0]]


def detect_grid(station: str, tmax_c: float, tmax_f: float) -> tuple[str, float, str]:
    """(unit, value on the native grid, series).

    Returns UNKNOWN rather than guessing when the value does not sit on the
    station's declared grid: a settlement computed off its own grid is worse than
    one that refuses to compute.
    """
    series, unit, res = station_series(station)
    raw = tmax_f if unit == "F" else tmax_c
    snapped = round(raw / res) * res
    # Compare on the VALUE scale, not the step scale. Dividing by a 0.1 resolution
    # multiplies the floating-point error tenfold, which made KBKF's 78.4 F — an
    # exact tenth — miss an epsilon set for whole degrees. The tolerance belongs
    # where the quantity lives.
    if abs(raw - snapped) < _GRID_TOL:
        return unit, round(snapped, 6), series
    return "UNKNOWN", tmax_c, series


@dataclass(frozen=True)
class DailyHigh:
    station: str
    target_date: date
    tmax_c: float
    when_utc: datetime
    n_obs: int
    tmax_f: float | None = None


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:  # pragma: no cover - depends on the install
        return ssl.create_default_context()


def f_to_c(f: float) -> float:
    """Fahrenheit to Celsius. The only place this conversion happens."""
    return (f - 32.0) * 5.0 / 9.0


def fetch_metar(
    icao: str, start: datetime, end: datetime, timeout: int = 90,
    types: tuple[int, ...] | None = None,
) -> list[tuple[datetime, float]]:
    """METAR temperatures in [start, end], as (UTC instant, °C).

    From the report types the station's series is built from (`report_types`) unless
    `types` says otherwise — never a single global constant, see `REPORT_TYPES_ALL`."""
    types = report_types(icao) if types is None else tuple(types)
    if not types:
        raise ValueError("fetch_metar needs at least one IEM report type")
    s, e = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    # IEM's day2 is EXCLUSIVE when it differs from day1 (measured: day1=20,
    # day2=21 returns only the 20th), yet day1=day2 returns that whole day. Rather
    # than depend on that quirk, ask for one day past what is needed and filter by
    # timestamp below — the filter is exact regardless of how the server reads the
    # range.
    e_query = e + timedelta(days=1)
    # A LIST OF PAIRS, not a dict: IEM takes one `report_type` parameter PER TYPE, and
    # a dict can hold the key only once.
    q = urllib.parse.urlencode(
        [
            ("station", icao.upper()),
            ("data", "tmpf"),
            ("year1", s.year), ("month1", s.month), ("day1", s.day),
            ("year2", e_query.year), ("month2", e_query.month), ("day2", e_query.day),
            ("tz", "Etc/UTC"),
            ("format", "onlycomma"),
            ("missing", "empty"),
            ("trace", "empty"),
            ("latlon", "no"),
            ("direct", "no"),
        ]
        + [("report_type", t) for t in types]
    )
    # IEM is intermittently slow and returns 503 under load. Those are transient
    # and worth a bounded retry. A 429 is NOT: a rate limit is an instruction,
    # and retrying past it is exactly what gate D0 forbids.
    body = None
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    f"{IEM_ASOS}?{q}", headers={"User-Agent": "pmw-agent/2b"}
                ),
                timeout=timeout,
                context=_ssl_context(),
            ) as r:
                body = r.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise ObservationError(
                    f"IEM rate limited for {icao} (HTTP 429); not retried"
                ) from exc
            if exc.code < 500:
                raise ObservationError(
                    f"IEM rejected {icao}: HTTP {exc.code}"
                ) from exc
            last = exc
        except Exception as exc:  # noqa: BLE001 - retried below, surfaced if terminal
            last = exc
        if attempt < RETRIES - 1:
            time.sleep(RETRY_BACKOFF_S * (attempt + 1))
    if body is None:
        raise ObservationError(f"IEM fetch failed for {icao}: {last!r}")

    out: list[tuple[datetime, float]] = []
    for row in csv.DictReader(io.StringIO(body)):
        raw = (row.get("tmpf") or "").strip()
        if not raw:
            continue
        try:
            t = datetime.strptime(row["valid"], "%Y-%m-%d %H:%M").replace(
                tzinfo=timezone.utc
            )
            out.append((t, f_to_c(float(raw))))
        except (KeyError, ValueError):
            continue  # a malformed row is skipped, never guessed at
    out.sort(key=lambda x: x[0])
    return out


def daily_high(icao: str, target_date: date, tz: str, fetcher=fetch_metar) -> DailyHigh:
    """The highest METAR temperature over the station-LOCAL target day.

    Over every report type the station's series is built from (`report_types`): at a
    half-hourly Celsius station that is the :20 reports as well as the :50 ones, and
    leaving either out makes the high low whenever the peak lands on it (B-131).

    The window is the same one the forecast uses (`weather.target_day_window`), so
    forecast and observation describe the same day — mismatching them would make
    every error measurement wrong by a timezone.

    Fails closed: raises `NoObservation` if the day has no reports at all, and if
    it is missing any of the peak local hours, since a partial day yields a lower
    maximum indistinguishable from a genuinely cool day.
    """
    start, end = weather.target_day_window(target_date, tz)
    obs = fetcher(icao, start - timedelta(hours=2), end + timedelta(hours=2))
    zone = ZoneInfo(tz)
    inside = [(t, v) for t, v in obs if start <= t < end]
    if not inside:
        raise NoObservation(f"no METAR for {icao} on {target_date} ({tz})")
    covered = {t.astimezone(zone).hour for t, _ in inside}
    missing = sorted(set(weather.PEAK_LOCAL_HOURS) - covered)
    if missing:
        raise NoObservation(
            f"{icao} {target_date}: missing local hours {missing}; a partial day "
            "cannot give the daily high"
        )
    when, tmax = max(inside, key=lambda x: x[1])
    return DailyHigh(
        icao.upper(), target_date, tmax, when, len(inside),
        tmax_f=tmax * 9.0 / 5.0 + 32.0,
    )


def _grid(dh: DailyHigh) -> tuple[str, float, str]:
    f = dh.tmax_f if dh.tmax_f is not None else dh.tmax_c * 9.0 / 5.0 + 32.0
    return detect_grid(dh.station, dh.tmax_c, f)


def to_row(dh: DailyHigh, dataset_version: str, fetched_at: datetime | None = None) -> dict:
    now = fetched_at or datetime.now(timezone.utc)
    return {
        # the day's high is the fact; observation_time anchors it to when it occurred
        "observation_time": dh.when_utc.isoformat(),
        "station": dh.station,
        "source": source_for(_grid(dh)[2]),
        "tmax_observed": dh.tmax_c,   # always Celsius, derived
        "observed_unit": _grid(dh)[0],
        "observed_value": _grid(dh)[1],
        "series": _grid(dh)[2],
        "daily_high_time": dh.when_utc.isoformat(),
        # true by construction, and fail-closed: see the module docstring
        "available_at": now.isoformat(),
        "fetched_at": now.isoformat(),
        "source_timestamp": dh.when_utc.isoformat(),
        "ingestion_timestamp": now.isoformat(),
        "dataset_version": dataset_version,
        "record_version": 1,
    }


def ingest_daily_high(
    con,
    icao: str,
    target_date: date,
    tz: str,
    dataset_version: str,
    fetcher=fetch_metar,
) -> DailyHigh:
    """Fetch and upsert one station-day. Idempotent on the natural key."""
    dh = daily_high(icao, target_date, tz, fetcher=fetcher)
    db.upsert(
        con,
        "weather_observations",
        to_row(dh, dataset_version),
        conflict_cols=("station", "source", "observation_time", "dataset_version", "record_version"),
    )
    return dh


def observed_tmax(
    con, station: str, target_date: date, tz: str, dataset_version: str | None = None
) -> float:
    """The realized daily high for a station-day, in °C. Raises if absent.

    This is a LABEL. It must never be read as a feature: `build_feature` does not
    touch this table, and `available_at` makes the as-of engine refuse it anyway.
    """
    start, end = weather.target_day_window(target_date, tz)
    where = "station = ? AND observation_time >= ? AND observation_time < ?"
    params: list[Any] = [station.upper(), start.isoformat(), end.isoformat()]
    if dataset_version is not None:
        where += " AND dataset_version = ?"
        params.append(dataset_version)
    # THE STATION'S CURRENT SERIES FIRST, then the latest revision. Corrected labels
    # land BESIDE the superseded ones (`SERIES_SOURCE`), so a station-day can hold
    # both, and `record_version` alone picks between them arbitrarily — both are
    # version 1 — which returns the type-3 label on a day it is 1 C low. Every other
    # reader (`m2`, `labels`, `label_bias_pnl`, settlement) aggregates with MAX and is
    # already safe; this is the one that picks a single row.
    rows = db.query(
        con,
        f"SELECT tmax_observed FROM weather_observations WHERE {where} "
        "ORDER BY (series = ?) DESC, record_version DESC LIMIT 1",
        params + [station_series(station)[0]],
    )
    if not rows:
        raise NoObservation(f"no observed high for {station} on {target_date}")
    return float(rows[0]["tmax_observed"])
