#!/usr/bin/env python3
"""Las constantes de resultado de L1/postl1, DERIVADAS y contrastadas con el literal.

POR QUE ESTE GUION EXISTE Y NO UN PARCHE. Los guiones de L1 estan publicados y su
`sha256` esta citado en los locks (`LOCK_L1_5.md` fija el de `l1_4_walkforward.py`,
`PREREG_LEVEL1.md` el de `n075_poblacion.py`). Reescribirlos por limpieza, sin que cambie
un solo numero, rompe la trazabilidad a cambio de nada. Asi que el remedio es ADITIVO:
aqui se deriva cada constante y se exige que coincida con el literal que quedo escrito.

QUE SE ESTA VIGILANDO, que no es la aritmetica sino la ESCALERA. `10/121` lleva el `n=11`
a la vista; `0.30464` lo lleva escondido. Si alguna vez se puntua una escalera de 9 o de 7,
el primero se vera mal a simple vista y el segundo no. A-280 convirtio en regla permanente
"estratificar SIEMPRE por n, no agregar nunca entre escaleras": un literal que supone n=11
en silencio es justo el peligro por el que esa regla existe.

Sale 1 si alguna constante no reproduce. No lee la base de datos ni gasta cuota.
"""
from __future__ import annotations

import math

N = 11                      # la escalera de TODO lo puntuable en L1, Fase C y el conjunto
fallos: list[str] = []


def ok(etq, derivado, literal, dec=5):
    bien = round(derivado, dec) == literal
    print(f"  {'OK ' if bien else '!! '} {etq:46s} derivado {derivado:.6f}  "
          f"literal {literal}  ({'coincide' if bien else 'NO COINCIDE'})")
    if not bien:
        fallos.append(etq)


def brier_uniforme(n: int) -> float:
    """Brier por CONTRATO del predictor 1/n con una sola ganadora: (n-1)/n^2."""
    p = 1.0 / n
    return (1 / n) * (1 - p) ** 2 + ((n - 1) / n) * p ** 2


def logloss_uniforme(n: int) -> float:
    """Log-loss BINARIA por CONTRATO del predictor 1/n, promediada sobre las n bandas."""
    p = 1.0 / n
    return -(1 / n) * math.log(p) - ((n - 1) / n) * math.log(1 - p)


def main() -> int:
    print("=" * 92)
    print(f"CONSTANTES DE RESULTADO · derivadas para n = {N} y contrastadas con el literal")
    print("=" * 92)

    ok("Brier uniforme  (l1_4 y l1_5: `10/121`)", brier_uniforme(N), round(10 / 121, 5))
    ok("Brier uniforme  (faseA/faseC: `UNIF = 10/121`)", brier_uniforme(N), round(10 / 121, 5))
    #: l1_4_walkforward.py:87  ->  math.log(11)*0 + 0.30464
    #: l1_5_calibracion.py:137 ->  0.30464
    #: El `math.log(11)*0 +` del primero es ARITMETICA MUERTA: vale cero y no deriva nada.
    #: Viste el literal de una procedencia que no tiene, que es la version en miniatura de
    #: "una cita correcta sosteniendo una afirmacion falsa".
    ok("log-loss uniforme (l1_4 y l1_5: `0.30464`)", logloss_uniforme(N), 0.30464)
    #: l1_3_probabilidades.py:188 -> n_ev * 0.0073, con `100/137` derivado UNA LINEA ANTES.
    ok("tasa de discrepancia proxy/resolucion `0.0073`", 1 / 137, 0.0073, dec=4)

    print("\n  y lo que NO es 0,30464, para que nadie lo confunda:")
    print(f"     -log(1/{N}) (entropia de la uniforme sobre bandas) = {-math.log(1/N):.5f}")
    print(f"     log-loss del acierto seguro                        = 0.00000")

    print("\n" + "=" * 92)
    if fallos:
        print(f"FALLA — {len(fallos)} constantes no reproducen")
        for f in fallos:
            print(f"   !! {f}")
    else:
        print(f"PASA — las 4 constantes reproducen desde su derivacion, con n = {N}")
        print("Si algun dia se puntua una escalera distinta, este guion es donde se ve.")
    print("=" * 92)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
