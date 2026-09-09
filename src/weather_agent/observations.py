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
station-days change the maximum); for Wunderground — the contractual source of
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

#: METAR routine reports only (report_type=3). Specials (SPECI) are excluded so
#: the series is the regular hourly record the climate summaries are built from.
REPORT_TYPE = 3


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


def _is_int(x: float) -> bool:
    return abs(x - round(x)) < _EPS


#: Stations whose METAR series is on a whole-FAHRENHEIT grid, measured over the
#: 2026-04..09 sample: their Celsius values carry fractional parts of exactly n/9.
#: Every other station reports whole Celsius. KBKF mixes both and is left UNKNOWN
#: rather than forced — it is also the station D6 could not verify against HOMR.
#:
#: A per-VALUE test cannot decide this: every multiple of 5 C is a whole number of
#: Fahrenheit too (20 C = 68 F), so it would label a Celsius-grid station like EHAM
#: as Fahrenheit one day in five. The grid is a property of the STATION's series.
FAHRENHEIT_GRID_STATIONS = frozenset(
    {"KATL", "KAUS", "KDAL", "KHOU", "KLAX", "KLGA", "KMIA", "KORD", "KSEA", "KSFO"}
)
MIXED_GRID_STATIONS = frozenset({"KBKF"})


def detect_grid(station: str, tmax_c: float, tmax_f: float) -> tuple[str, float]:
    """(unit, value) on the STATION's native grid.

    Returns UNKNOWN rather than guessing when the station's grid is not known or
    the value does not sit on it: a settlement computed off its own grid is worse
    than one that refuses to compute.
    """
    st = (station or "").upper()
    if st in FAHRENHEIT_GRID_STATIONS:
        return ("F", float(round(tmax_f))) if _is_int(tmax_f) else ("UNKNOWN", tmax_c)
    if st in MIXED_GRID_STATIONS:
        return "UNKNOWN", tmax_c
    return ("C", float(round(tmax_c))) if _is_int(tmax_c) else ("UNKNOWN", tmax_c)


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
    icao: str, start: datetime, end: datetime, timeout: int = 90
) -> list[tuple[datetime, float]]:
    """Routine METAR temperatures in [start, end], as (UTC instant, °C)."""
    s, e = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    # IEM's day2 is EXCLUSIVE when it differs from day1 (measured: day1=20,
    # day2=21 returns only the 20th), yet day1=day2 returns that whole day. Rather
    # than depend on that quirk, ask for one day past what is needed and filter by
    # timestamp below — the filter is exact regardless of how the server reads the
    # range.
    e_query = e + timedelta(days=1)
    q = urllib.parse.urlencode(
        {
            "station": icao.upper(),
            "data": "tmpf",
            "year1": s.year, "month1": s.month, "day1": s.day,
            "year2": e_query.year, "month2": e_query.month, "day2": e_query.day,
            "tz": "Etc/UTC",
            "format": "onlycomma",
            "missing": "empty",
            "trace": "empty",
            "latlon": "no",
            "direct": "no",
            "report_type": REPORT_TYPE,
        }
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
    """The highest routine METAR temperature over the station-LOCAL target day.

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


def _grid(dh: DailyHigh) -> tuple[str, float]:
    f = dh.tmax_f if dh.tmax_f is not None else dh.tmax_c * 9.0 / 5.0 + 32.0
    return detect_grid(dh.station, dh.tmax_c, f)


def to_row(dh: DailyHigh, dataset_version: str, fetched_at: datetime | None = None) -> dict:
    now = fetched_at or datetime.now(timezone.utc)
    return {
        # the day's high is the fact; observation_time anchors it to when it occurred
        "observation_time": dh.when_utc.isoformat(),
        "station": dh.station,
        "source": SOURCE,
        "tmax_observed": dh.tmax_c,   # always Celsius, derived
        "observed_unit": _grid(dh)[0],
        "observed_value": _grid(dh)[1],
        "series": SERIES,
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
    rows = db.query(
        con,
        f"SELECT tmax_observed FROM weather_observations WHERE {where} "
        "ORDER BY record_version DESC LIMIT 1",
        params,
    )
    if not rows:
        raise NoObservation(f"no observed high for {station} on {target_date}")
    return float(rows[0]["tmax_observed"])
