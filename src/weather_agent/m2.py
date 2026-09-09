"""
m2.py — assembling the M2 training set from the database
========================================================

The pairing and lead-derivation rules of `PREREG_M2_ERROR_v2.md`, promoted out of
`scripts/fit_m2.py` because R17, R19 and the paper cycle's forecast stage all need
them. Leaving them in a script would have meant a second implementation
somewhere, which is how two `prices.py` nearly shipped.

`error_model.py` deliberately stays database-free: it is the estimator and can be
tested without a schema. This module is the part that knows about tables.

The three rules that make the training set correct, all verified the hard way:

  * pair on the station's LOCAL day. `CAST(observation_time AS DATE)` made the
    sample size depend on the DuckDB session TimeZone — 2 599 rows under UTC,
    1 881 under Asia/Shanghai;
  * derive the lead by reproducing the run selection, never from "hours between
    issue and endDate", which collapsed every pair onto lead 24 and silently
    pooled the two leads the preregistration says are never mixed;
  * a label is available at end of local day + 24 h. Filtering on
    `target_date < D` instead leaked in 8 of 8 stations, by -9 h to -43 h.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import database as db
from . import error_model as em
from . import stations, weather

DATASET_VERSION = "backfill_2b_v1"
PREREG_SHA_V2 = "b2b168d4cddb65c469cbd00bd20cce30c54e5afd194526527714e23cf0d5b34c"
LEADS = (9, 24)


def local_day(ts, tz_name: str):
    """v2 §1: the station's LOCAL day. `observation_time::date` is forbidden."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(ZoneInfo(tz_name)).date()


def label_available_at(target_day, tz_name: str) -> datetime:
    """v2 §3: end of the local day, plus the assumed 24 h publication lag."""
    zone = ZoneInfo(tz_name)
    end_local = datetime(
        target_day.year, target_day.month, target_day.day, tzinfo=zone
    ) + timedelta(days=1)
    return end_local.astimezone(timezone.utc) + em.ASSUMED_LABEL_LAG


def pick_run(t: datetime, model: str, issue_hours=(0, 6, 12, 18), max_age_h=36):
    cursor = t.replace(minute=0, second=0, microsecond=0)
    limit = t - timedelta(hours=max_age_h)
    while cursor >= limit:
        if cursor.hour in issue_hours and weather.is_available_at(cursor, model, t):
            return cursor
        cursor -= timedelta(hours=1)
    return None


def load_pairs(con):
    """(pairs, issue_by_key, stats). Pairing by LOCAL day, in Python — the SQL
    join on `CAST(observation_time AS DATE)` is what made the sample depend on a
    session variable."""
    obs = db.query(
        con,
        """SELECT station, observation_time, tmax_observed FROM weather_observations
           WHERE dataset_version = ?""",
        [DATASET_VERSION],
    )
    by_local_day: dict[tuple, float] = {}
    no_tz = 0
    for r in obs:
        try:
            tz = stations.timezone_of(r["station"])
        except stations.UnknownStation:
            no_tz += 1
            continue
        key = (r["station"], local_day(r["observation_time"], tz))
        v = float(r["tmax_observed"])
        by_local_day[key] = max(by_local_day.get(key, v), v)

    fc = db.query(
        con,
        """SELECT station, target_date, issue_time, forecast_tmax
           FROM weather_forecasts
           WHERE dataset_version = ? AND forecast_tmax IS NOT NULL""",
        [DATASET_VERSION],
    )
    pairs: list[em.Pair] = []
    issue_by_key: dict[tuple, object] = {}
    unmatched_lead = unmatched_obs = 0
    for r in fc:
        td = r["target_date"]
        td = td.date() if hasattr(td, "date") else td
        try:
            tz = stations.timezone_of(r["station"])
        except stations.UnknownStation:
            continue
        y = by_local_day.get((r["station"], td))
        if y is None:
            unmatched_obs += 1
            continue
        issue = r["issue_time"]
        if issue.tzinfo is None:
            issue = issue.replace(tzinfo=timezone.utc)
        end = datetime(td.year, td.month, td.day, 12, tzinfo=timezone.utc)
        lead = None
        for cand in LEADS:
            run = pick_run(end - timedelta(hours=cand), weather.M1_MODEL)
            if run is not None and run == issue:
                lead = cand
                break
        if lead is None:
            unmatched_lead += 1  # v2 §2: counted, never assigned to a plausible lead
            continue
        issue_by_key[(r["station"], td, lead)] = r["issue_time"]
        pairs.append(
            em.Pair(
                station=r["station"],
                target_date=td,
                lead_h=lead,
                forecast_c=float(r["forecast_tmax"]),
                observed_c=y,
                label_available_at=label_available_at(td, tz),
            )
        )
    stats = {
        "obs_sin_huso": no_tz,
        "pronosticos_sin_observacion": unmatched_obs,
        "filas_sin_lead_preregistrado": unmatched_lead,
    }
    return pairs, issue_by_key, stats


