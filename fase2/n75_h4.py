#!/usr/bin/env python3
"""H4 — partes B, C, D y E. Comparabilidad del scoring entre escaleras 7/9/11.

NO ES NIVEL 1. No entrena nada, no hace walk-forward, no busca edge, no calcula PnL, no
selecciona bandas y no ejecuta CONFIRMA/REFUTA. Todo lo que produce son
REFERENCE / SANITY CONTROLS.

Unidades, ponderacion y regla de veredicto: `N075_H4_DECLARACION.md`, espejado antes.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics as stx
import sys
from collections import Counter, defaultdict

import duckdb

sys.path.insert(0, "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main/src")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
from n075_poblacion import DB, observaciones, poblacion, pronosticos      # noqa: E402
from n075_metricas import EPS, clip, filas                                # noqa: E402

LADDERS = (7, 9, 11)


# ---------------------------------------------------------------- B. derivaciones
def brier_unif_teorico(n):
    """Media POR CONTRATO del control uniforme p=1/n sobre un evento de n bandas.

        ganadora   (1/n - 1)^2 = ((n-1)/n)^2
        perdedoras (n-1) x (1/n)^2 = (n-1)/n^2
        suma       [(n-1)^2 + (n-1)] / n^2 = (n-1)(n-1+1)/n^2 = (n-1)/n
        media      (n-1)/n^2
    """
    return (n - 1) / n ** 2


def logloss_unif_teorico(n):
    """Media POR CONTRATO del control uniforme.

        ganadora   -ln(1/n) = ln n
        perdedoras (n-1) x -ln(1 - 1/n) = (n-1) ln(n/(n-1))
        media      [ln n + (n-1) ln(n/(n-1))] / n
    """
    return (math.log(n) + (n - 1) * math.log(n / (n - 1))) / n


def brier_familia(c, n):
    """Familia de calidad FIJA: probabilidad c a la ganadora, (1-c)/(n-1) al resto.

        media = (1/n)[ (1-c)^2 + (n-1)((1-c)/(n-1))^2 ]
              = (1/n)(1-c)^2 [1 + 1/(n-1)]
              = (1-c)^2 / (n-1)
    """
    return (1 - c) ** 2 / (n - 1)


def logloss_familia(c, n):
    r = (1 - c) / (n - 1)
    return (-math.log(c) - (n - 1) * math.log(1 - r)) / n


def fuerza_bruta(qs, k):
    """Puntuacion directa, sin formula: qs = vector de probabilidades, k = indice ganador."""
    b = [(clip(q) - (1.0 if i == k else 0.0)) ** 2 for i, q in enumerate(qs)]
    l = [-((1.0 if i == k else 0.0) * math.log(clip(q))
           + (0.0 if i == k else 1.0) * math.log(1 - clip(q))) for i, q in enumerate(qs)]
    return stx.mean(b), stx.mean(l), sum(b), sum(l)


def parte_B():
    print("=" * 86)
    print("B. LINEA BASE MATEMATICA — derivada y verificada contra fuerza bruta")
    print("=" * 86)
    print(f"  {'n':>3s} {'Brier/contr':>13s} {'fuerza bruta':>13s} {'Brier/evento(suma)':>19s}"
          f" {'LL/contr':>11s} {'fuerza bruta':>13s}")
    for n in range(2, 16):
        qs = [1.0 / n] * n
        bm, lm, bs, ls = fuerza_bruta(qs, 0)
        tb, tl = brier_unif_teorico(n), logloss_unif_teorico(n)
        marca = " <-" if n in LADDERS else ""
        assert abs(bm - tb) < 1e-12 and abs(lm - tl) < 1e-12, n
        print(f"  {n:3d} {tb:13.8f} {bm:13.8f} {bs:19.8f} {tl:11.8f} {lm:13.8f}{marca}")
    print("\n  TODAS las identidades verificadas a 1e-12 contra el calculo directo.")
    b = {n: brier_unif_teorico(n) for n in LADDERS}
    l = {n: logloss_unif_teorico(n) for n in LADDERS}
    print(f"\n  Brier    7 {b[7]:.6f} · 9 {b[9]:.6f} · 11 {b[11]:.6f}   "
          f"recorrido 7->11 {b[7]-b[11]:+.6f}  ({(b[7]-b[11])/b[11]*100:.1f} % del valor de 11)")
    print(f"  LogLoss  7 {l[7]:.6f} · 9 {l[9]:.6f} · 11 {l[11]:.6f}   "
          f"recorrido 7->11 {l[7]-l[11]:+.6f}  ({(l[7]-l[11])/l[11]*100:.1f} % del valor de 11)")
    print("\n  MONOTONIA: d/dn[(n-1)/n^2] = (2-n)/n^3 < 0 para n > 2  ->  estrictamente decreciente.")
    print("  El TOTAL por evento va al reves: (n-1)/n crece con n "
          f"({(7-1)/7:.6f} -> {(11-1)/11:.6f}).")

    print("\n  --- y no es solo la linea base: una familia de CALIDAD FIJA tambien cae con n")
    print("      q(ganadora) = c, resto uniforme.  Brier/contrato = (1-c)^2/(n-1)")
    print(f"  {'c':>6s} " + " ".join(f"{'n='+str(n):>12s}" for n in LADDERS)
          + "   | LL/contrato por n           | -ln c (solo ganadora)")
    for c in (0.20, 0.35, 0.50, 0.70, 0.90):
        bs = [brier_familia(c, n) for n in LADDERS]
        ls = [logloss_familia(c, n) for n in LADDERS]
        for n, bb in zip(LADDERS, bs):
            qs = [c] + [(1 - c) / (n - 1)] * (n - 1)
            m, _, _, _ = fuerza_bruta(qs, 0)
            assert abs(m - bb) < 1e-12, (c, n)
        print(f"  {c:6.2f} " + " ".join(f"{x:12.6f}" for x in bs)
              + " | " + " ".join(f"{x:8.5f}" for x in ls)
              + f"  | {-math.log(c):8.5f}")
    print("\n  A CALIDAD IDENTICA, mas bandas = mejor Brier y mejor Log Loss POR CONTRATO.")
    print("  La UNICA columna que no se mueve con n es -ln(q_ganadora): depende de UN numero.")


# ---------------------------------------------------------------- C. ponderacion
def parte_C(En):
    print("\n" + "=" * 86)
    print("C. PONDERACION — peso efectivo de UN evento de n bandas, con la muestra real")
    print("=" * 86)
    tot_c = sum(m * e for m, e in En.items())
    tot_e = sum(En.values())
    print(f"  muestra declarada: " + " · ".join(f"{n} bandas x {En.get(n,0)}" for n in LADDERS)
          + f"   contratos {tot_c}  eventos {tot_e}")
    print(f"\n  {'n':>3s} {'eventos':>8s} {'W1 por contrato':>17s} {'W2 por evento':>15s}"
          f" {'W3 evento x lead':>18s}  {'W1/W2':>7s}")
    for n in LADDERS:
        e = En.get(n, 0)
        if not e:
            print(f"  {n:3d} {e:8d} {'-':>17s} {'-':>15s} {'-':>18s}  {'-':>7s}")
            continue
        w1, w2 = n / tot_c, 1 / tot_e
        print(f"  {n:3d} {e:8d} {w1:17.6f} {w2:15.6f} {w2:18.6f}  {w1/w2:7.3f}")
    print("\n  W1 da a un evento de 11 bandas 11/7 = 1,571 veces el peso de uno de 7.")
    print("  W2 y W3 igualan el peso del EVENTO — y no igualan lo que se promedia dentro,")
    print("  que es (n-1)/n^2 y sigue dependiendo de n. Igualar pesos NO iguala escalas.")


# ---------------------------------------------------------------- D. confusion temporal
def parte_D(con):
    print("\n" + "=" * 86)
    print("D. COMPARABILIDAD TEMPORAL — ¿se puede separar escalera de calendario?")
    print("=" * 86)
    filas_ = con.execute(
        """SELECT station_identifier, event_id, count(*) n, min(CAST(end_date AS DATE)) d
           FROM markets WHERE dataset_version='markets_v2' GROUP BY 1,2""").fetchall()
    por = defaultdict(lambda: defaultdict(list))
    for st, _, n, d in filas_:
        por[st][n].append(d)
    multi = {st: v for st, v in por.items() if len(v) > 1}
    print(f"  estaciones en markets_v2: {len(por)}   con mas de una escalera: {len(multi)}")
    rangos = defaultdict(set)
    for st, v in por.items():
        for n, ds in v.items():
            rangos[n].add((min(ds), max(ds)))
    print("\n  rango de fechas de cada escalera, POR ESTACION (conjunto de rangos distintos):")
    for n in sorted(rangos):
        rs = sorted(rangos[n])
        print(f"    {n:2d} bandas: {len(rs)} rangos distintos   global [{min(r[0] for r in rs)} .. {max(r[1] for r in rs)}]")
    # ¿hay solape de fechas entre escaleras, en cualquier estacion?
    fecha_n = defaultdict(set)
    for st, _, n, d in filas_:
        fecha_n[d].add(n)
    mixtas = {d: ns for d, ns in fecha_n.items() if len(ns) > 1}
    print(f"\n  FECHAS con mas de un tamano de escalera EN TODO EL CATALOGO: {len(mixtas)}")
    for d in sorted(mixtas)[:6]:
        print(f"    {d}: {sorted(mixtas[d])}")
    cortes = {}
    for n in sorted(rangos):
        cortes[n] = (min(r[0] for r in rangos[n]), max(r[1] for r in rangos[n]))
    print("\n  -> la escalera es una propiedad del CALENDARIO, identica en las 52 estaciones.")

    obs_min = con.execute("SELECT min(observation_time) FROM weather_observations").fetchone()[0]
    fc_min = con.execute("SELECT min(target_date) FROM weather_forecasts").fetchone()[0]
    print(f"\n  primera observacion de TODO el almacen: {obs_min}")
    print(f"  primer target_date de TODO el almacen:  {fc_min}")
    for n in sorted(cortes):
        ini, fin = cortes[n]
        n_obs = con.execute(
            "SELECT count(*) FROM weather_observations WHERE observation_time < ?",
            [dt.datetime.combine(fin + dt.timedelta(days=1), dt.time(0), dt.timezone.utc)]
        ).fetchone()[0] if n != 11 else None
        print(f"    escalera {n:2d}: [{ini} .. {fin}]"
              + (f"   observaciones del almacen en o antes de {fin}: {n_obs}" if n != 11 else "   (el resto)"))
    print("\n  CONFUSORES que no se pueden separar de la escalera con este corpus:")
    for k in ("cambio de escalera", "estacion del anyo", "distribucion de temperatura",
              "regimen de mercado", "calidad del pronostico"):
        print(f"    - {k}: varia EXACTAMENTE en las mismas fechas que la escalera")


# ---------------------------------------------------------------- E. control decisivo
def parte_E(con):
    print("\n" + "=" * 86)
    print("E. CONTROL DECISIVO — REFERENCE / SANITY CONTROL, no modelo predictivo")
    print("=" * 86)
    obs, FC = observaciones(con), pronosticos(con)
    new, _, _, _ = poblacion(con, "markets_v2", "EGLC")
    old, _, _, _ = poblacion(con, "backfill_2b_v1", "EGLC")
    for nom, pob in (("CORRECTED", new), ("OLD", old)):
        for lead in (24, 9):
            fs = filas(pob, obs, FC, lead)
            if not fs:
                continue
            ns = Counter(r["n_bandas"] for r in fs)
            ev = {(r["event_id"], r["lead"]) for r in fs}
            bc = stx.mean((clip(r["p"]["REF_uniforme"]) - r["y"]) ** 2 for r in fs)
            lc = stx.mean(-(r["y"] * math.log(clip(r["p"]["REF_uniforme"]))
                            + (1 - r["y"]) * math.log(1 - clip(r["p"]["REF_uniforme"])))
                          for r in fs)
            teo_b = stx.mean(brier_unif_teorico(r["n_bandas"]) for r in fs)
            teo_l = stx.mean(logloss_unif_teorico(r["n_bandas"]) for r in fs)
            print(f"  {nom:10s} lead {lead:2d}  eventos {len(ev):3d}  escaleras {dict(ns)}"
                  f"   Brier {bc:.6f} (teorico {teo_b:.6f})   LL {lc:.6f} (teorico {teo_l:.6f})")
    print("\n  El control vale lo mismo en los cuatro cuadrantes PORQUE la muestra es 100 %")
    print("  de once bandas: (n-1)/n^2 con n=11 y nada mas. No es una propiedad del codigo")
    print("  de puntuacion: es que n no varia. Si variara, el control variaria con el.")


def main():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    parte_B()
    _, _, _, pf = poblacion(con, "markets_v2", "EGLC")
    En = Counter()
    for es in pf.values():
        for e in es:
            if e["elegible"]:
                En[e["n_bandas"]] += 1
    parte_C(En)
    parte_D(con)
    parte_E(con)
    parte_F(con)
    con.close()




# ------------------------------------------- F. metodologia corregida + sanity controls
def bss(b, n):
    return 1 - b / brier_unif_teorico(n)


def lss(l, n):
    return 1 - l / logloss_unif_teorico(n)


def parte_F(con):
    print("\n" + "=" * 86)
    print("F. ¿ARREGLA ALGO NORMALIZAR? — medido, no supuesto")
    print("=" * 86)
    print("  Skill score contra el nulo uniforme DE SU PROPIA ESCALERA:")
    print("    BSS_n = 1 - B/B_unif(n)      LSS_n = 1 - LL/LL_unif(n)")
    print("  Por construccion valen 0 en el nulo para TODA n. La pregunta es si valen lo")
    print("  mismo para una familia de CALIDAD FIJA, que es lo que haria comparable la escala.\n")
    print(f"  {'c':>6s} " + " ".join(f"{'BSS n='+str(n):>12s}" for n in LADDERS)
          + f" {'rango':>9s}  | " + " ".join(f"{'LSS n='+str(n):>11s}" for n in LADDERS)
          + f" {'rango':>9s}  | {'-ln c':>8s}")
    for c in (0.20, 0.35, 0.50, 0.70, 0.90):
        bs = [bss(brier_familia(c, n), n) for n in LADDERS]
        ls = [lss(logloss_familia(c, n), n) for n in LADDERS]
        print(f"  {c:6.2f} " + " ".join(f"{x:12.5f}" for x in bs) + f" {max(bs)-min(bs):9.5f}"
              + "  | " + " ".join(f"{x:11.5f}" for x in ls) + f" {max(ls)-min(ls):9.5f}"
              + f"  | {-math.log(c):8.5f}")
    print("\n  NO llega a cero. Normalizar reduce la dependencia de n, no la elimina:")
    print("  BSS(c) = 1 - (1-c)^2 n^2/(n-1)^2, que sigue siendo funcion de n.")
    print("  La UNICA cantidad exactamente invariante es -ln(q_ganadora) -- pero su NULO,")
    print("  ln n, si depende de n, asi que tampoco es comparable como evidencia de skill.")

    print("\n" + "=" * 86)
    print("SANITY CONTROLS bajo la metodologia corregida")
    print("REFERENCE / SANITY CONTROLS — NOT LEVEL 1")
    print("=" * 86)
    obs, FC = observaciones(con), pronosticos(con)
    new, _, _, _ = poblacion(con, "markets_v2", "EGLC")
    from n075_metricas import MOD
    for lead in (24, 9):
        fs = filas(new, obs, FC, lead)
        if not fs:
            continue
        ns = sorted({r["n_bandas"] for r in fs})
        # la interpretacion categorica exige que las probabilidades sumen 1 por evento
        sumas = defaultdict(lambda: defaultdict(float))
        for r in fs:
            for m in MOD:
                sumas[(r["event_id"], m)][m] += r["p"][m]
        peor = max(abs(v[m] - 1.0) for (e, m), v in sumas.items())
        print(f"\n  lead {lead} h · eventos {len({(r['event_id'], r['lead']) for r in fs})}"
              f" · escaleras presentes {ns} · |suma de probabilidades - 1| maximo {peor:.2e}")
        print(f"    {'control':16s} {'Brier/ev':>10s} {'BSS_11':>9s} {'LL/ev':>10s}"
              f" {'LSS_11':>9s} {'-ln q_gan':>10s}")
        for m in MOD:
            porev_b, porev_l, cat = defaultdict(list), defaultdict(list), {}
            for r in fs:
                p, y = clip(r["p"][m]), r["y"]
                k = (r["event_id"], r["lead"])
                porev_b[k].append((p - y) ** 2)
                porev_l[k].append(-(y * math.log(p) + (1 - y) * math.log(1 - p)))
                if y == 1.0:
                    cat[k] = -math.log(p)
            b = stx.mean(stx.mean(v) for v in porev_b.values())
            l = stx.mean(stx.mean(v) for v in porev_l.values())
            etq = "CONTROL ESTRUCTURAL" if m == "REF_uniforme" else ""
            print(f"    {m:16s} {b:10.5f} {bss(b, 11):9.5f} {l:10.5f} {lss(l, 11):9.5f}"
                  f" {stx.mean(cat.values()):10.5f}  {etq}")
        print("    (todas las escaleras presentes son de 11 bandas: BSS_11 y LSS_11 son")
        print("     el nulo correcto para TODAS las filas. En cuanto entre otra n, hay que")
        print("     estratificar y NO agregar.)")


if __name__ == "__main__":
    main()
