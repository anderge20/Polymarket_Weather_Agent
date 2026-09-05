"""Historical CLOB price ingestion.

``/prices-history`` supplies indicative historical price points, not fills.  This
module deliberately has no order-book or trade fallback: historical L2 is not
available and an unavailable CLOB point must remain unavailable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .. import database as db
from ..config import CLOB

MAX_WINDOW_SECONDS = 48 * 60 * 60
SOURCE = "clob /prices-history"

S_OK = "OK"
S_EMPTY = "EMPTY"
S_RATE_LIMITED = "RATE_LIMITED"
S_HTTP_ERROR = "HTTP_ERROR"
S_TIMEOUT = "TIMEOUT"
S_NETWORK = "NETWORK_ERROR"
S_PARSE = "PARSE_ERROR"
ERROR_STATUSES = (S_RATE_LIMITED, S_HTTP_ERROR, S_TIMEOUT, S_NETWORK, S_PARSE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _windows(start_ts: int, end_ts: int) -> Iterable[tuple[int, int]]:
    """Yield adjacent request windows no longer than 48 hours.

    We intentionally retain identical boundaries.  The CLOB API excludes request
    endpoints, and a point at a shared boundary is therefore not duplicated by
    this convention.
    """
    if end_ts <= start_ts:
        raise ValueError("end_ts must be after start_ts")
    cursor = start_ts
    while cursor < end_ts:
        nxt = min(cursor + MAX_WINDOW_SECONDS, end_ts)
        yield cursor, nxt
        cursor = nxt


def fetch_window(session: Any, token_id: str, start_ts: int, end_ts: int,
                 *, timeout: int = 30) -> tuple[str, list[dict[str, Any]]]:
    """Fetch one CLOB window once; callers must stop, not hammer, on a 429."""
    try:
        response = session.get(
            f"{CLOB}/prices-history",
            params={"market": token_id, "startTs": start_ts, "endTs": end_ts,
                    "fidelity": 1},
            timeout=timeout,
        )
    except Exception as exc:
        # Import requests lazily and avoid making it an import-time dependency.
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
            if not (start_ts < ts < end_ts) or not (0.0 <= price <= 1.0):
                return S_PARSE, []
            points.append({"t": ts, "p": price})
    except (TypeError, ValueError):
        return S_PARSE, []
    return (S_OK if points else S_EMPTY), points


def fetch_history(session: Any, token_id: str, start_ts: int, end_ts: int,
                  *, timeout: int = 30) -> tuple[str, list[dict[str, Any]]]:
    """Fetch and stitch a complete interval, without writing partial histories."""
    by_timestamp: dict[int, float] = {}
    for left, right in _windows(start_ts, end_ts):
        status, points = fetch_window(session, token_id, left, right, timeout=timeout)
        if status in ERROR_STATUSES:
            return status, []
        for point in points:
            old = by_timestamp.get(point["t"])
            if old is not None and old != point["p"]:
                return S_PARSE, []
            by_timestamp[point["t"]] = point["p"]
    return (S_OK if by_timestamp else S_EMPTY), [
        {"t": ts, "p": by_timestamp[ts]} for ts in sorted(by_timestamp)
    ]


def ingest_history(con: Any, session: Any, *, market_id: str, token_id: str,
                   start_ts: int, end_ts: int, dataset_version: str,
                   timeout: int = 30) -> dict[str, Any]:
    """Atomically persist one complete, directly observed indicative history.

    Network failures and 429s leave the database untouched.  Re-ingesting the
    same source points is idempotent on the table's natural primary key.
    """
    status, points = fetch_history(session, token_id, start_ts, end_ts, timeout=timeout)
    summary = {"market_id": market_id, "token_id": token_id, "status": status,
               "points_written": 0, "start_ts": start_ts, "end_ts": end_ts}
    if status in ERROR_STATUSES:
        return summary
    fetched_at = _now()
    try:
        con.execute("BEGIN TRANSACTION")
        for point in points:
            observation_time = datetime.fromtimestamp(point["t"], timezone.utc).isoformat()
            db.upsert(con, "price_history", {
                "observation_time": observation_time,
                "market_id": market_id,
                "token_id": token_id,
                "indicative_price": point["p"],
                "price_semantics": "MIDPOINT_ESTIMATED",
                "price_source": "CLOB_PRICES_HISTORY",
                "fidelity": 1,
                "source_window": "DIRECT",
                "fetched_at": fetched_at,
                "source": SOURCE,
                "source_timestamp": observation_time,
                "ingestion_timestamp": fetched_at,
                "dataset_version": dataset_version,
                "record_version": 1,
            }, ["token_id", "observation_time", "dataset_version", "record_version"])
            summary["points_written"] += 1
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return summary
