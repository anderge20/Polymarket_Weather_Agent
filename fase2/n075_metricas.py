#!/usr/bin/env python3
"""NIVEL 0.75 · puntos 1 y 2 — Brier y Log Loss, OLD vs CORRECTED.

REFERENCE / SANITY CONTROLS — NOT LEVEL 1.  (reetiquetado tras H4 = INVALIDADA, A-280)
Todo lo que produce este guion son controles de cordura del instrumento. `REF_uniforme`
es un CONTROL ESTRUCTURAL, no un modelo predictivo. `B0`..`B4` son lineas base de
referencia. Nada de esto ordena modelos ni mide poder predictivo. Y NUNCA agregar estas
puntuaciones entre eventos con distinto numero de bandas: ver `N075_H4_RESULTADO.md`.

ESTO NO ES NIVEL 1. El encargo dice «NO ejecutes todavia ningun modelo de Level 1», y
aqui no se ejecuta ninguno: no hay bootstrap, no hay intervalo de confianza, no se evalua
el criterio CONFIRMA/REFUTA, no se ordenan modelos y no se declara poder predictivo. Las
metricas se calculan como INSTRUMENTO DE VALIDACION DEL DATASET: la pregunta es si la
maquinaria metrica se comporta igual sobre las dos poblaciones, no cual gana.

Dos familias de probabilidad, y la primera no es un modelo:

  REF_uniforme   p = 1 / n_bandas del evento. No mira datos: es una propiedad de la
                 ESTRUCTURA DEL CONTRATO. Es la referencia honesta para comparar
                 poblaciones, porque cualquier diferencia entre brazos viene de la
                 poblacion y de nada mas.
  B0..B4         las cinco lineas base ya preinscritas (docstring de `n1_14`). Se
                 reportan porque el encargo pide «exactamente la misma metrica», y se
                 reportan CON EL VEREDICTO RETENIDO.

FORMULAS, identicas en los dos brazos:

  clip(p)   = min(max(p, 1e-6), 1 - 1e-6)            el mismo 1e-6 de `n1_20` y `n1_40`
  Brier     = (clip(p) - y)^2                         por CONTRATO
  LogLoss   = -[ y*ln(clip(p)) + (1-y)*ln(1-clip(p)) ] por CONTRATO

  unidad por contrato : media sobre todas las filas (evento, banda)
  unidad por evento   : media DENTRO del evento, luego media sobre eventos   <- primaria
  unidad evento x lead: la fila es (event_id, lead); los dos leads se reportan siempre

La unidad PRIMARIA es el evento, y la razon esta escrita desde `n1_14`: las 11 bandas de
un evento son 11 contratos del MISMO sorteo, no 11 observaciones independientes. Ponderar
por contrato da mas peso a los eventos con escalera larga. En esta ventana todos son de 11
bandas, asi que las dos ponderaciones coinciden hasta el redondeo -- y se muestran las dos
precisamente para que eso se vea en lugar de suponerse.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics as stx
import sys
from collections import Counter, defaultdict

import duckdb

sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
from n075_poblacion import DB, LON, observaciones, poblacion, pronosticos   # noqa: E402

EPS = 1e-6
LEADS = (24, 9)
MOD = ["REF_uniforme", "B0_clima30", "B1_persistencia", "B2_fc_crudo", "B3_fc_error", "B4_fc_bias"]


def tasof(td, lead):
    return dt.datetime.combine(td, dt.time(12), dt.timezone.utc) - dt.timedelta(hours=lead)


def label_av(td):
    return (dt.datetime.combine(td + dt.timedelta(days=1), dt.time(0), LON)
            .astimezone(dt.timezone.utc) + dt.timedelta(hours=24))


def filas(pob, obs, FC, lead):
    """Una fila por (event_id, lead, banda). Independiente del brazo salvo por `pob`."""
    out = []
    for td in sorted(pob):
        if td not in obs or (td, lead) not in FC:
            continue
        t = tasof(td, lead)
        f = FC[(td, lead)][1]
        tr = [(d, obs[d], FC[(d, lead)][1]) for d in sorted(obs)
              if label_av(d) <= t and (d, lead) in FC]
        if len(tr) < 20:
            continue
        errs = [o - fx for _, o, fx in tr]
        bias = stx.mean(errs)
        hist = [o for _, o, _ in tr[-30:]]
        _a = [o for d, o, _ in tr if d == td - dt.timedelta(days=1)]
        pers = _a[0] if _a else tr[-1][1]
        ev = pob[td]
        n = ev["n_bandas"]
        for lo, hi, won in ev["bandas"]:
            dentro = lambda g: (lo is None or g >= lo) and (hi is None or g <= hi)
            masa = lambda ff, ee: sum(1 for e in ee if dentro(round(ff + e))) / len(ee)
            out.append({
                "event_id": ev["event_id"], "fecha": td, "lead": lead, "n_bandas": n,
                "y": 1.0 if won else 0.0,
                "p": {"REF_uniforme": 1.0 / n,
                      "B0_clima30": sum(1 for o in hist if dentro(round(o))) / len(hist),
                      "B1_persistencia": 1.0 if dentro(round(pers)) else 0.0,
                      "B2_fc_crudo": 1.0 if dentro(round(f)) else 0.0,
                      "B3_fc_error": masa(f, errs),
                      "B4_fc_bias": masa(f - bias, [e - bias for e in errs])},
            })
    return out


def clip(p):
    return min(max(p, EPS), 1.0 - EPS)


def resumen(fs, m):
    por_ev = defaultdict(list)
    bri_c, log_c = [], []
    for r in fs:
        p, y = clip(r["p"][m]), r["y"]
        b = (p - y) ** 2
        l = -(y * math.log(p) + (1 - y) * math.log(1 - p))
        bri_c.append(b); log_c.append(l)
        por_ev[(r["event_id"], r["lead"])].append((b, l))
    bri_e = [stx.mean(x[0] for x in v) for v in por_ev.values()]
    log_e = [stx.mean(x[1] for x in v) for v in por_ev.values()]
    return {"n_ev": len(por_ev), "n_con": len(fs),
            "brier_contrato": stx.mean(bri_c) if bri_c else float("nan"),
            "brier_evento": stx.mean(bri_e) if bri_e else float("nan"),
            "logloss_contrato": stx.mean(log_c) if log_c else float("nan"),
            "logloss_evento": stx.mean(log_e) if log_e else float("nan")}


def auditoria_p(fs, m):
    c = Counter()
    for r in fs:
        p, y = r["p"][m], r["y"]
        if p == 0.0: c["p_exactamente_0"] += 1; c["p0_con_y1" if y == 1 else "p0_con_y0"] += 1
        if p == 1.0: c["p_exactamente_1"] += 1; c["p1_con_y0" if y == 0 else "p1_con_y1"] += 1
        if 0.0 < p < EPS: c["p_bajo_eps_sin_ser_0"] += 1
        if 1 - EPS < p < 1.0: c["p_sobre_1meps_sin_ser_1"] += 1
        if p != clip(p): c["recortados"] += 1
    # cuanto del log loss viene de terminos recortados
    tot = rec = 0.0
    for r in fs:
        p, y = clip(r["p"][m]), r["y"]
        l = -(y * math.log(p) + (1 - y) * math.log(1 - p))
        tot += l
        if r["p"][m] != p: rec += l
    c["_logloss_total"] = tot
    c["_logloss_de_recortados"] = rec
    return c


def tabla(nombre, conjuntos):
    print(f"\n{'='*100}\n{nombre}\n{'='*100}")
    print(f"{'brazo/ambito':26s} {'lead':>4s} {'evs':>4s} {'contr':>6s} {'YESrate':>8s} "
          f"{'modelo':16s} {'Brier/contr':>12s} {'Brier/evento':>13s} {'LL/contr':>10s} {'LL/evento':>10s}")
    for etq, fs in conjuntos:
        if not fs:
            print(f"{etq:26s}  (vacio)"); continue
        lead = fs[0]["lead"]
        yr = sum(r["y"] for r in fs) / len(fs)
        for m in MOD:
            s = resumen(fs, m)
            print(f"{etq:26s} {lead:4d} {s['n_ev']:4d} {s['n_con']:6d} {yr:8.5f} "
                  f"{m:16s} {s['brier_contrato']:12.5f} {s['brier_evento']:13.5f} "
                  f"{s['logloss_contrato']:10.5f} {s['logloss_evento']:10.5f}")


def main():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    obs = observaciones(con)
    FC = pronosticos(con)
    old, _, _, _ = poblacion(con, "backfill_2b_v1")
    new, _, _, _ = poblacion(con, "markets_v2")
    comunes = set(old) & set(new)
    nuevas = set(new) - set(old)
    print(f"fechas: OLD {len(old)}  CORRECTED {len(new)}  comunes {len(comunes)}  nuevas {len(nuevas)}")

    for lead in LEADS:
        fo = filas(old, obs, FC, lead)
        fn = filas(new, obs, FC, lead)
        fo_c = [r for r in fo if r["fecha"] in comunes]
        fn_c = [r for r in fn if r["fecha"] in comunes]
        fn_n = [r for r in fn if r["fecha"] in nuevas]
        tabla(f"C1 — AISLADA (primaria): solo las fechas comunes · lead {lead} h",
              [("OLD  (comunes)", fo_c), ("CORRECTED (comunes)", fn_c)])
        tabla(f"C2 — COMPLETA (confundida con la estacion) · lead {lead} h",
              [("OLD  (todo)", fo), ("CORRECTED (todo)", fn)])
        tabla(f"C3 — DESCOMPOSICION dentro de CORRECTED · lead {lead} h",
              [("CORRECTED comunes (40)", fn_c), ("CORRECTED nuevas (77)", fn_n)])

        print(f"\n--- escaleras presentes, lead {lead} h")
        for etq, fs in (("OLD todo", fo), ("CORRECTED todo", fn)):
            c = Counter(r["n_bandas"] for r in fs)
            ev = Counter()
            for r in fs: ev[(r["event_id"], r["n_bandas"])] = 1
            pe = Counter(k[1] for k in ev)
            print(f"    {etq:22s} contratos {dict(sorted(c.items()))}   eventos {dict(sorted(pe.items()))}")

        print(f"\n--- AUDITORIA DE PROBABILIDADES (punto 2), lead {lead} h")
        for etq, fs in (("OLD todo", fo), ("CORRECTED todo", fn)):
            for m in MOD:
                a = auditoria_p(fs, m)
                if not fs: continue
                frac = a["_logloss_de_recortados"] / a["_logloss_total"] if a["_logloss_total"] else 0.0
                print(f"    {etq:16s} {m:16s} p=0 {a['p_exactamente_0']:5d} (y=1 en {a['p0_con_y1']:3d})"
                      f"   p=1 {a['p_exactamente_1']:4d} (y=0 en {a['p1_con_y0']:3d})"
                      f"   recortados {a['recortados']:5d}   LL de recortados {frac*100:6.2f}%")
    con.close()


if __name__ == "__main__":
    main()
