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
    con, station: str, dataset_version: str
) -> list[st.Observation]:
    """The station's readings, on the grid the SOURCE reported them on.

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
           ORDER BY observation_time""",
        [station, dataset_version],
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
    return st.MarketContext(
        market_id=str(market["market_id"]),
        event_id=str(market.get("event_id") or ""),
        contract_source=market.get("contract_source") or "",
        measurement_rule_code=market.get("measurement_rule") or "",
        unit=market.get("unit") or "",
        rounding_rule=market.get("rounding_rule"),
        target_date=target_date,
        station_icao=market.get("station_identifier"),
        station_tz=market.get("station_tz"),
    )


def label_market(
    con,
    market: dict,
    target_date: date,
    tokens: list[tuple[str, str]],
    dataset_version: str,
    asof: datetime | None = None,
) -> list[LabelRow]:
    """Label every token of one market. `tokens` is [(token_id, band_label), ...].

    Returns UNLABELLED rows carrying the operator's own reason when it declines.
    """
    station = market.get("station_identifier")
    if not station:
        return [
            LabelRow(str(market["market_id"]), t, LABEL_UNLABELLED, None, None,
                     "no_station_identifier")
            for t, _ in tokens
        ]
    obs = observations_for(con, station, dataset_version)
    result, reason = st.try_settle(obs, context_for(market, target_date), asof)
    if result is None:
        return [
            LabelRow(str(market["market_id"]), t, LABEL_UNLABELLED, None, None, reason)
            for t, _ in tokens
        ]

    out = []
    unit = market.get("unit")
    for idx, (token_id, band_label) in enumerate(tokens):
        if idx == 0:
            # the YES token carries the band
            won = st.band_key_wins(band_label, result.band_key, unit) if band_label else None
        else:
            # the NO token is the complement: it pays when the band did NOT occur
            yes_band = tokens[0][1]
            won = (
                not st.band_key_wins(yes_band, result.band_key, unit)
                if yes_band else None
            )
        if won is None:
            out.append(LabelRow(str(market["market_id"]), token_id, LABEL_UNLABELLED,
                                result.band_key, result.settled_value, "no_band_label"))
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
