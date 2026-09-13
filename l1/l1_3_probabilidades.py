#!/usr/bin/env python3
"""LEVEL 1 · L1.3 (puntos 4-7, 9, 10) — FORECAST -> P(YES), y sus propiedades.

NO evalua edge, precio, mispricing, PnL, umbrales, estrategia ni ejecucion.
NO calcula el veredicto de poder predictivo. NO compara contra precios de mercado.
NO selecciona modelos: las metricas que salen aqui son INSTRUMENTO (sensibilidad al
recorte), no resultado, y no se ordenan.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import statistics as stx
import sys
from collections import Counter

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/l1")
from n075_poblacion import DB, poblacion, pronosticos                      # noqa: E402
from l1_2_baselines import (MODELOS, construye, label_av,                  # noqa: E402
                            observaciones_c, tasof)

ST, DSV = "EGLC", "markets_v2"
EPS_DECLARADO = 1e-6                       # el de A-280, declarado antes de este guion
fallos: list[str] = []


def ok(c, etq, det=""):
    print(f"  {'OK ' if c else '!! '} {etq}" + (f"   {det}" if det else ""))
    if not c:
        fallos.append(etq)


def clip(p, eps):
    return min(max(p, eps), 1.0 - eps)


def puntua(filas, m, eps):
    """INSTRUMENTO, no resultado: sirve para medir la sensibilidad al recorte."""
    b, l = [], []
    for x in filas:
        pb = [(clip(p, eps) - y) ** 2 for p, y in zip(x["p"][m], x["y"])]
        pl = [-(y * math.log(clip(p, eps)) + (1 - y) * math.log(1 - clip(p, eps)))
              for p, y in zip(x["p"][m], x["y"])]
        b.append(stx.mean(pb)); l.append(stx.mean(pl))
    return stx.mean(b), stx.mean(l)


def main() -> int:
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    obs, zona = observaciones_c(con, ST)
    FC = pronosticos(con, ST)
    pob, _, _, _ = poblacion(con, DSV, ST)
    filas = {l: construye(con, pob, obs, FC, zona, l) for l in (24, 9)}

    # ---------------------------------------------------------------- 9. TEMPORAL
    print("=" * 94)
    print("PUNTO 9 — REGISTRO TEMPORAL. Cada P(YES) reconstruible con information_time <= t_asof")
    print("=" * 94)
    print(f"  {'lead':>4s} {'issue_time':>12s} {'available_at':>14s} {'prediction_time':>17s}"
          f" {'margen':>8s} {'train cutoff':>14s}")
    for lead in (24, 9):
        x = filas[lead][len(filas[lead]) // 2]
        td = x["td"]
        av = FC[(td, lead)][0]
        iss = con.execute("""SELECT issue_time FROM weather_forecasts WHERE station=?
             AND target_date=? AND available_at=?""", [ST, td, av]).fetchone()[0]
        t = tasof(td, lead)
        print(f"  {lead:4d} {iss:%m-%d %H:%MZ} {av:%m-%d %H:%M:%SZ} {t:%m-%d %H:%MZ}"
              f" {(t-av).total_seconds()/3600:7.2f}h {str(x['train_max']):>14s}")
    print(f"\n  ejemplo mostrado: target {filas[24][len(filas[24])//2]['td']}")
    print("  ADVERTENCIA MANTENIDA: available_at = issue_time + 4:45:36 es una HIPOTESIS")
    print("  OPERACIONAL NO VALIDADA EXTERNAMENTE. No se modifica retrospectivamente (tarea #75).")
    for lead in (24, 9):
        ok(all(FC[(x["td"], lead)][0] <= tasof(x["td"], lead) for x in filas[lead]),
           f"lead {lead}: available_at <= t_asof en los {len(filas[lead])} eventos")
        ok(all(label_av(x["train_max"], zona) <= tasof(x["td"], lead) for x in filas[lead]),
           f"lead {lead}: train cutoff con etiqueta disponible en t_asof")

    # ---------------------------------------------------------------- 7. PROBABILIDADES
    print(f"\n{'=' * 94}")
    print("PUNTO 7 — PROBABILIDADES: suma, rango, y DIRECCION ante una perturbacion")
    print("=" * 94)
    for lead in (24, 9):
        peor = max(abs(sum(x["p"][m]) - 1.0) for x in filas[lead] for m in MODELOS)
        ok(peor <= 1e-12, f"lead {lead}: suman 1 con tolerancia <= 1e-12", f"maximo {peor:.2e}")
        malos = [1 for x in filas[lead] for m in MODELOS for p in x["p"][m] if not 0.0 <= p <= 1.0]
        ok(not malos, f"lead {lead}: 0 <= p <= 1 ANTES del recorte", f"{len(malos)} fuera")
        malos2 = [1 for x in filas[lead] for m in MODELOS for p in x["p"][m]
                  if not 0.0 <= clip(p, EPS_DECLARADO) <= 1.0]
        ok(not malos2, f"lead {lead}: 0 <= p <= 1 DESPUES del recorte")

    print("\n  -- DIRECCION: subir el pronostico debe mover masa a las bandas ALTAS --")
    #: SOLO el pronostico DEL DIA OBJETIVO. La primera version de esta prueba desplazaba
    #: TODOS los pronosticos, incluidos los del entrenamiento, y entonces los errores
    #: empiricos se desplazan al reves y `round((f+d) + (e-d)) = round(f+e)`: el
    #: desplazamiento se cancela EXACTO y la prueba medía cero. El defecto estaba en la
    #: prueba, no en el modelo -- y de paso deja dicha una propiedad real de B4: es
    #: INVARIANTE a un sesgo constante de TODOS los pronosticos, porque la distribucion
    #: empirica de error lo absorbe.
    lead = 24
    subidas = bajadas = 0
    for delta in (+3.0, -3.0):
        f2 = []
        for x in filas[lead]:
            FC2 = dict(FC); FC2[(x["td"], lead)] = (FC[(x["td"], lead)][0],
                                                    FC[(x["td"], lead)][1] + delta)
            f2 += construye(con, {x["td"]: pob[x["td"]]}, obs, FC2, zona, lead)
        base = {x["td"]: x for x in filas[lead]}
        mov = []
        for x in f2:
            b = base[x["td"]]
            ev = pob[x["td"]]
            #: centro de masa en indice de banda, ordenado de frio a caliente
            idx = sorted(range(len(ev["bandas"])),
                         key=lambda i: (-1e9 if ev["bandas"][i][0] is None else ev["bandas"][i][0]))
            cm = lambda p: sum(k * p[i] for k, i in enumerate(idx))
            mov.append(cm(x["p"]["B4_fc_prob"]) - cm(b["p"]["B4_fc_prob"]))
        med = stx.mean(mov)
        print(f"    forecast {delta:+.1f} C  ->  centro de masa de B4 se mueve {med:+.3f} bandas"
              f"   (mismo signo en {sum(1 for v in mov if v*delta > 0)} de {len(mov)})")
        if delta > 0:
            subidas = med
        else:
            bajadas = med
    ok(subidas > 0 and bajadas < 0,
       "subir el pronostico sube la masa y bajarlo la baja: la direccion es la esperada")

    # ---------------------------------------------------------------- 6. EPSILON
    print(f"\n{'=' * 94}")
    print("PUNTO 6 — SENSIBILIDAD AL RECORTE. Brier y Log Loss POR SEPARADO")
    print("INSTRUMENTO, no resultado: no se ordenan modelos ni se elige epsilon por el numero")
    print("=" * 94)
    EPSS = [1e-8, 1e-6, 1e-4, 1e-3, 1e-2]
    for lead in (24,):
        print(f"\n  lead {lead} h · {len(filas[lead])} eventos\n")
        print(f"  {'modelo':16s} {'Brier':>9s} | " + " ".join(f"{'LL@'+f'{e:.0e}':>11s}" for e in EPSS)
              + "   sensibilidad")
        for m in MODELOS:
            b0, _ = puntua(filas[lead], m, EPS_DECLARADO)
            lls = [puntua(filas[lead], m, e)[1] for e in EPSS]
            br = [puntua(filas[lead], m, e)[0] for e in EPSS]
            rangoB = max(br) - min(br)
            rangoL = max(lls) - min(lls)
            print(f"  {m:16s} {b0:9.5f} | " + " ".join(f"{x:11.5f}" for x in lls)
                  + f"   LL varia {rangoL:6.3f} · Brier {rangoB:.2e}")
        print("\n  Brier es practicamente INSENSIBLE al recorte. Log Loss NO.")
        print("  Y en B1/B2/B3 el Log Loss es ARITMETICA DEL RECORTE, no calibracion:")
        n = filas[lead][0]["n"]
        for m in ("B1_persist", "B2_fc_crudo", "B3_fc_sesgo"):
            fall = sum(1 for x in filas[lead]
                       if x["p"][m][x["y"].index(1.0)] == 0.0)
            #: FORMULA EXACTA, no aproximada. Por evento fallado: la ganadora tiene p=0
            #: (recortada a eps) y la elegida tiene p=1 con y=0 (recortada a 1-eps), las
            #: dos aportan -ln(eps); las n-2 restantes aportan -ln(1-eps). Por evento
            #: acertado: las n bandas aportan -ln(1-eps).
            N = len(filas[lead]); e = EPS_DECLARADO
            pred = (fall * (2 * -math.log(e) + (n - 2) * -math.log(1 - e))
                    + (N - fall) * n * -math.log(1 - e)) / (N * n)
            real = puntua(filas[lead], m, e)[1]
            print(f"    {m:16s} fallos {fall:3d}/{N}  formula exacta = {pred:.8f}  "
                  f"medido {real:.8f}  {'IDENTICO' if abs(pred-real) < 1e-10 else 'DIFIERE'}"
                  f"  (delta {abs(pred-real):.1e}, acumulacion en coma flotante sobre "
                  f"{N*n} terminos)")
        print("\n  -> el Log Loss de los deterministas es artificialmente DESFAVORABLE y su")
        print("     magnitud la fija epsilon, no el modelo. Se reporta, no se compara.")

    # ---------------------------------------------------------------- 10. PROXY
    print(f"\n{'=' * 94}")
    print("PUNTO 10 — SENSIBILIDAD AL PROXY (medicion, no modelo)")
    print("=" * 94)
    print("  T_WU  temperatura contractual real       NO existe serie historica independiente")
    print("  T_IEM proxy observado (METAR de IEM)     es lo que tenemos")
    print("  C     winning_outcome                    la ETIQUETA; NO se sustituye por B")
    print("\n  acuerdo proxy <-> resolucion (A-276):  136 coinciden · 1 discrepa · 50 sin observacion")
    print(f"    tasa medida de discrepancia: 1/137 = {100/137:.2f} %")
    print("\n  IMPACTO MAXIMO de una discrepancia de ±1 C:")
    print("    con bandas de 1 C, ±1 C mueve la banda SIEMPRE: el impacto por evento afectado")
    print("    es TOTAL. Lo que acota el dano es la TASA, no la magnitud.")
    lead = 24
    n_ev = len(filas[lead])
    print(f"    si la tasa real fuese la medida (0,73 %): ~{n_ev*0.0073:.1f} de {n_ev} eventos")
    print(f"    si fuese diez veces peor (7,3 %):        ~{n_ev*0.073:.1f} de {n_ev} eventos")
    e_base = []
    for td in sorted(pob):
        if td in obs and (td, lead) in FC:
            e_base.append(obs[td] - FC[(td, lead)][1])
    print(f"\n  efecto sobre la distribucion empirica de error (lo que alimenta B4):")
    print(f"    bias actual {stx.mean(e_base):+.4f} C sobre {len(e_base)} pares")
    for k in (1, 10):
        shift = k * 1.0 / len(e_base)
        print(f"    si {k} par{'es' if k > 1 else ''} estuviera mal por +1 C: el bias se mueve "
              f"{shift:+.4f} C  ({100*shift/abs(stx.mean(e_base)):.1f} % del bias)")
    print("\n  NO se corrige el desacuerdo IEM/Wunderground aqui. Queda cuantificado.")

    con.close()
    print(f"\n{'=' * 94}")
    print("RESULTADO:", "TODAS LAS COMPROBACIONES PASAN" if not fallos else f"FALLAN {fallos}")
    print("=" * 94)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
