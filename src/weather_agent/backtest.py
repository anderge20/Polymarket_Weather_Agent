"""
backtest.py — R19: the walk-forward backtest engine of PREREG_R21
=================================================================

Implements `PREREG_R21_BACKTEST_TAU.md` (sha `464226a3…`) as amended by
`PREREG_R21_ENMIENDA_A.md` (sha `3c7d9b13…`), both frozen before any PnL existed.

The engine is split in two on purpose:

  * `candidates()` produces one row per (market, lead, target_date) with its gross
    edge, its net edge, its calibration margin and its realised outcome. **This
    set does not depend on `tau_signal`.**
  * `walk_forward()` chooses `tau_signal` out of sample and filters that set.

The split is what makes the out-of-sample claim checkable: if choosing tau could
change which rows exist, "out of sample" would be a description of the code path
rather than a property of the data.

WHAT THIS ENGINE REFUSES TO DO
  * It never reads `is_winner`, `winning_outcome` or any resolution field before
    the decision instant — settlement enters only in `settle()`, after the row is
    built, and `build_feature` is the same as-of builder used in production.
  * It never evaluates at the quoted mid (§1). `costs.exec_price` moves the price
    adversely by `x_exec` before anything else happens.
  * It never subtracts the cost twice (§A.3): the cost is inside `edge_net`, and
    the threshold it is compared against is the calibration margin ALONE.
  * It never trades the short side. The priced token is the YES in all 6 143
    markets and no NO series exists; `1 − p` is a price identity, not a plan of
    execution (D19).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from statistics import median

from . import costs, database as db, error_model as em, features, stations, weather
from .m2 import DATASET_VERSION, LEADS, label_available_at
from .probability import band_probability, quantiles_to_distribution

#: PREREG_R21 §2 / B-11. Dispersion of the per-station bias, in Celsius. It is a
#: DIFFERENCE, so moving it to Fahrenheit multiplies by 9/5 and does NOT add 32
#: (§A.4) — adding the offset would shift the distribution 18 degrees and drive
#: the margin to ~1 for every narrow band.
TAU_EST_C = 0.545

#: §3, frozen: the candidate grid for `tau_signal`, in probability points.
TAU_SIGNAL_GRID = tuple(round(0.02 * k, 4) for k in range(1, 11))


def tau_in_unit(unit: str) -> float:
    u = (unit or "").strip().upper()
    if u == "C":
        return TAU_EST_C
    if u == "F":
        return TAU_EST_C * 9.0 / 5.0
    raise ValueError(f"unit {unit!r} is neither C nor F")


@dataclass(frozen=True)
class Candidate:
    market_id: str
    token_id: str
    station: str
    target_date: date
    lead_h: int
    decision_time: datetime
    label_available_at: datetime
    unit: str
    #: Band edges and the quantiles in the MARKET's unit. Carried on the row
    #: because R22 stratifies by where the band sits relative to the forecast, and
    #: recomputing that from the database afterwards would be a second, divergent
    #: implementation of the unit conversion — the defect that nearly shipped two
    #: `prices.py`.
    lo: float | None
    hi: float | None
    q_market: dict
    spec: costs.FeeSpec
    p_mid: float
    p_model: float
    edge_gross: float
    edge_net: float | None
    p_exec: float
    fee: float | None
    margin: float
    won: bool
    pnl: float | None

    @property
    def passes_exec(self) -> bool:
        """§A.3: the executable test. `edge_net is None` is a fail-closed refusal
        (unreadable fee schedule) and is NOT a rejection by threshold — it is
        counted separately so a substrate gap can never be read as a signal."""
        return self.edge_net is not None and self.edge_net > self.margin


def band_position(q_market: dict, lo, hi) -> str:
    """Where the band sits relative to the forecast, in the market's own unit.

    Declared ex ante and observable at the decision instant (R22 §2). The band's
    representative point is its midpoint for a closed band and its open edge for a
    tail band, because a tail band has no midpoint and defaulting to one would
    invent a location.
    """
    if lo is None and hi is None:
        return "abierta_ambos"
    x = hi if lo is None else lo if hi is None else (lo + hi) / 2.0
    if q_market[25] <= x <= q_market[75]:
        return "centro"
    if q_market[10] <= x <= q_market[90]:
        return "cola_cercana"
    return "cola_lejana"


def calibration_margin(quantiles_c: dict[int, float], *, unit: str,
                       lo: float | None, hi: float | None) -> float:
    """§2/§A.4: how much this band's probability moves when the distribution is
    displaced by the measured between-station dispersion.

    Computed PER MARKET, never as a constant in probability points: displacing by
    tau moves a narrow band near the centre a great deal and a wide band in the
    tail very little, so one constant would be a threshold with two operands —
    the defect that made M2 v1's `n>=30` wrong.
    """
    q = em.to_market_unit(quantiles_c, unit)
    base = band_probability(
        quantiles_to_distribution(p10=q[10], p25=q[25], p50=q[50], p75=q[75], p90=q[90]),
        lo=lo, hi=hi)
    tau = tau_in_unit(unit)
    worst = 0.0
    for s in (tau, -tau):
        shifted = {lvl: v + s for lvl, v in q.items()}
        p = band_probability(
            quantiles_to_distribution(
                p10=shifted[10], p25=shifted[25], p50=shifted[50],
                p75=shifted[75], p90=shifted[90]),
            lo=lo, hi=hi)
        worst = max(worst, abs(p - base))
    return worst


def decision_time(target_date: date, lead_h: int) -> datetime:
    """R8: the resolution window ends at `target_date` 12:00:00Z."""
    return datetime(target_date.year, target_date.month, target_date.day, 12,
                    tzinfo=timezone.utc) - timedelta(hours=lead_h)


def universe(con, target_date: date, dataset_version: str = DATASET_VERSION) -> list[dict]:
    """§A.6: the markets belonging to `target_date`.

    `target_date` is the CALLER'S parameter (2D §C). This is a universe filter on
    `end_date`, which R8 fixed at `target_date` 12:00Z — asking which markets
    belong to a date the caller already stated, not deriving the date from them.

    `uma_resolution_status = 'resolved'` is not decoration: without it a market
    that never resolved reads as a loss, because its `winning_outcome` is 'No' by
    default, and the backtest would settle trades against a world that has not
    happened.
    """
    end = datetime(target_date.year, target_date.month, target_date.day, 12,
                   tzinfo=timezone.utc)
    return db.query(
        con,
        """SELECT m.market_id, m.station_identifier AS station, m.unit,
                  m.winning_outcome, m.fees_enabled, m.fee_rate, m.fee_exponent,
                  m.fee_taker_only, o.token_id, o.lo, o.hi
           FROM markets m
           JOIN outcomes o
             ON o.market_id = m.market_id
            AND o.dataset_version = m.dataset_version
           WHERE m.dataset_version = ?
             AND m.end_date = ?
             AND m.uma_resolution_status = 'resolved'
             AND m.station_identifier IS NOT NULL
             AND lower(coalesce(m.rounding_rule, '')) <> 'tenths'
             AND o.outcome_label = 'Yes'
             AND m.unit IN ('C', 'F')""",
        [dataset_version, end],
    )


def candidates(con, target_dates, *, leads=LEADS,
               dataset_version: str = DATASET_VERSION,
               model: str = weather.M1_MODEL,
               x_exec: float = costs.X_EXEC_PRIMARY,
               cost_model: str = costs.H1_PRIMARY,
               counters: dict | None = None) -> list[Candidate]:
    """Every decision the strategy could have faced, with its realised outcome."""
    c = counters if counters is not None else {}

    def bump(k):
        c[k] = c.get(k, 0) + 1

    out: list[Candidate] = []
    for d in target_dates:
        rows = universe(con, d, dataset_version)
        if not rows:
            bump("dias_sin_universo")
            continue
        for lead in leads:
            t = decision_time(d, lead)
            for r in rows:
                feat = features.build_feature(
                    con, prediction_time=t, market_id=r["market_id"],
                    token_id=r["token_id"], station=r["station"], model=model,
                    target_date=d, dataset_version=dataset_version)
                if feat is None:
                    bump("sin_insumo_asof")
                    continue
                if feat["weather_prob"] is None:
                    bump("sin_probabilidad")
                    continue
                p_mid = float(feat["market_prob"])
                p_model = float(feat["weather_prob"])
                spec = costs.FeeSpec(
                    enabled=r["fees_enabled"], rate=r["fee_rate"],
                    exponent=r["fee_exponent"], taker_only=r["fee_taker_only"])
                net, p_exec, fee = costs.edge_net(
                    p_model=p_model, mid=p_mid, spec=spec, x_exec=x_exec,
                    model=cost_model)
                if net is None:
                    bump("fee_no_legible_fail_closed")
                quantiles_c = {lvl: feat[f"forecast_p{lvl}"] for lvl in (10, 25, 50, 75, 90)}
                margin = calibration_margin(
                    quantiles_c, unit=r["unit"], lo=r["lo"], hi=r["hi"])
                won = str(r["winning_outcome"]).strip().lower() == "yes"
                try:
                    tz = stations.timezone_of(r["station"])
                except stations.UnknownStation:
                    bump("estacion_sin_huso")
                    continue
                out.append(Candidate(
                    market_id=r["market_id"], token_id=r["token_id"], spec=spec,
                    lo=(None if r["lo"] is None else float(r["lo"])),
                    hi=(None if r["hi"] is None else float(r["hi"])),
                    q_market=em.to_market_unit(quantiles_c, r["unit"]),
                    station=r["station"], target_date=d, lead_h=lead,
                    decision_time=t, label_available_at=label_available_at(d, tz),
                    unit=r["unit"], p_mid=p_mid, p_model=p_model,
                    edge_gross=p_model - p_mid, edge_net=net, p_exec=p_exec,
                    fee=fee, margin=margin, won=won,
                    pnl=(None if fee is None else
                         costs.realised_pnl(won=won, p_exec=p_exec, fee=fee)),
                ))
                bump("candidatos")
    return out


def reprice(cands: list[Candidate], *, x_exec: float,
            cost_model: str = costs.H1_PRIMARY) -> list[Candidate]:
    """The same candidates at a different execution assumption.

    The sensitivity ladder of §A.2 changes `x_exec` and the cost reading and
    NOTHING else: the as-of price, the model probability, the band, the margin and
    the realised outcome are all identical. Re-running `candidates()` per rung
    would cost six full passes over the substrate AND would leave open the
    question of whether the six candidate sets were really the same. Repricing one
    set makes the identity structural rather than hoped for.
    """
    out: list[Candidate] = []
    for c in cands:
        net, p_exec, fee = costs.edge_net(
            p_model=c.p_model, mid=c.p_mid, spec=c.spec, x_exec=x_exec,
            model=cost_model)
        out.append(replace(
            c, edge_net=net, p_exec=p_exec, fee=fee,
            pnl=(None if fee is None else
                 costs.realised_pnl(won=c.won, p_exec=p_exec, fee=fee))))
    return out


def select_tau(train: list[Candidate], grid=TAU_SIGNAL_GRID) -> float | None:
    """§3, frozen: the tau maximising the MEDIAN net PnL per trade on `train`.

    Median and not mean because with few trades the mean is fixed by one tail.
    Ties within 1e-9 go to the LARGER tau: fewer trades, a stricter rule. A tau
    with no trades in training is not a candidate — it would win by vacuity, the
    same defect §4.1 exists to block downstream.
    """
    best, best_med = None, None
    for tau in grid:
        pnls = [c.pnl for c in train if c.edge_gross >= tau and c.passes_exec
                and c.pnl is not None]
        if not pnls:
            continue
        m = median(pnls)
        if best_med is None or m > best_med + 1e-9 or (abs(m - best_med) <= 1e-9 and tau > best):
            best, best_med = tau, m
    return best


def walk_forward(cands: list[Candidate], grid=TAU_SIGNAL_GRID) -> tuple[list[Candidate], dict]:
    """§3: expanding walk-forward by target date.

    At each decision instant only trades whose LABEL WAS ALREADY AVAILABLE may
    train the threshold — end of the local day plus the assumed 24 h lag (v2 §3).
    Filtering on `target_date < D` instead is the leak that withdrew M2 v1: it
    leaked in 8 of 8 stations, by −9 h to −43 h.
    """
    taken: list[Candidate] = []
    chosen: dict = {}
    for d in sorted({c.target_date for c in cands}):
        for lead in sorted({c.lead_h for c in cands}):
            day = [c for c in cands if c.target_date == d and c.lead_h == lead]
            if not day:
                continue
            t = decision_time(d, lead)
            train = [c for c in cands if c.label_available_at <= t]
            tau = select_tau(train, grid)
            chosen[f"{d.isoformat()}|{lead}"] = {
                "tau": tau, "n_entrenamiento": len(train)}
            if tau is None:
                continue
            taken.extend(c for c in day
                         if c.edge_gross >= tau and c.passes_exec and c.pnl is not None)
    return taken, chosen
