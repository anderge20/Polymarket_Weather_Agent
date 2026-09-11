"""
weather_agent.store — append-only NDJSON shard store (paper-mode state on Actions)
=================================================================================
STATUS: IMPLEMENTED + TESTED (tests/test_store.py, offline, real files).

THE PROBLEM THIS SOLVES
-----------------------
A-29.2 fixes the paper-mode host as GitHub Actions. An Actions run is an ephemeral
container: the filesystem it writes dies with the job. Paper mode is a process
that must accumulate state for weeks — a book history, signals, an open-position
ledger — so "where does the state live between two cron firings?" is the first
architectural question, not an implementation detail.

The options, and why this one:
  * `actions/cache` — evicted after 7 days of no hits and capped per repo. State
    that can silently vanish is not a ledger. REJECTED.
  * `upload-artifact` — 90-day retention and immutable per run; you cannot append
    to yesterday's artifact, only download N of them and merge. Workable but the
    retention clock deletes evidence, and the standing constraint is never delete
    data. REJECTED as the primary store.
  * an external DB / object store — needs credentials and, in practice, money.
    A-29.1 is explicit that the user does not want to pay. REJECTED.
  * **git, in the repository itself.** Durable, free, already authenticated inside
    Actions via GITHUB_TOKEN, and — the part that actually matters here — it
    timestamps and signs every append. The commit history IS the as-of audit
    trail: "what did the agent know, and when did it know it" becomes a question
    git answers, not one we have to model. ADOPTED.

WHY NDJSON SHARDS AND NOT A COMMITTED DATABASE
----------------------------------------------
A DuckDB file is one binary blob: every append rewrites it, git stores a new copy
each time, and two runs that overlap produce an unmergeable conflict. Shards
invert all three properties:
  * **Append-only.** A run only ever CREATES files named after its own run id. It
    never opens an existing shard for writing.
  * **Conflict-free by construction.** Two concurrent runs write disjoint paths,
    so a git merge is always a fast-forward or a trivial union. There is no
    last-writer-wins case to reason about, which is what makes an unattended cron
    job safe to leave running.
  * **The database becomes derived.** `load_shards()` rebuilds a DuckDB from the
    shards at any commit, so the 546 MB operational DB never enters git and can
    be thrown away and reconstructed. The shards are the source of truth.

LAYOUT
------
    <root>/<table>/<YYYY>/<MM>/<DD>/<table>__<run_id>__<seq>.ndjson[.gz]

Dated directories keep any one directory small (git and editors both degrade with
thousands of siblings) and make retention/inspection by date a path glob.

One JSON object per line, keys = column names. Values are JSON scalars; datetimes
are ISO-8601 strings. Gzip is opt-in per shard (`compress=True`): DuckDB and this
module read either, transparently, by extension.
"""
from __future__ import annotations

import datetime as _dt
import decimal
import gzip
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from . import database as db

#: Default store root, relative to the repo. Overridable with WEATHER_AGENT_STORE_ROOT.
DEFAULT_ROOT = os.environ.get(
    "WEATHER_AGENT_STORE_ROOT",
    str(Path(__file__).resolve().parents[2] / "paper_state"),
)

#: Conflict keys per table, so `load_shards` can re-ingest idempotently. These
#: mirror the PRIMARY KEYs declared in database.py; a table absent from this map
#: must be loaded with an explicit `conflict_cols`.
CONFLICT_COLS: dict[str, tuple[str, ...]] = {
    "orderbook_snapshots": ("token_id", "timestamp", "dataset_version", "record_version"),
    "trades": ("trade_id", "dataset_version", "record_version"),
    "price_history": ("token_id", "observation_time", "dataset_version", "record_version"),
    "markets": ("market_id", "dataset_version", "record_version"),
    "outcomes": ("token_id", "dataset_version", "record_version"),
    "weather_forecasts": ("station", "model", "issue_time", "target_date",
                          "dataset_version", "record_version"),
    "weather_observations": ("station", "source", "observation_time",
                             "dataset_version", "record_version"),
    "signals": ("market_id", "token_id", "strategy", "timestamp",
                "dataset_version", "record_version"),
    "predictions": ("market_id", "token_id", "model_version", "timestamp",
                    "dataset_version", "record_version"),
    "market_fee_schedule": ("fee_regime", "dataset_version", "record_version"),
    "markets_excluded": ("market_id", "reason", "dataset_version"),
    # paper_trades has a surrogate BIGINT key from a sequence. Reloading rows
    # keyed on it is only safe if the sequence is advanced past the highest id
    # restored — see `restore_sequences`, which the load path must call.
    "paper_trades": ("paper_trade_id",),
}

#: Sequence-backed surrogate keys: table -> (sequence, column).
_SEQUENCES: dict[str, tuple[str, str]] = {
    "paper_trades": ("seq_paper_trades", "paper_trade_id"),
}


def restore_sequences(con, *, table: str) -> int | None:
    """Advance a table's surrogate-key sequence past the ids just restored.

    A fresh DuckDB starts every sequence at 1. Rebuild `paper_trades` from shards
    without this and the next inserted position collides with paper_trade_id 1 —
    a primary-key error at best, and a silently overwritten ledger row at worst.

    The sequence is advanced by CONSUMING values, not recreated: DuckDB refuses to
    replace a sequence a table depends on ("Cannot drop entry seq_paper_trades ...
    table paper_trades depends on it"), and dropping it CASCADE would take the
    table with it. `currval` tells us how far it has already been consumed, so the
    whole catch-up is one statement regardless of ledger size.

    Returns the next id the sequence will hand out, or None when the table has no
    sequence."""
    spec = _SEQUENCES.get(table)
    if not spec:
        return None
    seq, col = spec
    row = con.execute(f"SELECT max({db._q(col)}) FROM {db._q(table)}").fetchone()
    top = int(row[0]) if row and row[0] is not None else 0
    try:
        current = int(con.execute(f"SELECT currval('{seq}')").fetchone()[0])
    except Exception:
        current = 0        # never drawn from in this connection
    if top > current:
        con.execute(f"SELECT nextval('{seq}') FROM range({top - current})")
        current = top
    return current + 1

#: Note the absence of '.': the extension is appended by this module, never taken
#: from a caller's string, so a dot in a component has no legitimate use and every
#: illegitimate one ('..') is a traversal attempt. Stripping '/' alone is not
#: enough — it would leave 'run-..-etc' behind, which is harmless today only
#: because nothing joins it back onto a path.
_SAFE = re.compile(r"[^A-Za-z0-9_=-]")
_DASHES = re.compile(r"-{2,}")


def _safe(part: str) -> str:
    """Make a path component filesystem- and git-safe without silently colliding:
    every disallowed character maps to '-', runs collapse, and the result must
    stay non-empty."""
    out = _DASHES.sub("-", _SAFE.sub("-", str(part))).strip("-")
    if not out:
        raise ValueError(f"path component {part!r} is empty after sanitising")
    return out


def _json_default(value: Any) -> Any:
    """Encode the value types DuckDB hands back that json cannot."""
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, _dt.timedelta):
        return value.total_seconds()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"cannot serialise {type(value).__name__} to a shard")


# --------------------------------------------------------------------------- paths
def shard_dir(root: str | os.PathLike, table: str, *, when: _dt.datetime) -> Path:
    return (Path(root) / _safe(table) / f"{when:%Y}" / f"{when:%m}" / f"{when:%d}")


def shard_path(
    root: str | os.PathLike, table: str, *, run_id: str, when: _dt.datetime,
    seq: int = 0, compress: bool = False,
) -> Path:
    ext = ".ndjson.gz" if compress else ".ndjson"
    name = f"{_safe(table)}__{_safe(run_id)}__{seq:04d}{ext}"
    return shard_dir(root, table, when=when) / name


def _write_bytes(path: Path, payload: bytes, compress: bool) -> None:
    """Write one shard. Gzip headers are normalised — mtime=0 AND an empty embedded
    filename — so identical rows produce an identical blob. `GzipFile(filename=...)`
    stamps the path into the header, which would make two shards with the same
    content differ and defeat git's de-duplication."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not compress:
        path.write_bytes(payload)
        return
    with open(path, "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as gz:
            gz.write(payload)


def _open_read(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rb")
    return open(path, "rb")


# --------------------------------------------------------------------------- write
def write_shard(
    rows: Sequence[Mapping[str, Any]],
    *,
    table: str,
    run_id: str,
    root: str | os.PathLike = DEFAULT_ROOT,
    when: _dt.datetime | None = None,
    compress: bool = True,
) -> dict:
    """Write `rows` as ONE new shard. Never appends to an existing file.

    Returns {'path', 'n_rows', 'bytes', 'skipped'}. Writing zero rows creates no
    file (an empty shard would be a commit that says nothing) and reports
    skipped=True. If the target path already exists, the sequence number is
    advanced rather than overwriting — append-only is enforced here, not by
    convention."""
    when = when or _dt.datetime.now(_dt.timezone.utc)
    if not rows:
        return {"path": None, "n_rows": 0, "bytes": 0, "skipped": True}

    seq = 0
    path = shard_path(root, table, run_id=run_id, when=when, seq=seq, compress=compress)
    while path.exists():
        seq += 1
        if seq > 9999:
            raise RuntimeError(f"too many shards for run {run_id!r} on {when:%Y-%m-%d}")
        path = shard_path(root, table, run_id=run_id, when=when, seq=seq,
                          compress=compress)

    payload = b"".join(
        (json.dumps(dict(r), default=_json_default, sort_keys=True,
                    separators=(",", ":")) + "\n").encode("utf-8")
        for r in rows
    )
    _write_bytes(path, payload, compress)
    return {"path": str(path), "n_rows": len(rows), "bytes": path.stat().st_size,
            "skipped": False}


def export_rows(
    con, table: str, *, where: str | None = None, params: Sequence[Any] | None = None,
) -> list[dict]:
    """Read rows out of DuckDB in a JSON-serialisable shape.

    JSON columns come back from DuckDB as strings; they are parsed here so the
    shard carries a real nested object rather than a string containing JSON
    (which would round-trip into a double-encoded value on load)."""
    sql = f"SELECT * FROM {db._q(table)}"
    if where:
        sql += f" WHERE {where}"
    rows = db.query(con, sql, params)
    for row in rows:
        for key, value in list(row.items()):
            if isinstance(value, str) and value[:1] in ("{", "["):
                try:
                    row[key] = json.loads(value)
                except (ValueError, TypeError):
                    pass                      # a genuine string that merely looks like JSON
    return rows


def dump_table(
    con, table: str, *, run_id: str, root: str | os.PathLike = DEFAULT_ROOT,
    where: str | None = None, params: Sequence[Any] | None = None,
    when: _dt.datetime | None = None, compress: bool = True,
) -> dict:
    """Export a table (or a filtered slice of it) into a new shard."""
    rows = export_rows(con, table, where=where, params=params)
    out = write_shard(rows, table=table, run_id=run_id, root=root, when=when,
                      compress=compress)
    out["table"] = table
    return out


# --------------------------------------------------------------------------- read
def iter_shards(
    root: str | os.PathLike = DEFAULT_ROOT, table: str | None = None,
) -> list[Path]:
    """All shard paths, sorted. Sorting is by path, and the layout was chosen so
    that path order == chronological order (zero-padded date parts and seq)."""
    base = Path(root) / _safe(table) if table else Path(root)
    if not base.exists():
        return []
    found = [p for p in base.rglob("*.ndjson")] + [p for p in base.rglob("*.ndjson.gz")]
    return sorted(found)


def read_shard(path: str | os.PathLike) -> Iterator[dict]:
    """Yield the rows of one shard. A malformed line raises with its number —
    silently skipping it would turn data corruption into quiet data loss."""
    with _open_read(Path(path)) as fh:
        for n, raw in enumerate(fh, start=1):
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError as exc:
                raise ValueError(f"{path}:{n}: malformed NDJSON line ({exc})") from exc


def load_shards(
    con,
    *,
    table: str,
    root: str | os.PathLike = DEFAULT_ROOT,
    conflict_cols: Iterable[str] | None = None,
    paths: Sequence[str | os.PathLike] | None = None,
) -> dict:
    """Re-ingest shards into DuckDB. Idempotent: replaying the whole store over a
    populated database changes nothing (upsert on the table's primary key).

    This is the recovery path — the reason the operational DuckDB never needs to
    be committed or backed up. It is also the HOT path: `paper_cycle` opens
    `:memory:`, so every cycle rebuilds the entire store from scratch before it
    can do anything, and the store only grows.

    `rows_written` IS THE APPLIED COUNT, NOT THE OFFERED ONE. They differ only
    when a shard repeats a conflict key, which no shard does today (measured over
    the whole store: zero repeats in any replayed table) — but the two numbers
    are different claims and this one is a fact about the table rather than about
    what the caller sent. `rows_read` remains the offered count, so a divergence
    between the two is visible rather than silent.

    AND IT FEEDS A SERIES, which is why the change of meaning is written down
    rather than left to be inferred. `stage_load_state` sums this field across
    tables into `rows_loaded`, and that number is what a cycle reports as the
    size of the store it just rebuilt — the quantity the RAM projection is
    differenced from. So the series has a SEAM at this commit: points before it
    are rows OFFERED, points after are rows APPLIED. They are equal on every
    shard written so far (measured: zero repeated conflict keys anywhere in the
    store), and `applied` is the better quantity for that purpose — what occupies
    memory is what lands in the database, not what was read off disk. But a
    series must never be differenced ACROSS the seam."""
    cols = tuple(conflict_cols) if conflict_cols else CONFLICT_COLS.get(table)
    if not cols:
        raise ValueError(
            f"no conflict columns known for {table!r}; pass conflict_cols explicitly"
        )
    shards = [Path(p) for p in paths] if paths is not None else iter_shards(root, table)
    summary = {"table": table, "shards": len(shards), "rows_read": 0, "rows_written": 0}
    for shard in shards:
        # ONE BATCH PER SHARD, not one statement per row — and PER SHARD rather
        # than per table, which is a choice with a measured price on both sides.
        #
        # THE 39x IS NOT PRODUCTION'S NUMBER, and this is written before the
        # rest so nobody reads the rest as an operational claim. It was measured
        # on a machine where pandas exists, and `upsert_many` takes a fast
        # `INSERT ... SELECT` path only when it can import pandas — which
        # `requirements-paper.txt` deliberately excludes. On the host that runs
        # the cycle this batching has NO DETECTABLE EFFECT. Measured 2026-09-11:
        # `load:*` went 855.7 s -> 890.4 s across the merge, but the store grew
        # by one shard in between (+3.1% of rows), so normalised the change is
        # +0.9% — indistinguishable from zero. It is NOT "4% worse": that figure
        # was the store growing, and attributing it to the code was comparing two
        # cycles with different amounts of data.
        #
        # `executemany`, the fallback, beats the row-at-a-time loop by 1.10x on
        # one shard and not by the 1.52x its own docstring records for a
        # different workload. On a full table it runs at 0.96x of an empty one,
        # so there is no quadratic in the conflict clause.
        #
        # AND ONE THING IS UNEXPLAINED, said rather than filled in: with pandas
        # blocked LOCALLY the batching does improve — 1.09x overall, 1.35x on
        # price_history — and on the host it does not. Same branch, same
        # workload, opposite signs. DuckDB version, a different executemany
        # backend, or something in `load:*` that the local loop does not do are
        # all candidates and none has been measured.
        #
        # WHAT SURVIVES IS THE CORRECTNESS, NOT THE SPEED: identical conflict
        # semantics, tests verified able to fail, and the column-set grouping
        # below. The speed needs a path where Python never touches the rows —
        # DuckDB reading the .gz shard itself — which is what the pandas branch
        # was really buying: not pandas, but staying out of Python.
        #
        # Per table would be one statement instead of 32 and, WHERE THE FAST PATH
        # EXISTS, would approach the ceiling: decompressing and parsing the whole
        # store costs 1.64 s against the 19.86 s that path takes, so if the upsert
        # were free the speedup would be 474x rather than 39x. (That 474 lands within
        # 1% of the 478x `upsert_many`'s own docstring measured for the pure
        # INSERT ... SELECT path, on a different workload years apart.) So there
        # is a factor of 12 left on the table and it is left there deliberately.
        #
        # WHY IT IS LEFT: holding one table's rows at once costs 242 MB of peak
        # Python heap for `orderbook_snapshots` against 8.3 MB per shard
        # (measured with `tracemalloc` over the real store, two sessions
        # agreeing within the difference of one shard). That is 8.6% of the
        # ~2 827 MB free on a host with NO SWAP, where exhausting memory does not
        # raise — the kernel kills the process, and `_non_fatal`, the try/except
        # ladder and the rule that nothing may throw between `stage_collect` and
        # `stage_dump` are all built on exceptions and cannot see it. Trading 20
        # seconds for 8.6% of the one resource that kills silently is not a
        # trade worth making.
        #
        # The first estimate of that cost was ~45 MB, from rows x uncompressed
        # JSON bytes. It was short by more than 5x: `book_snapshot` is nested, and
        # a parsed Python dict is far heavier than the text it came from.
        # ESTIMATING PYTHON OBJECT MEMORY FROM TEXT SIZE UNDERSTATES, ALWAYS.
        #
        # `upsert_many`'s own docstring measured the three paths on this exact
        # workload: one INSERT per row 24.99 s, executemany 16.47 s, and
        # INSERT ... SELECT 0.05 s — 478x. The fast path has been in the same
        # module all along and the replay was not using it, which is why the
        # cycle's pre-collection time is dominated by rebuilding a store that
        # only grows: `paper_cycle` opens `:memory:`, so EVERY cycle pays a full
        # cold rebuild of every row ever written.
        #
        # Semantics are preserved rather than assumed: `upsert_many`
        # deduplicates keeping the LAST occurrence, which is what row-by-row
        # upserting does, and it does so BEFORE choosing its internal path.
        #
        # GROUPED BY COLUMN SET because `upsert_many` refuses a ragged batch —
        # correctly, since it would bind values to the wrong parameters. No
        # replayed table is ragged today (measured: the only two shard tables
        # with more than one column set, `cycle_params` and `venue_coverage`,
        # have no conflict columns and are never loaded). The grouping is here
        # so that the day one of them gains a column, the replay keeps working
        # instead of raising halfway through.
        groups: dict[tuple, list] = {}
        for row in read_shard(shard):
            summary["rows_read"] += 1
            groups.setdefault(tuple(row.keys()), []).append(row)
        for batch in groups.values():
            summary["rows_written"] += db.upsert_many(con, table, batch, cols)
    seq_start = restore_sequences(con, table=table)
    if seq_start is not None:
        summary["sequence_restarted_at"] = seq_start
    return summary


def store_stats(root: str | os.PathLike = DEFAULT_ROOT) -> dict:
    """Shard count and byte size per table — what the Actions job prints so the
    store's growth is visible in the run log before it becomes a problem."""
    base = Path(root)
    if not base.exists():
        return {"root": str(base), "exists": False, "tables": {}}
    tables: dict[str, dict] = {}
    for path in iter_shards(base):
        table = path.relative_to(base).parts[0]
        entry = tables.setdefault(table, {"shards": 0, "bytes": 0})
        entry["shards"] += 1
        entry["bytes"] += path.stat().st_size
    return {"root": str(base), "exists": True, "tables": tables,
            "total_bytes": sum(t["bytes"] for t in tables.values())}
