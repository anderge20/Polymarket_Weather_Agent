"""
weather.py — forecast ingestion, as-of correct  (Phase 2B)
==========================================================

Fills `weather_forecasts` with the daily high forecast for a station and target
date, from a specific model run, and exposes the as-of read the feature join
needs.

THE ONE RULE THAT MATTERS: `available_at`
------------------------------------------
A forecast run is stamped with `issue_time` (the run's init time) but it is not
*knowable* then — it has to be computed and published. The as-of anchor is
therefore

    available_at(run) = issue_time(run) + L_MAX[model]

with `L_MAX` the **maximum** publication latency observed per model, not the
median: fail-closed. Values from the F-3 availability audit (n=307 passes, 20
dates, Jun-Sep 2026), preregistered in `PREREG_MODELSEL_ASOF_V2.md` §2.

`issue_time <= T` is NEVER used as an availability test anywhere. Neither is
`ingestion_timestamp`: when *we* happened to fetch a row says nothing about when
the world could have known it, and using it would leak our own scheduling into
history.

REGISTERED WARNING (from the same audit): L_MAX is an empirical bound over 307
observations and the maximum *grew* when the sample went from 20 to 307 — the
tail is not characterised. Treat these as lower bounds on the true worst case.

LATENCY IS NOT EQUALISED BETWEEN MODELS. Preregistered in V2 §2: *"la publicación
más rápida es una ventaja operativa real y forma parte de la comparación"*. ICON
publishes ~4 h faster than ECMWF, so at a 24 h lead ICON offers a 6 h-old run
where ECMWF can only offer a 12 h-old one. That is a genuine product property,
not a confound to neutralise — and equalising it would mean reading a run that
did not exist at decision time (see `MODELSEL_V5_CORRECTION_01.md`).

MODEL: M1 = `icon_seamless`, adopted in D12 after MODELSEL V5.
"""

from __future__ import annotations

import json
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
from . import stations

SINGLE_RUNS_API = "https://single-runs-api.open-meteo.com/v1/forecast"

#: Maximum observed publication latency, in hours, per model (F-3 audit; fail-closed).
L_MAX_HOURS: dict[str, float] = {
    "icon_seamless": 4.76,
    "gfs_seamless": 6.93,
    "ecmwf_ifs025": 8.78,
    "ukmo_global_deterministic_10km": 10.48,
}

#: M1, adopted in D12 (MODELSEL V5, category B + the §17 freshness tie-break).
M1_MODEL = "icon_seamless"

_UA = {"User-Agent": "pmw-agent/2b (+research)"}


def _ssl_context() -> ssl.SSLContext:
    """Prefer certifi's CA bundle.

    Python installs from python.org on macOS ship without the system trust store
    wired up, so the default context fails every HTTPS call with
    CERTIFICATE_VERIFY_FAILED. certifi arrives with `requests` (see
    requirements-pipeline.txt) and is what the research scripts used.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:  # pragma: no cover - depends on the install
        return ssl.create_default_context()


_CTX = _ssl_context()


class WeatherIngestError(RuntimeError):
    """Transport or protocol failure while fetching a forecast run."""


class NoForecastAsOf(LookupError):
    """No forecast for this (station, model, target_date) was available at T."""


class UnknownModelLatency(KeyError):
    """No measured publication latency for this model: availability is undefined."""


@dataclass(frozen=True)
class Forecast:
    station: str
    model: str
    issue_time: datetime
    target_date: date
    tmax: float
    available_at: datetime
    n_hours: int


# ---------------------------------------------------------------------------
# availability
# ---------------------------------------------------------------------------


def available_at(issue_time: datetime, model: str) -> datetime:
    """When `model`'s run could first be relied upon. Fail-closed (max latency)."""
    if issue_time.tzinfo is None:
        raise ValueError("naive datetime rejected: as-of logic requires tz-aware UTC")
    try:
        lag = L_MAX_HOURS[model]
    except KeyError as e:
        raise UnknownModelLatency(
            f"no measured publication latency for {model!r}; availability cannot be "
            "assumed — measure it before ingesting this model"
        ) from e
    return issue_time.astimezone(timezone.utc) + timedelta(hours=lag)


def is_available_at(issue_time: datetime, model: str, t: datetime) -> bool:
    """Was this run knowable at `t`?"""
    return available_at(issue_time, model) <= t.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# the target-day window
# ---------------------------------------------------------------------------


def target_day_window(target_date: date, tz: str) -> tuple[datetime, datetime]:
    """The station-local calendar day of `target_date`, as a UTC half-open range.

    The market resolves on the day's high *at the station*, so the window is the
    local day — not a UTC day, and not a fixed offset. Both are wrong for any
    station away from Greenwich.
    """
    zone = ZoneInfo(tz)
    start_local = datetime(target_date.year, target_date.month, target_date.day, tzinfo=zone)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


#: Local hours the run must cover for a daily high to be meaningful. Maxima
#: essentially always fall inside this band; a run that misses part of the local
#: night still gives the right high, one that misses the afternoon does not.
PEAK_LOCAL_HOURS = range(11, 19)


def tmax_from_series(
    series: dict[str, float], target_date: date, tz: str
) -> tuple[float, int]:
    """The daily high over the local target day, and how many hours backed it.

    Returns (tmax, n_hours). A run need not cover the whole local day — a 06z run
    legitimately starts after the local night — but it MUST cover the hours where
    the high actually occurs. A window missing the afternoon silently yields a
    lower maximum that is indistinguishable from a genuine forecast, so that case
    raises instead.
    """
    start, end = target_day_window(target_date, tz)
    zone = ZoneInfo(tz)
    vals: list[float] = []
    covered_local: set[int] = set()
    for ts, v in series.items():
        if v is None:
            continue
        t = datetime.fromisoformat(ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if start <= t < end:
            vals.append(float(v))
            covered_local.add(t.astimezone(zone).hour)
    if not vals:
        raise WeatherIngestError(
            f"run does not cover the local day of {target_date} in {tz}: no hours in window"
        )
    missing = sorted(set(PEAK_LOCAL_HOURS) - covered_local)
    if missing:
        raise WeatherIngestError(
            f"run misses local hours {missing} of {target_date} in {tz}; the daily high "
            "cannot be read from a window that omits the afternoon"
        )
    return max(vals), len(vals)


# ---------------------------------------------------------------------------
# fetching
# ---------------------------------------------------------------------------


def fetch_run(
    lat: float,
    lon: float,
    model: str,
    issue_time: datetime,
    retries: int = 4,
    timeout: int = 90,
) -> dict[str, Any]:
    """One Single-Runs call. Returns {'cell_lat','cell_lon','elevation','series'}."""
    q = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m",
            "models": model,
            "run": issue_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M"),
            "timezone": "UTC",
        }
    )
    url = f"{SINGLE_RUNS_API}?{q}"
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=_UA), timeout=timeout, context=_CTX
            ) as r:
                d = json.loads(r.read())
            if d.get("error"):
                raise WeatherIngestError(f"API error: {d.get('reason')}")
            h = d["hourly"]
            return {
                "cell_lat": d["latitude"],
                "cell_lon": d["longitude"],
                "elevation": d.get("elevation"),
                "series": dict(zip(h["time"], h["temperature_2m"])),
            }
        except urllib.error.HTTPError as e:
            if e.code == 400:
                # 400 covers several distinct conditions — a point outside the
                # model's domain, a run the archive no longer holds, a malformed
                # parameter. Reporting one of them as if it were another sends
                # the reader chasing the wrong problem, so quote the API's own
                # reason instead of guessing.
                try:
                    reason = json.loads(e.read()).get("reason", "")
                except Exception:  # noqa: BLE001 - diagnostics must not mask the error
                    reason = ""
                raise WeatherIngestError(
                    f"{model} rejected at ({lat},{lon}) run {issue_time:%Y-%m-%dT%H:%MZ}"
                    + (f": {reason}" if reason else " (HTTP 400, no reason given)")
                ) from e
            if e.code == 429:
                raise WeatherIngestError("daily quota exhausted (HTTP 429)") from e
            last = e
        except Exception as e:  # noqa: BLE001 - retried below, re-raised if terminal
            last = e
        if attempt == retries - 1:
            raise WeatherIngestError(f"giving up on {model} @ {issue_time}: {last!r}")
        time.sleep(1.5 * (attempt + 1))
    raise AssertionError("unreachable")


# ---------------------------------------------------------------------------
# ingestion
# ---------------------------------------------------------------------------


def build_forecast(
    icao: str,
    model: str,
    issue_time: datetime,
    target_date: date,
    tz: str,
    series: dict[str, float],
) -> Forecast:
    tmax, n = tmax_from_series(series, target_date, tz)
    return Forecast(
        station=icao.upper(),
        model=model,
        issue_time=issue_time.astimezone(timezone.utc),
        target_date=target_date,
        tmax=tmax,
        available_at=available_at(issue_time, model),
        n_hours=n,
    )


def to_row(fc: Forecast, dataset_version: str, fetched_at: datetime | None = None) -> dict:
    now = (fetched_at or datetime.now(timezone.utc)).isoformat()
    return {
        "issue_time": fc.issue_time.isoformat(),
        "forecast_run": fc.issue_time.strftime("%Hz"),
        "target_date": fc.target_date.isoformat(),
        "station": fc.station,
        "model": fc.model,
        "forecast_tmax": fc.tmax,
        "available_at": fc.available_at.isoformat(),
        "fetched_at": now,
        "source": "OPEN_METEO_SINGLE_RUNS",
        "source_timestamp": fc.issue_time.isoformat(),
        "ingestion_timestamp": now,
        "dataset_version": dataset_version,
        "record_version": 1,
    }


def ingest_run(
    con,
    icao: str,
    target_date: date,
    tz: str,
    issue_time: datetime,
    dataset_version: str,
    model: str = M1_MODEL,
    fetcher=fetch_run,
) -> Forecast:
    """Fetch one run for one station/target-date and upsert it. Idempotent."""
    st = stations.get(icao)
    got = fetcher(st.lat, st.lon, model, issue_time)
    fc = build_forecast(icao, model, issue_time, target_date, tz, got["series"])
    db.upsert(
        con,
        "weather_forecasts",
        to_row(fc, dataset_version),
        conflict_cols=(
            "station",
            "model",
            "issue_time",
            "target_date",
            "dataset_version",
            "record_version",
        ),
    )
    return fc


# ---------------------------------------------------------------------------
# as-of read
# ---------------------------------------------------------------------------


def forecast_asof(
    con,
    station: str,
    target_date: date,
    asof: datetime,
    model: str = M1_MODEL,
    dataset_version: str | None = None,
) -> dict:
    """The latest forecast for (station, model, target_date) knowable at `asof`.

    Filters on `available_at`, never on `issue_time` or `ingestion_timestamp`.
    Fails closed: raises rather than reaching for a run that was not out yet.
    """
    where = "station = ? AND model = ? AND target_date = ?"
    params: list[Any] = [station.upper(), model, target_date.isoformat()]
    if dataset_version is not None:
        where += " AND dataset_version = ?"
        params.append(dataset_version)
    rows = db.latest_asof(
        con,
        "weather_forecasts",
        asof=asof.astimezone(timezone.utc).isoformat(),
        partition_cols=["station", "model", "target_date"],
        where=where,
        params=params,
    )
    if not rows:
        raise NoForecastAsOf(
            f"no {model} forecast for {station} / {target_date} available at "
            f"{asof.isoformat()}"
        )
    return rows[0]
