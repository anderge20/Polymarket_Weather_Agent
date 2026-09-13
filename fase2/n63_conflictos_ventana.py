#!/usr/bin/env python3
"""Tarea #63 — CONTAR CONFLICTOS REALES DE VENTANA CONTRA RESOLUCIONES.

Ejecuta `PREREG_N063_CONFLICTOS_VENTANA.md`, espejado antes de correr esto. La definicion
de dia expuesto es la de A-259, copiada sin tocar; lo nuevo es el paso (d) contra la
ganadora declarada, que A-259 no pudo dar porque las escaleras estaban truncadas.

CERO PETICIONES: tarball ya descargado + `pmw.duckdb`.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import sys
import tarfile
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
from weather_agent import observations as obsmod, stations, weather        # noqa: E402
from weather_agent.polymarket.resolution import parse_band                 # noqa: E402
from n075_poblacion import DB, poblacion                                   # noqa: E402
from n63_particion_general import particion_general                        # noqa: E402

TB = "/Users/mariaaleu/pmw-e2/evidence/B-133/raw_iem_55_estaciones.tgz"
PEAK = set(weather.PEAK_LOCAL_HOURS)


def banda_de(valor, bandas):
    """La banda que contiene `valor`, o None. `bandas` = [(lo, hi, gano), ...]."""
    for lo, hi, gano in bandas:
        if (lo is None or valor >= lo) and (hi is None or valor <= hi):
            return (lo, hi, gano)
    return None


def poblacion_general(con, dsv, station):
    """Misma regla de A-275 que `n075_poblacion.poblacion`, con DOS generalizaciones que
    esa version no necesitaba porque solo se uso en EGLC:

      * `parse_band` con la unidad DEL MERCADO en vez de `"C"` fijo;
      * `particion_general`, que admite bandas de anchura > 1 (las de 2 grados F).

    Se verifica contra la original en EGLC antes de usarla (`_comprueba_equivalencia`):
    si las dos no dan exactamente la misma poblacion, este guion se para.
    """
    ev = {}
    for eid, td, ct, uma, banda, gan, unidad in con.execute(
            """SELECT m.event_id, CAST(m.end_date AS DATE), m.close_time,
                      m.uma_resolution_status, o.band_label, m.winning_outcome, m.unit
               FROM markets m JOIN outcomes o
                      ON o.market_id = m.market_id AND o.dataset_version = m.dataset_version
               WHERE m.station_identifier = ? AND m.dataset_version = ?
                 AND o.band_label IS NOT NULL AND o.outcome_label = 'Yes'""",
            [station, dsv]).fetchall():
        lo, hi = parse_band(banda, unidad or "C")
        e = ev.setdefault(eid, {"event_id": eid, "fecha": td, "close": ct,
                                "uma": set(), "bandas": [], "unit": unidad})
        e["uma"].add(uma)
        e["bandas"].append((lo, hi, str(gan).strip().lower() == "yes"))
        if ct is not None and (e["close"] is None or ct > e["close"]):
            e["close"] = ct

    por_fecha = {}
    for e in ev.values():
        bandas = [(lo, hi) for lo, hi, _ in e["bandas"]]
        gan = sum(1 for _, _, w in e["bandas"] if w)
        e["n_bandas"] = len(bandas)
        e["elegible"] = (e["uma"] == {"resolved"} and particion_general(bandas) and gan == 1)
        por_fecha.setdefault(e["fecha"], []).append(e)

    elegidos = {}
    for td, es in por_fecha.items():
        cands = [e for e in es if e["elegible"]]
        if not cands:
            continue
        corte = dt.datetime.combine(td + dt.timedelta(days=1), dt.time(0),
                                    ZoneInfo("UTC")).astimezone(dt.timezone.utc)
        arriba = [e for e in cands if e["close"] is not None and e["close"] > corte]
        pool = arriba or cands
        elegidos[td] = min(pool, key=lambda e: (e["close"] is None, e["close"] or corte))
    return elegidos


def _comprueba_equivalencia(con):
    """EGLC es todo Celsius y enteros sueltos: las dos poblaciones DEBEN coincidir."""
    a, _, _, _ = poblacion(con, "markets_v2", "EGLC")
    b = poblacion_general(con, "markets_v2", "EGLC")
    iguales = (set(a) == set(b)
               and all(a[d]["event_id"] == b[d]["event_id"] for d in a))
    print(f"equivalencia en EGLC: original {len(a)} fechas · general {len(b)} fechas · "
          f"{'IDENTICAS' if iguales else 'DIFIEREN'}")
    if not iguales:
        raise SystemExit("PARADA: la generalizacion cambia EGLC. No se sigue.")


def carga_estacion(t, icao, sufijo, tz):
    d = defaultdict(list)
    nombre = f"raw/{icao}_{sufijo}.csv"
    try:
        datos = t.extractfile(nombre).read().decode()
    except KeyError:
        return d
    for r in csv.DictReader(io.StringIO(datos)):
        try:
            f = float(r["tmpf"])
        except (TypeError, ValueError):
            continue
        loc = (dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M")
               .replace(tzinfo=dt.timezone.utc).astimezone(tz))
        d[loc.date()].append((loc, f))
    return d


def main():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    _comprueba_equivalencia(con)
    t = tarfile.open(TB)
    icaos = sorted({os.path.basename(n).split("_")[0]
                    for n in t.getnames() if n.endswith(".csv")})
    print(f"estaciones en el tarball: {len(icaos)}")

    c = Counter()
    expuestos = []          # (icao, dia, v_civil, v_resto, unidad)
    for icao in icaos:
        try:
            tz = ZoneInfo(stations.timezone_of(icao))
        except Exception:
            c["sin_timezone"] += 1
            continue
        serie, unidad, res = obsmod.station_series(icao)
        sufijo = "rt34" if "34" in serie or "RT34" in serie else "rt3"
        dias = carga_estacion(t, icao, sufijo, tz)
        if not dias:
            c["sin_fichero_para_su_serie"] += 1
            continue
        for d, vals in dias.items():
            if not PEAK <= {loc.hour for loc, _ in vals}:
                continue
            c["etiquetables"] += 1

            def q(f):
                cc = (f - 32.0) * 5.0 / 9.0
                raw = f if unidad == "F" else cc
                return round(raw / res) * res

            punt = [(loc, q(f)) for loc, f in vals]
            mx = max(p for _, p in punt)
            h0 = [p for loc, p in punt if loc.hour == 0]
            resto = [p for loc, p in punt if loc.hour != 0]
            if not (h0 and max(h0) == mx):
                continue
            c["argmax_en_h0"] += 1
            if resto and max(h0) <= max(resto):
                continue
            c["ESTRICTO"] += 1
            expuestos.append((icao, d, mx, max(resto) if resto else None, unidad))

    print(f"\n{'='*78}\nEXPOSICION (definicion de A-259, sin tocar)\n{'='*78}")
    for k in ("etiquetables", "argmax_en_h0", "ESTRICTO", "sin_timezone",
              "sin_fichero_para_su_serie"):
        if c[k]:
            print(f"  {k:28s} {c[k]:6d}")

    # ---- poblacion A-275 por estacion, solo para las que tienen expuestos ----
    pobs = {}
    for icao in sorted({e[0] for e in expuestos}):
        pobs[icao] = poblacion_general(con, "markets_v2", icao)

    print(f"\n{'='*78}\nPASO (d) Y RESOLUCION — lo que A-259 no pudo medir\n{'='*78}")
    r = Counter()
    detalle = []
    for icao, d, v_civ, v_res, unidad in expuestos:
        ev = pobs.get(icao, {}).get(d)
        if ev is None:
            r["SIN_EVENTO_ELEGIBLE"] += 1
            detalle.append((icao, d, v_civ, v_res, "SIN_EVENTO_ELEGIBLE", None, None))
            continue
        u_mkt = ev.get("unit") or unidad
        if u_mkt != unidad:
            r["UNIDAD_DISCREPA"] += 1
            detalle.append((icao, d, v_civ, v_res, "UNIDAD_DISCREPA", u_mkt, unidad))
            continue
        b_civ = banda_de(v_civ, ev["bandas"])
        b_res = banda_de(v_res, ev["bandas"]) if v_res is not None else None
        if b_civ is None or b_res is None:
            r["VALOR_FUERA_DE_LA_ESCALERA"] += 1
            detalle.append((icao, d, v_civ, v_res, "VALOR_FUERA_DE_LA_ESCALERA", b_civ, b_res))
            continue
        if b_civ[:2] == b_res[:2]:
            r["misma_banda"] += 1
            continue
        r["banda_distinta"] += 1
        if b_res[2]:
            cls = "A_FAVOR_DE_ESTRICTO"
        elif b_civ[2]:
            cls = "A_FAVOR_DE_CIVIL"
        else:
            cls = "NINGUNA"
        r[cls] += 1
        detalle.append((icao, d, v_civ, v_res, cls, b_civ[:2], b_res[:2]))

    for k in sorted(r):
        print(f"  {k:30s} {r[k]:5d}")
    print(f"\n  denominador (dias etiquetables) {c['etiquetables']}")
    if c["etiquetables"]:
        print(f"  ESTRICTO / etiquetables          {c['ESTRICTO']/c['etiquetables']*100:.3f} %")
        print(f"  banda_distinta / etiquetables    {r['banda_distinta']/c['etiquetables']*100:.3f} %")

    print(f"\n{'='*78}\nCASOS, uno a uno\n{'='*78}")
    print(f"  {'icao':6s} {'dia':12s} {'civil':>8s} {'resto':>8s}  {'clase':28s} banda_civil -> banda_resto")
    for icao, d, vc, vr, cls, bc, br in sorted(detalle, key=lambda x: (x[4], x[0], str(x[1]))):
        vrs = f"{vr:8.1f}" if isinstance(vr, float) else f"{str(vr):>8s}"
        print(f"  {icao:6s} {str(d):12s} {vc:8.1f} {vrs}  {cls:28s} {bc} -> {br}")
    con.close()


if __name__ == "__main__":
    main()
