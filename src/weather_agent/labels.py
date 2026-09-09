"""
labels.py — R14: the realized-outcome label table
==================================================

Turns the frozen SettlementOperator (R12, `weather_agent.settlement`) into the
label column R19/R20/R21 consume. The operator decides WHAT the settled value is;
this module only asks it, per market, and records the answer or the refusal.

WHAT A LABEL IS HERE, AND WHAT IT IS NOT
-----------------------------------------
A label is the realized outcome of a market: did this token's band contain the
settled value. It is a TARGET, never a feature. `build_feature` does not read this
table, and `weather_observations.available_at` (the download instant, B-4) makes
the as-of engine refuse it anyway.

A refusal is DATA, not a gap. When the operator declines — `series_mismatch`,
`source_inaccessible`, a stratum with no operator — the market is recorded as
unlabelled WITH the reason. Guessing a winner from the last traded price would
make the ledger fiction, which is exactly why the operator refuses in the first
place.

SUBSTRATE
---------
Requires `markets.contract_source` (the R29 classifier's output) and the source
grid columns of migration 4. `missing_substrate()` NAMES what is absent rather
than reporting "not wired": a caller that cannot run should be told which column
to add, not left to find out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from . import database as db
from . import settlement as st
from . import stations

LABEL_WINNER = "WINNER"
LABEL_LOSER = "LOSER"
LABEL_UNLABELLED = "UNLABELLED"

#: Columns this module needs beyond the 2A core.
REQUIRED_COLUMNS = {
    "markets": ("contract_source", "measurement_rule", "unit", "station_identifier"),
    "weather_observations": ("observed_value", "observed_unit", "series"),
}


@dataclass(frozen=True)
class LabelRow:
    market_id: str
    token_id: str
    label: str
    band_key: int | None
    settled_value: float | None
    reason: str | None


def _day_bounds(target_date: date, station: str):
    """The station-LOCAL day, in UTC. Falls back to the UTC day only when the
    station's timezone is unknown — and then the operator refuses anyway."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    try:
        zone = ZoneInfo(stations.timezone_of(station))
    except Exception:  # noqa: BLE001 - unknown station: the operator will refuse
        zone = timezone.utc
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=zone)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def _day_start(target_date: date, station: str) -> datetime:
    return _day_bounds(target_date, station)[0]


def _day_end(target_date: date, station: str) -> datetime:
    return _day_bounds(target_date, station)[1]


def missing_substrate(con) -> list[str]:
    """Which required columns are absent, as `table.column`. Empty means ready."""
    missing = []
    tables = set(db.table_names(con))
    for table, cols in REQUIRED_COLUMNS.items():
        if table not in tables:
            missing.append(table)
            continue
        have = set(db.column_names(con, table))
        missing.extend(f"{table}.{c}" for c in cols if c not in have)
    return sorted(missing)


def observations_for(
    con, station: str, target_date: date, dataset_version: str
) -> list[st.Observation]:
    """The readings of ONE station-day, on the grid the SOURCE reported them on.

    `target_date` is not optional. Under SOURCE_DAILY_ROW the operator applies no
    temporal predicate BY DESIGN — its contract is that the caller hands over the
    source's row for that date. Passing the station's whole history made the
    aggregation return the maximum of every day on record, and it did not fail
    closed: it emitted the label of a different day. Masked while the station
    guard killed stratum 10 first; it opens the moment that guard goes.

    `observed_value` + `observed_unit`, never `tmax_observed`: the latter is always
    Celsius, and settling a Fahrenheit market on a converted value settles it off
    its own grid (A-41).
    """
    rows = db.query(
        con,
        """SELECT observation_time, observed_value, observed_unit, series,
                  available_at, record_version
           FROM weather_observations
           WHERE station = ? AND dataset_version = ? AND observed_unit <> 'UNKNOWN'
             AND observation_time >= ? AND observation_time < ?
           ORDER BY observation_time""",
        [station, dataset_version, _day_start(target_date, station).isoformat(),
         _day_end(target_date, station).isoformat()],
    )
    out = []
    for r in rows:
        ts = r["observation_time"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        out.append(
            st.Observation(
                ts_utc=ts,
                value=float(r["observed_value"]),
                unit=r["observed_unit"],
                series=r["series"],
                available_at=r.get("available_at"),
                record_version=int(r.get("record_version") or 1),
            )
        )
    return out


def context_for(market: dict, target_date: date) -> st.MarketContext:
    """Build the operator's context.

    `station_tz` comes from `stations.timezone_of`, NOT from a `markets.station_tz`
    column — that column does not exist in any DDL or migration, so reading it with
    .get() returned None silently and every LOCAL_CIVIL_DAY operator (strata 5, 7
    and 8: 15 213 markets, 89 % of what should be labelled) died with
    `context_out_of_snapshot`. The correct piece was already in this package and
    unused; it also raises rather than defaulting to UTC.

    A station with no known timezone yields `fail_closed_reason`, which `settle`
    TRANSLATES into the closed enum — the caller does not invent reason strings.
    """
    icao = market.get("station_identifier")
    tz = None
    fail = None
    if icao:
        try:
            tz = stations.timezone_of(icao)
        except stations.UnknownStation:
            fail = f"unknown_station_timezone:{icao}"
    return st.MarketContext(
        market_id=str(market["market_id"]),
        event_id=str(market.get("event_id") or ""),
        contract_source=market.get("contract_source") or "",
        measurement_rule_code=market.get("measurement_rule") or "",
        unit=market.get("unit") or "",
        rounding_rule=market.get("rounding_rule"),
        target_date=target_date,
        station_icao=icao,
        station_tz=tz,
        fail_closed_reason=fail,
    )


def label_market(
    con,
    market: dict,
    target_date: date,
    tokens: list[tuple[str, str, str]],
    dataset_version: str,
    asof: datetime | None = None,
) -> list[LabelRow]:
    """Label every token of one market. `tokens` is
    [(token_id, band_label, outcome_label), ...].

    The YES token is the one whose `outcome_label` is "Yes" — the rule written in
    2D and restated in `strategy_a.py:9`: NEVER by `outcome_index`, NEVER by
    `is_winner`. Position happens to work today (93 221 of 93 221 markets come
    back as ('Yes','No')), but if it ever did not, every label would be inverted
    and the PnL would come out sign-flipped and perfectly self-consistent — wrong
    in the one way nothing downstream can detect.

    Returns UNLABELLED rows carrying the operator's own reason when it declines.
    """
    # NO station guard here. Stratum 10 (HKO, 1 859 markets — the only DIRECT
    # stratum and the only one with an evaluable holdout) has icao2 NULL BY NATURE,
    # not by defect, and a guard above the operator meant it never reached
    # try_settle at all. The operator decides what its own window_kind requires;
    # this is the same defect A-43 fixed one level down, reintroduced by the caller.
    station = market.get("station_identifier")
    obs = observations_for(con, station, target_date, dataset_version) if station else []
    result, reason = st.try_settle(obs, context_for(market, target_date), asof)
    if result is None:
        return [
            LabelRow(str(market["market_id"]), t, LABEL_UNLABELLED, None, None, reason)
            for t, _, _ in tokens
        ]

    yes = [(tid, band) for tid, band, olabel in tokens
           if str(olabel).strip().lower() == "yes"]
    if len(yes) != 1:
        # Fail closed: without exactly one YES token the complement is undefined,
        # and guessing which side is which is how a sign-flipped ledger happens.
        # The reason is TRANSLATED into the closed enum rather than invented:
        # settlement.py §4 is a closed set, and writing a caller-made string into
        # the same `reason` field would quietly stop it being closed downstream.
        return [
            LabelRow(str(market["market_id"]), t, LABEL_UNLABELLED,
                     result.band_key, result.settled_value,
                     st.R_CONTEXT_OUT_OF_SNAPSHOT)
            for t, _, _ in tokens
        ]
    yes_token, yes_band = yes[0]

    out = []
    unit = market.get("unit")
    for token_id, band_label, _olabel in tokens:
        if not yes_band:
            won = None
        elif token_id == yes_token:
            won = st.band_key_wins(yes_band, result.band_key, unit)
        else:
            # the NO token is the complement: it pays when the YES band did NOT occur
            won = not st.band_key_wins(yes_band, result.band_key, unit)
        if won is None:
            out.append(LabelRow(str(market["market_id"]), token_id, LABEL_UNLABELLED,
                                result.band_key, result.settled_value,
                                st.R_CONTEXT_OUT_OF_SNAPSHOT))
        else:
            out.append(LabelRow(
                str(market["market_id"]), token_id,
                LABEL_WINNER if won else LABEL_LOSER,
                result.band_key, result.settled_value, None))
    return out


def persist(con, rows: list[LabelRow], dataset_version: str) -> int:
    """Write labels onto `outcomes.is_winner`. Only ever writes a settled verdict;
    an UNLABELLED row leaves `is_winner` NULL, which reads as unknown."""
    n = 0
    for r in rows:
        if r.label == LABEL_UNLABELLED:
            continue
        con.execute(
            """UPDATE outcomes SET is_winner = ?
               WHERE market_id = ? AND token_id = ? AND dataset_version = ?""",
            [r.label == LABEL_WINNER, r.market_id, r.token_id, dataset_version],
        )
        n += 1
    return n
