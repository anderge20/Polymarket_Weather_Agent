"""
prices.py — CLOB historical price ingestion  (Phase 2B)
=======================================================

Fills `price_history` with the **indicative** price series of a market's outcome
token, from the Polymarket CLOB `prices-history` endpoint.

CONTRACT (frozen; the tests in tests/test_market_asof.py enforce it)
--------------------------------------------------------------------
* The series is INDICATIVE, never executable. `prices-history` returns a
  midpoint-derived series: there is no guarantee any of these prices was
  fillable, and no size is attached. Every row is written with
  `price_semantics = 'MIDPOINT_ESTIMATED'` and the 2A CHECK constraint makes
  'EXECUTABLE' unrepresentable. Downstream must never treat it as a fill price.
* As-of reads use `observation_time` (market-time of the point). The price used
  for a decision at T is `latest_asof(price_history, asof=T, partition=[token_id])`
  — the last point at or before T, never a later one.
* `fidelity=1` (1-minute native resolution) and windows of at most
  `MAX_WINDOW_HOURS`, stitched. The endpoint silently coarsens or truncates long
  ranges, which would fabricate a resolution we never had.
* `source_window` records whether a point came straight from a request whose
  range covered it (`DIRECT`) — the only kind this module writes. `DERIVED` is
  reserved for points reconstructed by other means; this module never invents one.
* Idempotent: re-running over the same range upserts on the natural key and adds
  no duplicates.
* Fails CLOSED: `price_asof()` raises `NoPriceAsOf` when no point exists at or
  before the requested instant. A missing price is never silently a zero, a
  forward-filled stale value, or the next point after T.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Iterator, Sequence

from .. import database as db

CLOB_PRICES_HISTORY = "https://clob.polymarket.com/prices-history"

#: The endpoint's native resolution, in minutes. Anything coarser is a different
#: quantity and must not be written as if it were the native series.
NATIVE_FIDELITY_MIN = 1

#: Longest range requested in a single call. The endpoint degrades resolution for
#: wide ranges; stitching keeps every point at native fidelity.
MAX_WINDOW_HOURS = 48

PRICE_SEMANTICS = "MIDPOINT_ESTIMATED"
PRICE_SOURCE = "CLOB_PRICES_HISTORY"
SOURCE_WINDOW_DIRECT = "DIRECT"

_UA = {"User-Agent": "pmw-agent/2b (+research)"}
_CTX = ssl.create_default_context()


class PriceIngestError(RuntimeError):
    """Transport or protocol failure while fetching a price window."""


class NoPriceAsOf(LookupError):
    """No indicative price exists at or before the requested instant."""


@dataclass(frozen=True)
class PricePoint:
    """One indicative observation. `t` is market-time, tz-aware UTC."""

    t: datetime
    p: float


# ---------------------------------------------------------------------------
# fetching
# ---------------------------------------------------------------------------


def _to_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("naive datetime rejected: as-of logic requires tz-aware UTC")
    return ts.astimezone(timezone.utc)


def windows(
    start: datetime, end: datetime, max_hours: int = MAX_WINDOW_HOURS
) -> Iterator[tuple[datetime, datetime]]:
    """Split [start, end] into consecutive ranges of at most `max_hours`.

    Ranges are half-open going forward but the endpoint is inclusive on both
    ends, so consecutive windows overlap by one instant; de-duplication on the
    natural key removes the repeat.
    """
    start, end = _to_utc(start), _to_utc(end)
    if end < start:
        raise ValueError("end precedes start")
    step = timedelta(hours=max_hours)
    cur = start
    while cur < end:
        nxt = min(cur + step, end)
        yield cur, nxt
        cur = nxt


def fetch_window(
    token_id: str,
    start: datetime,
    end: datetime,
    fidelity: int = NATIVE_FIDELITY_MIN,
    retries: int = 4,
    timeout: int = 60,
) -> list[PricePoint]:
    """One `prices-history` call. Returns the points it reports, in time order."""
    if fidelity < 1:
        raise ValueError("fidelity must be >= 1 minute")
    q = urllib.parse.urlencode(
        {
            "market": token_id,
            "startTs": int(_to_utc(start).timestamp()),
            "endTs": int(_to_utc(end).timestamp()),
            "fidelity": fidelity,
        }
    )
    url = f"{CLOB_PRICES_HISTORY}?{q}"
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                payload = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            # 4xx other than rate-limiting will not fix themselves.
            if e.code not in (429, 500, 502, 503, 504):
                raise PriceIngestError(f"HTTP {e.code} for token {token_id}") from e
            last = e
        except Exception as e:  # noqa: BLE001 - retried below, re-raised if terminal
            last = e
        if attempt == retries - 1:
            raise PriceIngestError(f"giving up on {token_id}: {last!r}")
        time.sleep(1.5 * (attempt + 1))

    hist = payload.get("history")
    if hist is None:
        raise PriceIngestError(f"no 'history' key in response for {token_id}")
    out: list[PricePoint] = []
    for pt in hist:
        try:
            t = datetime.fromtimestamp(int(pt["t"]), tz=timezone.utc)
            p = float(pt["p"])
        except (KeyError, TypeError, ValueError) as e:
            raise PriceIngestError(f"malformed point {pt!r} for {token_id}") from e
        if not 0.0 <= p <= 1.0:
            raise PriceIngestError(f"price {p} out of [0,1] for {token_id} at {t}")
        out.append(PricePoint(t, p))
    out.sort(key=lambda x: x.t)
    return out


def fetch_series(
    token_id: str,
    start: datetime,
    end: datetime,
    fidelity: int = NATIVE_FIDELITY_MIN,
    fetcher=fetch_window,
) -> list[PricePoint]:
    """Stitch consecutive windows into one de-duplicated, time-ordered series."""
    seen: dict[datetime, PricePoint] = {}
    for w_start, w_end in windows(start, end):
        for pt in fetcher(token_id, w_start, w_end, fidelity):
            seen[pt.t] = pt
    return [seen[t] for t in sorted(seen)]


# ---------------------------------------------------------------------------
# ingestion
# ---------------------------------------------------------------------------


def to_rows(
    token_id: str,
    market_id: str,
    points: Iterable[PricePoint],
    dataset_version: str,
    fidelity: int = NATIVE_FIDELITY_MIN,
    fetched_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Map points onto `price_history` rows, with provenance."""
    now = (fetched_at or datetime.now(timezone.utc)).isoformat()
    return [
        {
            "observation_time": pt.t.isoformat(),
            "market_id": market_id,
            "token_id": token_id,
            "indicative_price": pt.p,
            "price_semantics": PRICE_SEMANTICS,
            "price_source": PRICE_SOURCE,
            "fidelity": fidelity,
            "source_window": SOURCE_WINDOW_DIRECT,
            "fetched_at": now,
            "source": PRICE_SOURCE,
            "source_timestamp": pt.t.isoformat(),
            "ingestion_timestamp": now,
            "dataset_version": dataset_version,
            "record_version": 1,
        }
        for pt in points
    ]


def ingest(
    con,
    token_id: str,
    market_id: str,
    start: datetime,
    end: datetime,
    dataset_version: str,
    fidelity: int = NATIVE_FIDELITY_MIN,
    fetcher=fetch_window,
) -> int:
    """Fetch [start, end] and upsert it. Returns the number of points written.

    Idempotent: the natural key is (token_id, observation_time, dataset_version,
    record_version), so re-running the same range rewrites the same rows.
    """
    points = fetch_series(token_id, start, end, fidelity, fetcher=fetcher)
    rows = to_rows(token_id, market_id, points, dataset_version, fidelity)
    for row in rows:
        db.upsert(
            con,
            "price_history",
            row,
            conflict_cols=(
                "token_id",
                "observation_time",
                "dataset_version",
                "record_version",
            ),
        )
    return len(rows)


# ---------------------------------------------------------------------------
# as-of read
# ---------------------------------------------------------------------------


def price_asof(con, token_id: str, asof: datetime, dataset_version: str | None = None) -> dict:
    """The last indicative price at or before `asof` for `token_id`.

    Fails closed: raises `NoPriceAsOf` rather than returning a later point, a
    stale forward-fill from another token, or a default.
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
        raise NoPriceAsOf(f"no indicative price at or before {asof.isoformat()} for {token_id}")
    return rows[0]
