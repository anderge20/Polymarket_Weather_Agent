#!/usr/bin/env python3
"""NIVEL 1 — REEJECUCION sobre el corpus reparado. NO cambia el criterio.

Implementa, palabra por palabra, la preinscripcion que ya existia (docstring de
`n1_14_baselines.py`) sobre la poblacion que define `PREREG_NIVEL1_REEJECUCION.md`:

  Unidad        (target_date, lead). Brier por banda, promediado DENTRO del evento y
                luego sobre eventos. Nunca las bandas como observaciones sueltas.
  Entrenamiento solo dias cuya ETIQUETA estaba disponible en t_asof del evento
                (fin del dia local + 24 h). Ventana expansiva. Minimo 20 pares.
  Modelos       B0 climatologia 30d · B1 persistencia · B2 forecast crudo
                B3 forecast + error empirico · B4 forecast bias-corregido + error
  CONFIRMA (nivel B): B3 o B4 mejoran a B0 en Brier por evento con IC95 bootstrap
                por evento que EXCLUYE el cero, EN LOS DOS LEADS.
  REFUTA: el intervalo incluye el cero en cualquiera de los dos leads.
  No se elige lead ni modelo despues de mirar: se reportan los cinco.

SOBRE B1, Y UNA AFIRMACION MIA QUE ERA FALSA. Escribi que `n1_14` y `n1_20` reportaban
cuatro modelos de los cinco. **Falso para `n1_14`**: su `MODELOS` (linea 112) incluye
`B1_persist`, lo calcula en la 98 y lo reporta en los tres bucles -- la tabla de A-239 lo
lleva. Quien lo dejo fuera es `n1_20_filtros.py:43`, y solo ese. Lo corrijo aqui porque
lo escribi en el docstring, en DECISIONS y en un mensaje de commit (session B).

Y B1 SE IMPLEMENTA CON EL MISMO CONJUNTO DE INFORMACION QUE EL ENTRENAMIENTO, que es lo
que `n1_14` ya hacia y la primera version de este guion NO: tomaba `obs[td - 1 dia]` sin
pasar por `label_av`, y en lead 24 el `t_asof` son las 12:00Z del dia ANTERIOR -- o sea
que "el maximo de ayer" incluia una tarde que aun no habia ocurrido. **Informacion del
futuro en un nivel cuya regla absoluta es EX-ANTE.** Aqui `pers` sale de `tr`, que ya
esta filtrado por `label_av(d) <= t`, con el mismo respaldo que `n1_14`: la ultima
etiqueta DISPONIBLE cuando la de ayer no lo esta.

La FORMA es la de B2 -- puntual convertido en indicador -- y no la de B3, porque la
preinscripcion agrupa B1 y B2 como los dos puntuales y reserva el error empirico para
B3/B4. Es una lectura declarada antes de correr, no una variante elegida tras ver un
numero.

LA VERDAD LA PONE EL MERCADO: `markets.winning_outcome`. La observacion sirve para las
lineas base y para la comprobacion de integridad (c), nunca como verdad.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import random
import statistics as st
import sys
from collections import Counter
from zoneinfo import ZoneInfo

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main")
sys.path.insert(0, os.path.join(REPO, "src"))
from weather_agent.polymarket.resolution import parse_band   # noqa: E402

LON = ZoneInfo("Europe/London")
MOD = ["B0_clima30", "B1_persistencia", "B2_fc_crudo", "B3_fc_error", "B4_fc_bias"]
SEMILLA = 20260913          # la misma de la ejecucion anterior, fijada antes de correr


def tasof(td, lead):
    return dt.datetime.combine(td, dt.time(12), dt.timezone.utc) - dt.timedelta(hours=lead)


def label_av(td):
    return (dt.datetime.combine(td + dt.timedelta(days=1), dt.time(0), LON)
            .astimezone(dt.timezone.utc) + dt.timedelta(hours=24))


def particion(bandas) -> bool:
    """Un `or below`, un `or higher`, y todos los enteros entre medias sin huecos.

    LA REGLA ES LA PARTICION, NUNCA EL RECUENTO: los 187 eventos EGLC del catalogo son
    187 particiones completas en TRES tamanos {7:2, 9:26, 11:159}. Un criterio escrito
    como "11 bandas" habria excluido 28 eventos sanos sin que nada avisara.
    """
    ab = [b for b in bandas if b[0] is None]
    ar = [b for b in bandas if b[1] is None]
    if len(ab) != 1 or len(ar) != 1:
        return False
    cer = sorted(int(a) for a, b in bandas if a is not None and b is not None and a == b)
    return cer == list(range(int(ab[0][1]) + 1, int(ar[0][0])))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dataset-version", required=True)
    ap.add_argument("--station", default="EGLC")
    ap.add_argument("--obs-dataset-version", default=None,
                    help="por defecto, el mismo que --dataset-version")
    args = ap.parse_args(argv)
    dsv_obs = args.obs_dataset_version or args.dataset_version

    con = duckdb.connect(args.db, read_only=True)
    con.execute("SET TimeZone='UTC'")

    # ---- observaciones: maximo por DIA LOCAL (A-238: nunca CAST(... AS DATE)) -----
    obs = {}
    for t, v in con.execute(
            "SELECT observation_time, observed_value FROM weather_observations "
            "WHERE station = ? AND dataset_version = ?", [args.station, dsv_obs]).fetchall():
        d = t.astimezone(LON).date()
        if d not in obs or v > obs[d]:
            obs[d] = v

    # ---- pronosticos: el ultimo disponible en t_asof, por lead ------------------
    FC = {}
    for td, av, tm in con.execute(
            "SELECT target_date, available_at, forecast_tmax FROM weather_forecasts "
            "WHERE station = ? AND dataset_version = ? AND forecast_tmax IS NOT NULL "
            "ORDER BY target_date, issue_time", [args.station, args.dataset_version]).fetchall():
        for lead in (24, 9):
            if av <= tasof(td, lead) and ((td, lead) not in FC or av > FC[(td, lead)][0]):
                FC[(td, lead)] = (av, tm)

    # ---- eventos: bandas + ganadora declarada POR EL MERCADO --------------------
    crudo = {}
    for eid, td, banda, gan in con.execute(
            """SELECT m.event_id, CAST(m.end_date AS DATE), o.band_label, m.winning_outcome
               FROM markets m JOIN outcomes o ON o.market_id = m.market_id
               WHERE m.station_identifier = ? AND m.dataset_version = ?
                 AND o.band_label IS NOT NULL AND o.outcome_label = 'Yes'""",
            [args.station, args.dataset_version]).fetchall():
        lo, hi = parse_band(banda, "C")
        crudo.setdefault((eid, td), []).append((lo, hi, str(gan).strip().lower() == "yes"))

    # ---- INTEGRIDAD: se imprime ANTES de cualquier Brier, y para si falla --------
    print("=" * 72)
    print("COMPROBACIONES DE INTEGRIDAD (PREREG_NIVEL1_REEJECUCION §6)")
    print("=" * 72)
    c = Counter()
    eventos = {}
    for (eid, td), bs in crudo.items():
        bandas = [(lo, hi) for lo, hi, _ in bs]
        ganadoras = [w for _, _, w in bs]
        if not particion(bandas):
            c["a_sin_particion_completa"] += 1
            continue
        if sum(ganadoras) != 1:
            c["b_sin_ganadora_unica" if sum(ganadoras) == 0 else "b_ganadoras_multiples"] += 1
            continue
        c["admitidos"] += 1
        eventos[td] = bs
    for k, v in sorted(c.items()):
        print(f"  {k:28s} {v:4d}")

    fuera = []
    for td, bs in eventos.items():
        if td not in obs:
            continue
        lo, hi, _ = next(b for b in bs if b[2])
        y = obs[td]
        if not ((lo is None or y >= lo) and (hi is None or y <= hi)):
            fuera.append((td, y, lo, hi))
    print(f"  c_obs_fuera_de_la_ganadora   {len(fuera):4d}   (de {sum(1 for td in eventos if td in obs)} con observacion)")
    for f in sorted(fuera):
        print(f"       {f[0]}  obs {f[1]:.1f}  banda [{f[2]}, {f[3]}]")
    print("  (c) NO detiene: es un RESULTADO propio, el desajuste observacion/resolucion.")

    tarde = con.execute(
        "SELECT count(*) FROM weather_forecasts WHERE station = ? AND dataset_version = ? "
        "AND available_at > issue_time + INTERVAL 48 HOUR", [args.station, args.dataset_version]).fetchone()[0]
    print(f"  d_pronosticos_sospechosos    {tarde:4d}")

    if c["admitidos"] == 0:
        print("\nPARADA: ningun evento admitido. No se calcula nada.")
        return 1

    # ---- el criterio, sin tocarlo ----------------------------------------------
    def masa(f, errs, lo, hi):
        return sum(1 for e in errs
                   if (lo is None or round(f + e) >= lo) and (hi is None or round(f + e) <= hi)) / len(errs)

    def corre(lead):
        filas = []
        for td in sorted(eventos):
            if (td, lead) not in FC:
                continue
            t = tasof(td, lead)
            f = FC[(td, lead)][1]
            tr = [(d, obs[d], FC[(d, lead)][1]) for d in sorted(obs)
                  if label_av(d) <= t and (d, lead) in FC]
            if len(tr) < 20:
                continue
            errs = [o - fx for _, o, fx in tr]
            bias = st.mean(errs)
            hist = [o for _, o, _ in tr[-30:]]
            # DE `tr`, QUE YA ESTA FILTRADO POR DISPONIBILIDAD, y nunca de `obs`
            # directamente: `obs[td-1]` en lead 24 incluiria una tarde posterior a
            # `t_asof`. Mismo respaldo que `n1_14`: la ultima etiqueta disponible.
            _a = [o for d, o, _ in tr if d == td - dt.timedelta(days=1)]
            pers = _a[0] if _a else tr[-1][1]
            for lo, hi, won in eventos[td]:
                dentro = lambda g: (lo is None or g >= lo) and (hi is None or g <= hi)
                filas.append((td, won, {
                    "B0_clima30": sum(1 for o in hist if dentro(round(o))) / len(hist),
                    "B1_persistencia": 1.0 if dentro(round(pers)) else 0.0,
                    "B2_fc_crudo": 1.0 if dentro(round(f)) else 0.0,
                    "B3_fc_error": masa(f, errs, lo, hi),
                    "B4_fc_bias": masa(f - bias, [e - bias for e in errs], lo, hi),
                }))
        return filas

    def brier(filas, m):
        d = {}
        for td, w, p in filas:
            d.setdefault(td, []).append(
                (min(max(p[m], 1e-6), 1 - 1e-6) - (1.0 if w else 0.0)) ** 2)
        return {td: st.mean(v) for td, v in d.items()}

    random.seed(SEMILLA)
    veredicto = {}
    for lead in (24, 9):
        filas = corre(lead)
        evs = sorted({td for td, _, _ in filas})
        print(f"\n{'='*72}\nlead {lead} h · eventos {len(evs)} · bandas {len(filas)}\n{'='*72}")
        if not evs:
            print("  sin eventos evaluables"); veredicto[lead] = None; continue
        B = {m: brier(filas, m) for m in MOD}
        for m in MOD:
            print(f"  {m:16s} Brier {st.mean(B[m].values()):.5f}")
        for m in MOD[1:]:
            d = [B[m][td] - B["B0_clima30"][td] for td in evs]
            n = len(d)
            r = sorted(st.mean(random.choices(d, k=n)) for _ in range(10000))
            lo_, hi_ = r[250], r[9750]
            excl = lo_ * hi_ > 0
            print(f"      {m:16s} - B0: {st.mean(d):+9.5f}  IC95 [{lo_:+.5f}, {hi_:+.5f}]"
                  f"  {'EXCLUYE EL CERO' if excl else 'incluye el cero'}")
            if m in ("B3_fc_error", "B4_fc_bias"):
                veredicto.setdefault(lead, []).append(excl and st.mean(d) < 0)

    print(f"\n{'='*72}\nCRITERIO PREREGISTRADO\n{'='*72}")
    ok = all(v and any(v) for v in veredicto.values())
    print("  CONFIRMA (nivel B): B3 o B4 mejoran a B0 con IC95 que excluye el cero "
          "EN LOS DOS LEADS")
    for lead in (24, 9):
        v = veredicto.get(lead)
        print(f"    lead {lead:2d}: {'SI' if (v and any(v)) else 'NO'}")
    print(f"\n  RESULTADO: {'B — HAY PODER PREDICTIVO' if ok else 'el criterio NO se cumple'}")
    print("  (la clasificacion A/B/C/D se escribe a mano leyendo esto, no la decide el guion)")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
