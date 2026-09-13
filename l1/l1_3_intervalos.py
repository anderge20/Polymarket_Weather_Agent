#!/usr/bin/env python3
"""LEVEL 1 · L1.3 (punto 3 y 8) — INTERVALOS CONTRACTUALES Y FRONTERAS.

Reconstruye los intervalos de CADA escalera y prueba exhaustivamente que particionan.
No asume que 7/9/11 sean equivalentes: se prueba cada una por separado.

No evalua edge, precio, mispricing, PnL, umbrales, estrategia ni ejecucion.
"""
from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
from weather_agent.polymarket.resolution import parse_band                # noqa: E402
from n075_poblacion import DB                                             # noqa: E402

fallos: list[str] = []


def ok(c, etq, det=""):
    print(f"  {'OK ' if c else '!! '} {etq}" + (f"   {det}" if det else ""))
    if not c:
        fallos.append(etq)


def dentro(g, lo, hi):
    """LA REGLA DE PERTENENCIA, tal cual la usan los baselines. `g` es un ENTERO."""
    return (lo is None or g >= lo) and (hi is None or g <= hi)


def main() -> int:
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")

    print("=" * 92)
    print("PUNTO 3 — INTERVALOS CONTRACTUALES, POR ESCALERA Y POR SEPARADO")
    print("=" * 92)

    ev = defaultdict(list)
    meta = {}
    for eid, banda, unidad, n in con.execute(
            """SELECT m.event_id, o.band_label, m.unit, count(*) OVER (PARTITION BY m.event_id)
               FROM markets m JOIN outcomes o
                 ON o.market_id = m.market_id AND o.dataset_version = m.dataset_version
               WHERE m.station_identifier='EGLC' AND m.dataset_version='markets_v2'
                 AND o.outcome_label='Yes' AND o.band_label IS NOT NULL""").fetchall():
        lo, hi = parse_band(banda, unidad)
        ev[eid].append((lo, hi, banda))
        meta[eid] = (unidad, n)

    por_n = defaultdict(list)
    for eid, bs in ev.items():
        por_n[len(bs)].append(eid)

    for n in sorted(por_n):
        eids = por_n[n]
        print(f"\n{'-' * 92}\nESCALERA DE {n} BANDAS · {len(eids)} eventos\n{'-' * 92}")
        eid0 = sorted(eids)[0]
        bs = sorted(ev[eid0], key=lambda b: (-1e9 if b[0] is None else b[0]))
        print(f"  ejemplo (event {eid0}, unidad {meta[eid0][0]}):")
        for lo, hi, lbl in bs:
            ab = ("(-inf" if lo is None else f"[{lo:g}")
            ar = ("+inf)" if hi is None else f"{hi:g}]")
            print(f"    {lbl:22s}  ->  {ab}, {ar}")

        # (1) sin solapamientos  (2) sin huecos  (3) todo entero en EXACTAMENTE una banda
        sol = hue = malos = 0
        rango_min, rango_max = 10**9, -10**9
        for eid in eids:
            b = ev[eid]
            cer = sorted((lo, hi) for lo, hi, _ in b if lo is not None and hi is not None)
            ab = [x for x in b if x[0] is None]
            ar = [x for x in b if x[1] is None]
            if len(ab) != 1 or len(ar) != 1:
                malos += 1
                continue
            inf, sup = ab[0][1], ar[0][0]
            rango_min = min(rango_min, int(inf)); rango_max = max(rango_max, int(sup))
            # solapes y huecos sobre los ENTEROS del tramo cerrado
            esperado = list(range(int(inf) + 1, int(sup)))
            visto = [int(a) for a, _ in cer]
            if visto != esperado:
                if len(set(visto)) != len(visto):
                    sol += 1
                else:
                    hue += 1
            # exhaustivo: todo entero de -60 a +80 cae en EXACTAMENTE una banda
            for g in range(-60, 81):
                c = sum(1 for lo, hi, _ in b if dentro(g, lo, hi))
                if c != 1:
                    malos += 1
                    break
        ok(sol == 0, f"{n} bandas · sin solapamientos", f"{sol} eventos con solape")
        ok(hue == 0, f"{n} bandas · sin huecos", f"{hue} eventos con hueco")
        ok(malos == 0,
           f"{n} bandas · TODO entero de -60 a +80 cae en EXACTAMENTE una banda",
           f"{malos} eventos fallan")
        print(f"  tramo cerrado observado: enteros {rango_min+1} .. {rango_max-1}")

    print(f"\n{'=' * 92}")
    print("PUNTO 8 — FRONTERAS. La particion es sobre ENTEROS, y eso hay que decirlo")
    print("=" * 92)
    b = ev[sorted(por_n[11])[0]]
    ab = next(x for x in b if x[0] is None); ar = next(x for x in b if x[1] is None)
    inf, sup = int(ab[1]), int(ar[0])
    print(f"  escalera de prueba: <= {inf} · {inf+1}..{sup-1} sueltos · >= {sup}")
    casos = [
        ("limite inferior exacto", inf, ab[2]),
        ("limite inferior + 1", inf + 1, None),
        ("limite superior exacto", sup, ar[2]),
        ("limite superior - 1", sup - 1, None),
        ("muy por debajo", -40, ab[2]),
        ("muy por encima", 60, ar[2]),
        ("cero", 0, ab[2]),
        ("negativo", -5, ab[2]),
    ]
    for etq, g, esp in casos:
        hit = [lbl for lo, hi, lbl in b if dentro(g, lo, hi)]
        ok(len(hit) == 1 and (esp is None or hit[0] == esp),
           f"entero {etq:24s} g={g:4d} -> {hit[0] if hit else 'NINGUNA'}",
           "" if esp is None else f"esperado {esp}")

    print("\n  -- LOS REALES NO ESTAN PARTICIONADOS, Y NO TIENEN QUE ESTARLO --")
    for g in (12.5, 13.4, 13.5, 13.6):
        hit = [lbl for lo, hi, lbl in b if dentro(g, lo, hi)]
        print(f"    valor REAL {g:5.2f}  cae en {len(hit)} banda(s): {hit}")
    print("    -> la pertenencia se evalua sobre round(valor), no sobre el real.")
    print("       `round()` es PARTE de la interpretacion del contrato, no un detalle.")

    print("\n  -- ±0,01 ALREDEDOR DE UN LIMITE DE REDONDEO --")
    for g in (13.49, 13.50, 13.51, 14.49, 14.50, 14.51):
        r = round(g)
        hit = [lbl for lo, hi, lbl in b if dentro(r, lo, hi)]
        print(f"    {g:6.2f} -> round {r:3d} -> {hit[0]}")
    print("\n  -- EL EMPATE EXACTO: Python redondea a PAR, no 'medio arriba' --")
    for g in (12.5, 13.5, 14.5, 15.5, 16.5, -0.5, -1.5):
        print(f"    round({g:6.2f}) = {round(g):4d}   ('medio arriba' daria "
              f"{int(g + 0.5) if g >= 0 else int(g - 0.5):4d})")
    ok(round(13.5) == 14 and round(14.5) == 14,
       "confirmado: redondeo bancario (a par) en los empates exactos")
    print("     CUANTIFICADO en el guion de probabilidades: cuantos empates exactos ocurren.")

    print("\n  -- UNIDADES: esta escalera es C; las de F se prueban aparte --")
    uds = Counter(meta[e][0] for e in ev)
    print(f"    unidades de los eventos de EGLC: {dict(uds)}")
    ok(set(uds) == {"C"}, "EGLC es enteramente Celsius: no hay conversion que probar aqui")

    con.close()
    print(f"\n{'=' * 92}")
    print("RESULTADO:", "INTERVALOS Y FRONTERAS VERIFICADOS" if not fallos else f"FALLAN {fallos}")
    print("=" * 92)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
