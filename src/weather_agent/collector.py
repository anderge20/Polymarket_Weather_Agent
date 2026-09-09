"""
weather_agent.collector — forward-only market-data collector (R22)
==================================================================
STATUS: IMPLEMENTED + TESTED (tests/test_collector.py, offline fixtures).
The live endpoints below were exercised READ-ONLY on 2026-09-09 (see §Endpoints).

WHY POLLING AND NOT A WEBSOCKET
-------------------------------
`config.CLOB_WS_URL` is still None/UNVERIFIED and this module does NOT try to
verify it, because the question is moot for the host the user chose. A-29.2 fixes
the paper-mode host as GitHub Actions: every run is an ephemeral container on a
cron trigger, so there is no process that can hold a socket open between runs.
A websocket collector would have to be rewritten the day it moved hosts.

R22 therefore takes its documented alternative — **polling policy ADOPTED** — and
the policy is: batch REST snapshots of the CLOB book, one cycle per invocation.
This is a consequence of the user's host decision, not a workaround for a
technical failure, and `CLOB_WS_URL` stays UNVERIFIED rather than being guessed.

ENDPOINTS (verified live 2026-09-09, read-only GET/POST, no auth, no wallet)
---------------------------------------------------------------------------
  * POST {CLOB}/books   body=[{"token_id": "..."}, ...]  -> list of book objects.
    OBSERVED: returns one object per requested token; no API key; no signature.
    This is the batching primitive — one request covers a whole band set.
  * GET  {CLOB}/book?token_id=...                        -> one book object.
    Kept as the single-token fallback and for parity checks.
  * GET  {DATA_API}/trades?market=<conditionId>&limit=   -> executed trades.
    OBSERVED: public; rows carry proxyWallet/side/asset/size/price/timestamp/
    transactionHash. There is NO server-side trade id, so we derive a
    deterministic one (see `trade_fingerprint`).

  Book object shape (OBSERVED):
      {"market": "0x..", "asset_id": "1151..", "timestamp": "1788937456569",
       "hash": "37a93746..", "bids": [{"price": "0.001", "size": "42.92"}, ...],
       "asks": [{"price": "0.999", "size": "8015"}, ...]}
  `timestamp` is the exchange's milliseconds-since-epoch, NOT our clock, and it
  advances on every poll even when the book is byte-identical (`hash` does not).

  ORDERING IS NOT ASSUMED. In the 2026-09-09 sample `asks` came back DESCENDING
  by price, so the best (lowest) ask was the LAST element — the opposite of the
  obvious reading. Every function here re-sorts explicitly and takes best_bid =
  max(bid prices) / best_ask = min(ask prices). Never index [0].

EXPLICIT DEFINITIONS for the 2A columns this module fills (the schema names them
but does not define them; these definitions are the contract):
  * bid_depth_k / ask_depth_k = total size summed over the k BEST price levels on
    that side (k = 1, 5, 10). Levels, not cents. Fewer than k levels -> the sum of
    what exists (not NULL); an empty side -> 0.0.
  * mid    = (best_bid + best_ask) / 2, NULL if either side is empty.
  * spread = best_ask - best_bid, NULL if either side is empty.
  * imbalance = (bid_depth_10 - ask_depth_10) / (bid_depth_10 + ask_depth_10),
    NULL when the denominator is 0. Range [-1, +1]; positive = bid-heavy.

SESSIONS AND RESUMPTION (R22 "test de reanudación de sesión")
-------------------------------------------------------------
A *cycle* is one collection pass over a token universe, identified by
`collector_session_id`. Rows carry it, so resumption needs no extra table and no
checkpoint file: on restart, `tokens_pending()` reads back the token_ids already
written under that session id and returns only the remainder. An Actions run that
is cancelled halfway (or hits the 6 h job cap) resumes exactly where it stopped
when the next run passes the same session id.

QUOTA: a 429 or any HTTP error STOPS the cycle and is recorded in the summary.
Nothing here retries to get around a rate limit (standing user constraint).

NO CREDENTIALS: this module reads public endpoints only. It never signs, never
places an order, and imports nothing that could.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from . import config
from . import database as db

CLOB_BOOK_URL = f"{config.CLOB}/book"
CLOB_BOOKS_URL = f"{config.CLOB}/books"
DATA_TRADES_URL = f"{config.DATA_API}/trades"

SOURCE_BOOK = "clob_books_poll"
SOURCE_TRADES = "data_api_trades"

#: Depth levels materialised into the *_depth_1 / *_depth_5 / *_depth_10 columns.
DEPTH_LEVELS: tuple[int, ...] = (1, 5, 10)

#: Tokens per POST /books request. Conservative: one weather event's band set is
#: typically < 20 tokens, so a cycle over a day's universe is a handful of calls.
DEFAULT_CHUNK_SIZE = 50

#: Politeness delay between chunk requests (seconds). Not a rate-limit bypass —
#: it exists to stay well under any limit, never to retry through one.
DEFAULT_CHUNK_DELAY_S = 0.5

#: Price levels per side kept inside `book_snapshot`. A live book carries ~50-70
#: ask levels (~2 KB of JSON per token per poll); at paper-mode polling rates that
#: is ~10 MB/day, which the git-backed store of A-29.2 cannot carry for a month.
#: 10 is not an arbitrary trim: it is exactly what has consumers — the deepest
#: *_depth_k column and the paper fill simulator, whose position cap cannot reach
#: past a handful of levels. Truncation is ALWAYS detectable, never silent: the
#: payload records the true level counts and a `truncated` flag, so a fill that
#: exhausts the stored book can be told apart from one that exhausted the market.
DEFAULT_KEEP_LEVELS = 10


# --------------------------------------------------------------------------- time
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime) -> str:
    return ts.isoformat()


def new_session_id(*, prefix: str = "col", now: datetime | None = None) -> str:
    """Mint a collector session (cycle) id: `col_YYYYMMDDTHHMMSSZ_<6 hex>`.

    Callers that want a *resumable* cycle must persist and re-pass the id (the
    Actions runner derives it from the cron slot, so a retried run resumes rather
    than starting a second cycle)."""
    stamp = (now or _utcnow()).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:6]}"


# --------------------------------------------------------------------------- book maths
def _levels(side: Any) -> list[tuple[float, float]]:
    """Parse one book side into [(price, size)], dropping unparseable entries.

    Prices/sizes arrive as STRINGS from the CLOB; a silently-coerced NaN would
    poison every downstream aggregate, so anything that does not parse as a finite
    number is dropped rather than defaulted."""
    out: list[tuple[float, float]] = []
    for lvl in side or []:
        if not isinstance(lvl, dict):
            continue
        try:
            price = float(lvl["price"])
            size = float(lvl["size"])
        except (KeyError, TypeError, ValueError):
            continue
        if price != price or size != size:      # NaN
            continue
        out.append((price, size))
    return out


def _depth(levels: Sequence[tuple[float, float]], k: int) -> float:
    """Total size over the k best levels (already sorted best-first)."""
    return float(sum(size for _price, size in levels[:k]))


def book_top(book: dict) -> dict:
    """Reduce a raw CLOB book to the `orderbook_snapshots` measure columns.

    Returns best_bid/best_ask/mid/spread, the six depth columns, imbalance, and
    the book's own `hash`/`timestamp` (exchange clock, kept as evidence). Every
    field is NULL-able: an empty or one-sided book is a legitimate observation,
    not an error, and is recorded as such."""
    bids = sorted(_levels(book.get("bids")), key=lambda lv: -lv[0])   # best = highest
    asks = sorted(_levels(book.get("asks")), key=lambda lv: lv[0])    # best = lowest

    best_bid = bids[0][0] if bids else None
    best_ask = asks[0][0] if asks else None
    mid = (best_bid + best_ask) / 2.0 if (best_bid is not None and best_ask is not None) else None
    spread = (best_ask - best_bid) if (best_bid is not None and best_ask is not None) else None

    depths = {f"bid_depth_{k}": _depth(bids, k) for k in DEPTH_LEVELS}
    depths.update({f"ask_depth_{k}": _depth(asks, k) for k in DEPTH_LEVELS})

    deepest = max(DEPTH_LEVELS)
    b, a = depths[f"bid_depth_{deepest}"], depths[f"ask_depth_{deepest}"]
    imbalance = ((b - a) / (b + a)) if (b + a) > 0 else None

    exch_ts = book.get("timestamp")
    try:
        exch_ms = int(exch_ts) if exch_ts is not None else None
    except (TypeError, ValueError):
        exch_ms = None

    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
        "spread": spread,
        "imbalance": imbalance,
        "book_hash": book.get("hash"),
        "exchange_timestamp_ms": exch_ms,
        "n_bid_levels": len(bids),
        "n_ask_levels": len(asks),
        **depths,
    }


def book_snapshot_row(
    book: dict,
    *,
    collected_at: datetime,
    collector_session_id: str,
    collector_started_at: datetime,
    dataset_version: str,
    market_id: str | None = None,
    keep_levels: int = DEFAULT_KEEP_LEVELS,
) -> dict:
    """Build one `orderbook_snapshots` row from a raw book object.

    `timestamp` (the PK component) is OUR observation instant, not the exchange's:
    the exchange clock advances on every poll even for an unchanged book, so using
    it as the key would make identical polls look like distinct market states. The
    exchange value is preserved inside `book_snapshot` as evidence.

    The stored ladder is the `keep_levels` BEST levels per side, sorted best-first
    (so a consumer never has to re-derive the ordering). The measure columns above
    are computed from the FULL book before truncation."""
    top = book_top(book)
    token_id = str(book.get("asset_id") or "")
    bids = sorted(_levels(book.get("bids")), key=lambda lv: -lv[0])[:keep_levels]
    asks = sorted(_levels(book.get("asks")), key=lambda lv: lv[0])[:keep_levels]
    payload = {
        "hash": top["book_hash"],
        "exchange_timestamp_ms": top["exchange_timestamp_ms"],
        "n_bid_levels": top["n_bid_levels"],      # true counts, pre-truncation
        "n_ask_levels": top["n_ask_levels"],
        "kept_levels": keep_levels,
        "truncated": (top["n_bid_levels"] > keep_levels
                      or top["n_ask_levels"] > keep_levels),
        "bids": [{"price": p, "size": s} for p, s in bids],
        "asks": [{"price": p, "size": s} for p, s in asks],
    }
    return {
        "timestamp": _iso(collected_at),
        "market_id": market_id if market_id is not None else book.get("market"),
        "token_id": token_id,
        "best_bid": top["best_bid"],
        "best_ask": top["best_ask"],
        "mid": top["mid"],
        "spread": top["spread"],
        "bid_depth_1": top["bid_depth_1"],
        "bid_depth_5": top["bid_depth_5"],
        "bid_depth_10": top["bid_depth_10"],
        "ask_depth_1": top["ask_depth_1"],
        "ask_depth_5": top["ask_depth_5"],
        "ask_depth_10": top["ask_depth_10"],
        "imbalance": top["imbalance"],
        "book_snapshot": payload,
        "collected_at": _iso(collected_at),
        "collector_session_id": collector_session_id,
        "collector_started_at": _iso(collector_started_at),
        "source": SOURCE_BOOK,
        "source_timestamp": _iso(collected_at),
        "ingestion_timestamp": _iso(_utcnow()),
        "dataset_version": dataset_version,
        "record_version": 1,
    }


# --------------------------------------------------------------------------- trades
def trade_fingerprint(trade: dict) -> str:
    """Deterministic id for a Data-API trade row.

    The endpoint exposes no trade id, and `transactionHash` is NOT unique (one
    transaction can settle several fills). The fingerprint hashes the tuple that
    identifies a fill, so re-fetching the same trade collapses onto the same PK
    (idempotent) while two genuinely distinct fills in one transaction stay
    distinct."""
    key = json.dumps(
        {
            "tx": trade.get("transactionHash"),
            "asset": trade.get("asset"),
            "wallet": trade.get("proxyWallet"),
            "side": trade.get("side"),
            "size": trade.get("size"),
            "price": trade.get("price"),
            "ts": trade.get("timestamp"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "tr_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:24]


def trade_row(
    trade: dict,
    *,
    fetched_at: datetime,
    collector_session_id: str,
    collector_started_at: datetime,
    dataset_version: str,
) -> dict | None:
    """Build one `trades` row. Returns None when the payload lacks a usable
    timestamp or side (fail-closed: an unparseable trade is dropped and counted,
    never coerced into a plausible-looking row)."""
    ts = trade.get("timestamp")
    try:
        when = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (TypeError, ValueError):
        return None
    side = trade.get("side")
    if side not in ("BUY", "SELL"):
        return None
    try:
        price = float(trade["price"])
        size = float(trade["size"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "timestamp": _iso(when),
        "market_id": trade.get("conditionId"),
        "token_id": str(trade.get("asset") or ""),
        "price": price,
        "size": size,
        "side": side,
        "trade_id": trade_fingerprint(trade),
        "fetched_at": _iso(fetched_at),
        "collected_at": _iso(fetched_at),
        "collector_session_id": collector_session_id,
        "collector_started_at": _iso(collector_started_at),
        "source": SOURCE_TRADES,
        "source_timestamp": _iso(when),
        "ingestion_timestamp": _iso(_utcnow()),
        "dataset_version": dataset_version,
        "record_version": 1,
    }


# --------------------------------------------------------------------------- HTTP
class CollectorStopped(Exception):
    """Raised internally when the cycle must stop (rate limit / transport error)."""


def _chunks(seq: Sequence[str], n: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_books(
    session,
    token_ids: Sequence[str],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    timeout: int = 30,
    delay_s: float = DEFAULT_CHUNK_DELAY_S,
    sleep=time.sleep,
) -> dict:
    """POST {CLOB}/books in chunks. Returns
    {'books': [...], 'requests': n, 'stopped': bool, 'error': str|None}.

    STOP-ON-ERROR, never retry-through: an HTTP 429 (or any non-200, or a
    transport exception) ends the cycle and is reported. Whatever was already
    fetched is returned so the caller can persist it and resume later."""
    books: list[dict] = []
    requests_made = 0
    for i, chunk in enumerate(_chunks(list(token_ids), max(1, chunk_size))):
        if i and delay_s:
            sleep(delay_s)
        payload = [{"token_id": str(t)} for t in chunk]
        try:
            resp = session.post(CLOB_BOOKS_URL, json=payload, timeout=timeout)
        except Exception as exc:                      # transport-level failure
            return {"books": books, "requests": requests_made,
                    "stopped": True, "error": f"transport: {exc!r}"}
        requests_made += 1
        status = getattr(resp, "status_code", None)
        if status == 429:
            return {"books": books, "requests": requests_made,
                    "stopped": True, "error": "http_429_rate_limited"}
        if status != 200:
            return {"books": books, "requests": requests_made,
                    "stopped": True, "error": f"http_{status}"}
        try:
            data = resp.json()
        except Exception as exc:
            return {"books": books, "requests": requests_made,
                    "stopped": True, "error": f"bad_json: {exc!r}"}
        if isinstance(data, dict):                    # single-object tolerance
            data = [data]
        if not isinstance(data, list):
            return {"books": books, "requests": requests_made,
                    "stopped": True, "error": "unexpected_payload_shape"}
        books.extend(b for b in data if isinstance(b, dict))
    return {"books": books, "requests": requests_made, "stopped": False, "error": None}


def fetch_trades(
    session,
    condition_id: str,
    *,
    limit: int = 500,
    timeout: int = 30,
) -> dict:
    """GET {DATA_API}/trades for one market. Same stop-on-error contract."""
    try:
        resp = session.get(
            DATA_TRADES_URL, params={"market": condition_id, "limit": limit},
            timeout=timeout,
        )
    except Exception as exc:
        return {"trades": [], "stopped": True, "error": f"transport: {exc!r}"}
    status = getattr(resp, "status_code", None)
    if status == 429:
        return {"trades": [], "stopped": True, "error": "http_429_rate_limited"}
    if status != 200:
        return {"trades": [], "stopped": True, "error": f"http_{status}"}
    try:
        data = resp.json()
    except Exception as exc:
        return {"trades": [], "stopped": True, "error": f"bad_json: {exc!r}"}
    if not isinstance(data, list):
        return {"trades": [], "stopped": True, "error": "unexpected_payload_shape"}
    return {"trades": [t for t in data if isinstance(t, dict)], "stopped": False, "error": None}


# --------------------------------------------------------------------------- resumption
def tokens_collected(con, *, collector_session_id: str, dataset_version: str) -> set[str]:
    """Token ids already persisted under this cycle."""
    rows = db.query(
        con,
        "SELECT DISTINCT token_id FROM orderbook_snapshots "
        "WHERE collector_session_id = ? AND dataset_version = ?",
        [collector_session_id, dataset_version],
    )
    return {str(r["token_id"]) for r in rows if r.get("token_id") is not None}


def tokens_pending(
    con, token_ids: Sequence[str], *, collector_session_id: str, dataset_version: str
) -> list[str]:
    """The tokens of this cycle that are NOT yet persisted, order preserved.

    This is the whole resumption mechanism: no checkpoint file, no extra table.
    Re-running a cycle with the same session id is a no-op once complete."""
    done = tokens_collected(
        con, collector_session_id=collector_session_id, dataset_version=dataset_version
    )
    seen: set[str] = set()
    pending: list[str] = []
    for t in token_ids:
        t = str(t)
        if t in done or t in seen:
            continue
        seen.add(t)
        pending.append(t)
    return pending


# --------------------------------------------------------------------------- cycles
def collect_books(
    con,
    token_ids: Sequence[str],
    *,
    dataset_version: str,
    collector_session_id: str,
    collector_started_at: datetime | None = None,
    session=None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    timeout: int = 30,
    delay_s: float = DEFAULT_CHUNK_DELAY_S,
    market_id_by_token: dict[str, str] | None = None,
    keep_levels: int = DEFAULT_KEEP_LEVELS,
    resume: bool = True,
) -> dict:
    """Run ONE collection cycle over `token_ids` and persist `orderbook_snapshots`.

    Idempotent and resumable: with `resume=True` (default) tokens already stored
    under `collector_session_id` are skipped, so a cancelled Actions run finishes
    on the next invocation of the same cycle."""
    started = collector_started_at or _utcnow()
    pending = (
        tokens_pending(con, token_ids, collector_session_id=collector_session_id,
                       dataset_version=dataset_version)
        if resume else [str(t) for t in token_ids]
    )
    summary = {
        "collector_session_id": collector_session_id,
        "collector_started_at": _iso(started),
        "dataset_version": dataset_version,
        "tokens_requested": len(list(token_ids)),
        "tokens_pending": len(pending),
        "books_received": 0,
        "rows_written": 0,
        "requests": 0,
        "stopped": False,
        "error": None,
    }
    if not pending:
        return summary

    if session is None:
        import requests
        session = requests.Session()

    res = fetch_books(session, pending, chunk_size=chunk_size, timeout=timeout,
                      delay_s=delay_s)
    summary["requests"] = res["requests"]
    summary["stopped"] = res["stopped"]
    summary["error"] = res["error"]
    summary["books_received"] = len(res["books"])

    collected_at = _utcnow()
    for book in res["books"]:
        token = str(book.get("asset_id") or "")
        if not token:
            continue
        row = book_snapshot_row(
            book,
            collected_at=collected_at,
            collector_session_id=collector_session_id,
            collector_started_at=started,
            dataset_version=dataset_version,
            market_id=(market_id_by_token or {}).get(token),
            keep_levels=keep_levels,
        )
        db.upsert(con, "orderbook_snapshots", row,
                  ["token_id", "timestamp", "dataset_version", "record_version"])
        summary["rows_written"] += 1
    return summary


def collect_trades(
    con,
    condition_ids: Sequence[str],
    *,
    dataset_version: str,
    collector_session_id: str,
    collector_started_at: datetime | None = None,
    session=None,
    limit: int = 500,
    timeout: int = 30,
    delay_s: float = DEFAULT_CHUNK_DELAY_S,
    sleep=time.sleep,
) -> dict:
    """Collect executed trades for each condition id. Forward-only by nature:
    the endpoint returns the most recent trades, and our store keeps whatever we
    have observed, never claiming completeness of history."""
    started = collector_started_at or _utcnow()
    summary = {
        "collector_session_id": collector_session_id,
        "markets_requested": len(list(condition_ids)),
        "markets_done": 0,
        "trades_received": 0,
        "rows_written": 0,
        "rows_dropped": 0,
        "stopped": False,
        "error": None,
    }
    if session is None:
        import requests
        session = requests.Session()

    for i, cid in enumerate(condition_ids):
        if i and delay_s:
            sleep(delay_s)
        res = fetch_trades(session, str(cid), limit=limit, timeout=timeout)
        if res["stopped"]:
            summary["stopped"] = True
            summary["error"] = res["error"]
            break
        summary["markets_done"] += 1
        fetched_at = _utcnow()
        for tr in res["trades"]:
            summary["trades_received"] += 1
            row = trade_row(tr, fetched_at=fetched_at,
                            collector_session_id=collector_session_id,
                            collector_started_at=started,
                            dataset_version=dataset_version)
            if row is None:
                summary["rows_dropped"] += 1
                continue
            db.upsert(con, "trades", row,
                      ["trade_id", "dataset_version", "record_version"])
            summary["rows_written"] += 1
    return summary
