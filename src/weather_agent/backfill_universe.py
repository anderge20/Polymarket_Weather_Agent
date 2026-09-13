"""
backfill_universe.py — the ONE selection of catalogue events the backfills use
=============================================================================

WHY THIS EXISTS. The historical store held 1 028 of its 1 464 events TRUNCATED to
their lowest-id bands (B-136). Nothing downstream cut them: `backfill_prices`
chose which MARKETS to price — `row_number() OVER (PARTITION BY date ORDER BY
market_id)` kept the three lowest ids of each target date, which are usually the
three lowest bands of one London event — and `backfill_markets` then read only the
markets present in `price_history`, so the truncation spread to `markets` and
`outcomes`. Two scripts, two selections, and one of them inherited the other
through a gate.

WHAT THIS GUARANTEES, and the tests pin each point:

  * the unit of selection is the EVENT. Every catalogue row of a chosen event is
    returned; no filter here can drop a single market, so no caller can store part
    of a ladder;
  * filters are explicit and apply to events: station, target-date range, and
    optionally "(station, date) has a forecast";
  * a cap is a number of EVENTS, taken in a DECLARED order — target date, then the
    event id as an integer. The old cap sorted ids as strings; harmless while every
    id has six digits, and wrong the day one has seven, so a non-numeric id raises;
  * everything left out is COUNTED by reason, so "the store holds N events" can be
    read against "the catalogue offered M".

`target_date` is `endDate[:10]` (R8 / 2D §C anchor: target_date 12:00:00Z).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

#: The order a cap is taken in, stated so the output can print it.
ORDER = "target_date, int(event_id)"

EXCLUDED_NO_STATION = "no_station_identifier"
EXCLUDED_BEFORE_SINCE = "target_date_before_since"
EXCLUDED_AFTER_UNTIL = "target_date_after_until"
EXCLUDED_STATION_FILTER = "station_not_selected"
EXCLUDED_NO_FORECAST = "no_forecast_for_station_day"
EXCLUDED_BEYOND_CAP = "beyond_max_events"

#: Columns every consumer needs from `mk`. Callers may ask for more.
BASE_COLUMNS = ("market_id", "event_id", "station_identifier", "city", "endDate", "clobTokenIds")


@dataclass(frozen=True)
class Selection:
    """Whole events, in declared order, and what was left out and why."""

    rows: list[dict]
    events: list[str]
    order: str = ORDER
    excluded: dict[str, int] = field(default_factory=dict)


def present(value: Any) -> Any:
    """`value`, or None when it is missing — including the float NaN that pandas'
    `fetchdf()` hands back for a NULL VARCHAR. Measured on the real catalogue: 1 224
    events have no station, and they arrive as NaN, not None, so a plain
    `if not station` would treat them as a station named `nan`."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    return value


def target_date(row: Mapping[str, Any]) -> str:
    """`endDate[:10]` as `YYYY-MM-DD`. Raises if the row has none."""
    end = present(row.get("endDate"))
    if end is None:
        raise ValueError(f"market {row.get('market_id')!r} has no endDate")
    return str(end)[:10]


def _event_key(event_id: str) -> int:
    try:
        return int(event_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"event_id {event_id!r} is not an integer; the cap order is "
            f"{ORDER} and a string sort is exactly what this module replaces"
        ) from exc


def select_events(
    rows: Iterable[Mapping[str, Any]],
    *,
    stations: Iterable[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    forecast_pairs: set[tuple[str, str]] | None = None,
    max_events: int | None = None,
) -> Selection:
    """Choose whole catalogue events. See the module docstring for the guarantees.

    `forecast_pairs`, when given, is the set of `(station, "YYYY-MM-DD")` with a
    forecast; events whose station-day is not in it are excluded.
    """
    by_event: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_event[str(r["event_id"])].append(dict(r))

    wanted = {s.upper() for s in stations} if stations else None
    excluded: Counter[str] = Counter()
    kept: list[tuple[str, int, str]] = []
    for event_id, markets in by_event.items():
        station = next((present(m.get("station_identifier")) for m in markets
                        if present(m.get("station_identifier"))), None)
        dates = {target_date(m) for m in markets}
        if len(dates) != 1:
            raise ValueError(f"event {event_id} spans several target dates: {sorted(dates)}")
        day = dates.pop()
        if not station:
            excluded[EXCLUDED_NO_STATION] += 1
            continue
        if wanted is not None and station.upper() not in wanted:
            excluded[EXCLUDED_STATION_FILTER] += 1
            continue
        if since and day < since:
            excluded[EXCLUDED_BEFORE_SINCE] += 1
            continue
        if until and day > until:
            excluded[EXCLUDED_AFTER_UNTIL] += 1
            continue
        if forecast_pairs is not None and (station, day) not in forecast_pairs:
            excluded[EXCLUDED_NO_FORECAST] += 1
            continue
        kept.append((day, _event_key(event_id), event_id))

    kept.sort()
    if max_events is not None and len(kept) > max_events:
        excluded[EXCLUDED_BEYOND_CAP] += len(kept) - max_events
        kept = kept[:max_events]

    events = [event_id for _, _, event_id in kept]
    out_rows = [m for event_id in events
                for m in sorted(by_event[event_id], key=lambda m: _event_key(m["market_id"]))]
    return Selection(rows=out_rows, events=events, excluded=dict(excluded))


def summarize(selection: Selection) -> dict[str, Any]:
    """Counts a dry run prints: events and markets overall, by station and by month,
    and markets that cannot be priced for want of CLOB token ids."""
    by_station: Counter[str] = Counter()
    by_month: Counter[str] = Counter()
    seen: set[str] = set()
    no_tokens = 0
    for m in selection.rows:
        if not present(m.get("clobTokenIds")):
            no_tokens += 1
        event_id = str(m["event_id"])
        if event_id in seen:
            continue
        seen.add(event_id)
        by_station[str(m.get("station_identifier"))] += 1
        by_month[target_date(m)[:7]] += 1
    return {
        "events": len(selection.events),
        "markets": len(selection.rows),
        "markets_without_clob_token_ids": no_tokens,
        "by_station": dict(sorted(by_station.items())),
        "by_month": dict(sorted(by_month.items())),
        "order": selection.order,
        "excluded": dict(sorted(selection.excluded.items())),
    }


def load_catalog_rows(catalog_path: str, columns: Iterable[str] = BASE_COLUMNS) -> list[dict]:
    """Every market row of the catalogue (`mk`), with the requested columns."""
    import duckdb

    cols = list(dict.fromkeys([*BASE_COLUMNS, *columns]))
    con = duckdb.connect(catalog_path, read_only=True)
    try:
        return con.execute(f"SELECT {', '.join(cols)} FROM mk").fetchdf().to_dict("records")
    finally:
        con.close()
