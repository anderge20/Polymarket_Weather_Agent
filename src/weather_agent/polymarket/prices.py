"""
prices.py — CLOB historical price ingestion  (Phase 2B)
=======================================================

Fills `price_history` with the **indicative** price series of a market's outcome
token, from the Polymarket CLOB `prices-history` endpoint, and provides the as-of
read the backtest and the live loop both use.

`/prices-history` supplies indicative points, not fills. This module deliberately
has no order-book or trade fallback: historical L2 does not exist, and a point
that was not observable must stay unobservable.

CONTRACT (frozen; tests/test_market_asof.py enforces it)
---------------------------------------------------------
* INDICATIVE, never executable. Every row is written with
  `price_semantics = 'MIDPOINT_ESTIMATED'`; the 2A CHECK makes 'EXECUTABLE'
  unrepresentable. Downstream must never treat it as a fill price.
* As-of reads use `observation_time`. The price for a decision at T is the last
  point at or before T — never a later one, never a forward-fill from elsewhere.
* `fidelity=1` and windows of at most `MAX_WINDOW_HOURS`, stitched. The endpoint
  coarsens wide ranges, which would fabricate a resolution we never had.
* **A 429 stops the walk. It is never retried.** Rate limits are respected, not
  worked around (self-imposed gate D0).
* **All-or-nothing per market.** The whole interval is fetched before anything is
  written, and the write runs in one transaction. A network failure mid-walk
  leaves no partial history that a later run would mistake for a complete one.
* If two windows report **different prices for the same instant**, that is a
  contradiction in the source and the ingest refuses rather than silently
  picking one.
* Idempotent on the natural key.

RANGE SEMANTICS (measured twice; the first measurement was wrong)
------------------------------------------------------------------
The endpoint's range is `[startTs, endTs]` — **both ends inclusive**.

First measurement (2026-09-06) confirmed the start is inclusive and inferred the
end was exclusive, from a request that happened to have no point exactly at
`endTs`. Absence of a boundary point is not evidence of exclusion. On
2026-09-08 a market (Dallas/KDAL, target 2026-04-08) returned a point at exactly
`endTs`, and the end-exclusive check threw away all **2 862** legitimate points
of that window as PARSE_ERROR. Silent, total data loss for that market from one
boundary point.

Windows therefore overlap by one instant at each boundary. The stitcher keys by
timestamp so the repeat collapses, and a genuine disagreement at that instant is
still caught as a contradiction rather than resolved silently.

Provenance: this module is the reconciliation of two independent implementations
— Codex's (transport discipline: status taxonomy, no-hammer 429, atomic write,
cross-window conflict detection) and Claude's (tz-aware API, as-of read, docs).
Codex's boundary validation rejected `t == startTs`; the measurement above fixes it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Iterator

from .. import database as db
from ..config import CLOB

#: The endpoint's native resolution, in minutes.
NATIVE_FIDELITY_MIN = 1

#: Longest range requested in a single call.
MAX_WINDOW_HOURS = 48
MAX_WINDOW_SECONDS = MAX_WINDOW_HOURS * 60 * 60

PRICE_SEMANTICS = "MIDPOINT_ESTIMATED"
PRICE_SOURCE = "CLOB_PRICES_HISTORY"
SOURCE = "clob /prices-history"
SOURCE_WINDOW_DIRECT = "DIRECT"

# Transport outcomes. Returned, not raised: a caller walking thousands of markets
# needs to distinguish "stop now" (rate limited) from "skip this one" (parse) and
# from "nothing here" (empty).
S_OK = "OK"
S_EMPTY = "EMPTY"
S_RATE_LIMITED = "RATE_LIMITED"
S_HTTP_ERROR = "HTTP_ERROR"
S_TIMEOUT = "TIMEOUT"
S_NETWORK = "NETWORK_ERROR"
S_PARSE = "PARSE_ERROR"
ERROR_STATUSES = (S_RATE_LIMITED, S_HTTP_ERROR, S_TIMEOUT, S_NETWORK, S_PARSE)

#: The one status that must stop a batch walk rather than skip an item.
STOP_STATUSES = (S_RATE_LIMITED,)


class NoPriceAsOf(LookupError):
    """No indicative price exists at or before the requested instant."""


@dataclass(frozen=True)
class PricePoint:
    """One indicative observation. `t` is market-time, tz-aware UTC."""

    t: datetime
    p: float


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("naive datetime rejected: as-of logic requires tz-aware UTC")
    return ts.astimezone(timezone.utc)


def default_session():
    """A plain `requests` session. `requests` bundles its own CA store, which is
    what keeps this working on Python builds without a wired-up system trust store."""
    import requests

    return requests.Session()


# ---------------------------------------------------------------------------
# windowing
# ---------------------------------------------------------------------------


def windows(start_ts: int, end_ts: int) -> Iterator[tuple[int, int]]:
    """Adjacent request windows of at most `MAX_WINDOW_SECONDS`, in unix seconds.

    Windows share a boundary instant. The endpoint's range is `[start, end]`, so
    a point exactly on the boundary is returned by BOTH adjacent windows; the
    stitcher keys by timestamp, which collapses the repeat while still catching a
    genuine disagreement as a contradiction.
    """
    if end_ts <= start_ts:
        raise ValueError("end_ts must be after start_ts")
    cursor = start_ts
    while cursor < end_ts:
        nxt = min(cursor + MAX_WINDOW_SECONDS, end_ts)
        yield cursor, nxt
        cursor = nxt


def windows_dt(
    start: datetime, end: datetime
) -> Iterator[tuple[datetime, datetime]]:
    """`windows` in tz-aware datetimes, for callers working in wall-clock terms."""
    for a, b in windows(int(_to_utc(start).timestamp()), int(_to_utc(end).timestamp())):
        yield (
            datetime.fromtimestamp(a, timezone.utc),
            datetime.fromtimestamp(b, timezone.utc),
        )


# ---------------------------------------------------------------------------
# fetching
# ---------------------------------------------------------------------------


def fetch_window(
    session: Any,
    token_id: str,
    start_ts: int,
    end_ts: int,
    *,
    fidelity: int = NATIVE_FIDELITY_MIN,
    timeout: int = 30,
) -> tuple[str, list[dict[str, Any]]]:
    """One `prices-history` call, attempted ONCE.

    A 429 returns `S_RATE_LIMITED` and the caller must stop; it is never retried
    here. Any point outside `[start_ts, end_ts]` or outside `[0,1]` makes the
    whole window `S_PARSE` — a source that answers outside what was asked is not
    understood, and guessing which points to keep would be inventing data.
    """
    if fidelity < 1:
        raise ValueError("fidelity must be >= 1 minute")
    try:
        response = session.get(
            f"{CLOB}/prices-history",
            params={
                "market": token_id,
                "startTs": start_ts,
                "endTs": end_ts,
                "fidelity": fidelity,
            },
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 - classified below, re-raised if unknown
        try:
            import requests

            if isinstance(exc, requests.Timeout):
                return S_TIMEOUT, []
            if isinstance(exc, requests.RequestException):
                return S_NETWORK, []
        except ImportError:
            pass
        raise
    if response.status_code == 429:
        return S_RATE_LIMITED, []
    if response.status_code != 200:
        return S_HTTP_ERROR, []
    try:
        payload = response.json()
        history = payload.get("history") if isinstance(payload, dict) else None
        if not isinstance(history, list):
            return S_PARSE, []
        points: list[dict[str, Any]] = []
        for point in history:
            if not isinstance(point, dict) or "t" not in point or "p" not in point:
                return S_PARSE, []
            ts, price = int(point["t"]), float(point["p"])
            # measured: the range is [start, end] — BOTH ends inclusive
            if not (start_ts <= ts <= end_ts) or not (0.0 <= price <= 1.0):
                return S_PARSE, []
            points.append({"t": ts, "p": price})
    except (TypeError, ValueError):
        return S_PARSE, []
    return (S_OK if points else S_EMPTY), points


def fetch_history(
    session: Any,
    token_id: str,
    start_ts: int,
    end_ts: int,
    *,
    fidelity: int = NATIVE_FIDELITY_MIN,
    timeout: int = 30,
) -> tuple[str, list[dict[str, Any]]]:
    """Fetch and stitch a whole interval. Returns nothing at all on any error, so
    a partial history is never mistaken for a complete one."""
    by_timestamp: dict[int, float] = {}
    for left, right in windows(start_ts, end_ts):
        status, points = fetch_window(
            session, token_id, left, right, fidelity=fidelity, timeout=timeout
        )
        if status in ERROR_STATUSES:
            return status, []
        for point in points:
            previous = by_timestamp.get(point["t"])
            if previous is not None and previous != point["p"]:
                # the source contradicts itself; refuse rather than pick one
                return S_PARSE, []
            by_timestamp[point["t"]] = point["p"]
    return (S_OK if by_timestamp else S_EMPTY), [
        {"t": ts, "p": by_timestamp[ts]} for ts in sorted(by_timestamp)
    ]


# ---------------------------------------------------------------------------
# ingestion
# ---------------------------------------------------------------------------


def ingest_history(
    con: Any,
    session: Any,
    *,
    market_id: str,
    token_id: str,
    start_ts: int,
    end_ts: int,
    dataset_version: str,
    fidelity: int = NATIVE_FIDELITY_MIN,
    timeout: int = 30,
) -> dict[str, Any]:
    """Persist one complete, directly observed indicative history, atomically.

    Network failures and 429s leave the database untouched. Re-ingesting the same
    points is idempotent on the table's natural key.
    """
    status, points = fetch_history(
        session, token_id, start_ts, end_ts, fidelity=fidelity, timeout=timeout
    )
    summary: dict[str, Any] = {
        "market_id": market_id,
        "token_id": token_id,
        "status": status,
        "points_written": 0,
        "start_ts": start_ts,
        "end_ts": end_ts,
    }
    if status in ERROR_STATUSES:
        return summary
    fetched_at = _now()
    try:
        con.execute("BEGIN TRANSACTION")
        for point in points:
            observation_time = datetime.fromtimestamp(
                point["t"], timezone.utc
            ).isoformat()
            db.upsert(
                con,
                "price_history",
                {
                    "observation_time": observation_time,
                    "market_id": market_id,
                    "token_id": token_id,
                    "indicative_price": point["p"],
                    "price_semantics": PRICE_SEMANTICS,
                    "price_source": PRICE_SOURCE,
                    "fidelity": fidelity,
                    "source_window": SOURCE_WINDOW_DIRECT,
                    "fetched_at": fetched_at,
                    "source": SOURCE,
                    "source_timestamp": observation_time,
                    "ingestion_timestamp": fetched_at,
                    "dataset_version": dataset_version,
                    "record_version": 1,
                },
                ["token_id", "observation_time", "dataset_version", "record_version"],
            )
            summary["points_written"] += 1
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return summary


def ingest(
    con,
    session: Any,
    token_id: str,
    market_id: str,
    start: datetime,
    end: datetime,
    dataset_version: str,
    fidelity: int = NATIVE_FIDELITY_MIN,
) -> dict[str, Any]:
    """`ingest_history` in tz-aware wall-clock terms."""
    return ingest_history(
        con,
        session,
        market_id=market_id,
        token_id=token_id,
        start_ts=int(_to_utc(start).timestamp()),
        end_ts=int(_to_utc(end).timestamp()),
        dataset_version=dataset_version,
        fidelity=fidelity,
    )


# ---------------------------------------------------------------------------
# as-of read
# ---------------------------------------------------------------------------


def price_asof(
    con, token_id: str, asof: datetime, dataset_version: str | None = None
) -> dict:
    """The last indicative price at or before `asof` for `token_id`.

    Fails closed: raises `NoPriceAsOf` rather than returning a later point, a
    stale value from another token, or a default.
    """
    where = "token_id = ?"
    params: list[Any] = [token_id]
    if dataset_version is not None:
        where += " AND dataset_version = ?"
        params.append(dataset_version)
    rows = db.latest_asof(
        con,
        "price_history",
        asof=_to_utc(asof).isoformat(),
        partition_cols=["token_id"],
        where=where,
        params=params,
    )
    if not rows:
        raise NoPriceAsOf(
            f"no indicative price at or before {asof.isoformat()} for {token_id}"
        )
    return rows[0]
