#!/usr/bin/env python3
"""R30 §5.5 — contraste de calibracion del MERCADO, ejecutado tal como se congelo.

Preinscripcion: PREREG_R30_PUERTA_SUSTRATO.md  0a5b794e6563...  + enmiendas A-K.
Nada de lo que sigue elige un umbral: todos vienen del documento.

  §0/C      precio_bin(p_mid) = min(int(p_mid*10), 9)
  §5.5(a)   d_b = f_b - media(p_mid)_b            unidad de analisis: el EVENTO
  §5.5(b)   IC bootstrap POR BLOQUES SOBRE EVENTOS
  §5.4(C)   familia = los precio_bin con >= 150 EVENTOS post-borrado
  §5.5(e)   un intervalo que no llegue: NO EVALUABLE POR POTENCIA, con su n a la vista
  §5.5(c/K+L) T = max_b |d_b| sobre los EVALUABLES; nula = por cada grupo de
            PARTICION una banda ganadora con probabilidad proporcional a los
            p_mid; >= 10 000 replicas; mal calibrado si p < 0,05
  §5.5(c/L) la unidad de la particion es (EVENTO, LEAD), no el evento
  §5.5(f/L) ambito del contraste: grupos con suma de p_mid >= 0,50. Se publican
            LAS DOS poblaciones; la completa SIN p-valor, porque su nula no
            esta definida sobre ella
  §5.5(d/J) y mal calibrado no es explotable: hace falta |d_b| > MEDIA del
            semidiferencial del intervalo + fees D19. Se reportan las DOS cifras.
  §5.3      el signo del intervalo del maximo sobrevive los dos borrados

LA UNIDAD, y por que esta asi. `f_b` es frecuencia sobre FILAS y la estructura de
evento entra por donde el documento dice que entra: los bloques del bootstrap y una
nula que sortea UN ganador por evento. La lectura alternativa —promediar dentro del
intervalo por evento— la descarta el propio §5.5(c): la nula produce `won` por
banda, y observado y nula tienen que calcularse igual. Donde el documento quiso una
agregacion la nombro (§5.2: «la SUMA de sus bandas»); aqui no la nombra.
La potencia y el bootstrap SI cuentan eventos, que es donde estaba mi error de anoche.
"""
import json, os, random, statistics, sys
from collections import defaultdict

POBLACION = __import__("sys").argv[1] if len(__import__("sys").argv) > 1 else "particion"
SEED = 20260912
N_BOOT = 10_000
N_NULL = 10_000
UMBRAL_EVENTOS = 150          # §4.2 (A+B), §5.4 (C), §5.5(e)
ALFA = 0.05                   # §5.5(c) K

# Enmienda F, tabla MEDIDA del semidiferencial por intervalo (columna «media»).
SEMIDIF_MEDIA = {0: 0.0065, 1: 0.0147, 2: 0.0200, 3: 0.0126, 4: 0.0110,
                 5: 0.0102, 6: 0.0126, 7: 0.0205, 8: 0.0146, 9: 0.0066}
SEMIDIF_MEDIANA = {0: 0.0050, 1: 0.0100, 2: 0.0100, 3: 0.0100, 4: 0.0100,
                   5: 0.0100, 6: 0.0100, 7: 0.0100, 8: 0.0100, 9: 0.0050}

def fee_d19(p):
    """D19: c_taker(p) = rate * p * (1-p), rate 0.05, solo taker, hold-to-resolution."""
    return 0.05 * p * (1.0 - p)

def pbin(p):
    return min(int(p * 10), 9)

def curva(rows):
    """f_b, media(p_mid)_b y d_b por intervalo, sobre las filas dadas."""
    por = defaultdict(lambda: [0.0, 0.0, 0])
    for r in rows:
        a = por[r["_b"]]
        a[0] += r["won"]; a[1] += r["p_mid"]; a[2] += 1
    return {b: ((a[0]/a[2]) - (a[1]/a[2]), a[0]/a[2], a[1]/a[2], a[2])
            for b, a in por.items()}

def grupos_por_bin(rows):
    """§5.5(e) y la ocupacion de §5.4 se cuentan en EVENTOS (§4.2, y enmienda M).

    L escribio que se contaran en grupos (evento, lead). No se sigue de su propio
    hallazgo y afloja: los dos plazos de un evento son la misma estacion, el mismo
    dia y el mismo tiempo. Con grupos la familia sube a [0,1,2,3,4]; con eventos
    sigue en [0,1,2]. La PARTICION de la nula si es (evento, lead) -- son papeles
    distintos y L uso la palabra «bloque» para los dos.
    """
    por = defaultdict(set)
    for r in rows:
        por[r["_b"]].add(r["event_id"])
    return {b: len(s) for b, s in por.items()}

def main():
    rows = json.load(open(os.path.expanduser("~/pmw-e2/R30_ROWS.json")))
    for r in rows:
        r["_b"] = pbin(r["p_mid"])
    rng = random.Random(SEED)

    # §5.5(c/L): el bloque y la particion son (evento, lead)
    por_evento = defaultdict(list)
    for r in rows:
        por_evento[(r["event_id"], r["lead_h"])].append(r)
    eventos = list(por_evento)

    print(f"filas {len(rows)}   grupos (evento,lead) {len(eventos)}")
    # §5.5(f/L): ambito
    suma = {k: sum(x["p_mid"] for x in v) for k, v in por_evento.items()}
    dentro = {k for k in por_evento if suma[k] >= 0.50}
    print(f"§5.5(f/L) ambito suma p_mid >= 0,50: {len(dentro)} grupos, "
          f"{sum(len(por_evento[k]) for k in dentro)} filas   "
          f"(fuera {len(eventos)-len(dentro)} grupos, "
          f"{len(rows)-sum(len(por_evento[k]) for k in dentro)} filas)")
    if POBLACION == "particion":
        rows = [x for k in dentro for x in por_evento[k]]
        por_evento = {k: v for k, v in por_evento.items() if k in dentro}
        eventos = list(por_evento)
        print(f"--> se calcula sobre la POBLACION DE PARTICION: {len(rows)} filas, "
              f"{len(eventos)} grupos")
    else:
        print("--> se calcula sobre la POBLACION COMPLETA, SIN p-valor "
              "(§5.5(f/L): su nula no esta definida)")
    # Contado DESPUES de aplicar el ambito, que es lo unico que tiene sentido
    # imprimir aqui: la version anterior lo calculaba antes y escribia
    # «734 de 726», un numero imposible sobre una poblacion de 726 grupos.
    ganadores = [sum(x["won"] for x in v) for v in por_evento.values()]
    print(f"grupos con exactamente 1 banda ganadora: "
          f"{sum(1 for g in ganadores if g == 1)} de {len(eventos)}  "
          f"(0 ganadores: {sum(1 for g in ganadores if g == 0)}, "
          f">1: {sum(1 for g in ganadores if g > 1)})")
    assert all(g <= 1 for g in ganadores), (
        "algun grupo tiene mas de un ganador: la nula de §5.5(c) no esta "
        "definida sobre esta poblacion y no se puede continuar")

    # --- poblaciones de borrado de §5.3, contadas en EVENTOS ---------------
    ev_est = defaultdict(set); ev_mes = defaultdict(set)
    for r in rows:
        ev_est[r["station"]].add(r["event_id"])
        ev_mes[str(r["target_date"])[:7]].add(r["event_id"])
    est_mayor = max(ev_est, key=lambda k: len(ev_est[k]))
    mes_mayor = max(ev_mes, key=lambda k: len(ev_mes[k]))
    print(f"\nborrado §5.3, por EVENTOS (enmienda M) — no por filas:")
    print(f"  estacion de mayor peso: {est_mayor}  "
          f"{len(ev_est[est_mayor])} eventos")
    print(f"  mes de mayor peso:      {mes_mayor}  "
          f"{len(ev_mes[mes_mayor])} eventos")
    sin_est = [r for r in rows if r["station"] != est_mayor]
    sin_mes = [r for r in rows if str(r["target_date"])[:7] != mes_mayor]

    # --- §5.5(e) + §5.4(C): ocupacion en EVENTOS sobre las tres poblaciones -
    oc_tot = grupos_por_bin(rows)
    oc_est = grupos_por_bin(sin_est)
    oc_mes = grupos_por_bin(sin_mes)
    c = curva(rows)
    print(f"\n{'bin':>4}{'filas':>8}{'eventos':>9}{'ev-est':>8}{'ev-mes':>8}"
          f"{'f_b':>9}{'p_mid_b':>9}{'d_b':>9}   veredicto")
    evaluables = []
    for b in range(10):
        if b not in c:
            print(f"{b:>4}{0:>8}{0:>9}{0:>8}{0:>8}{'—':>9}{'—':>9}{'—':>9}   VACIO")
            continue
        d, f, p, n = c[b]
        e0, e1, e2 = oc_tot.get(b,0), oc_est.get(b,0), oc_mes.get(b,0)
        ok = min(e0, e1, e2) >= UMBRAL_EVENTOS
        if ok:
            evaluables.append(b)
        print(f"{b:>4}{n:>8}{e0:>9}{e1:>8}{e2:>8}{f:>9.4f}{p:>9.4f}{d:>+9.4f}   "
              f"{'EVALUABLE' if ok else 'NO EVALUABLE POR POTENCIA'}")
    print(f"\nfamilia §5.4 (>= {UMBRAL_EVENTOS} EVENTOS en las TRES poblaciones): "
          f"{evaluables if evaluables else 'VACIA'}")
    if not evaluables:
        print("\nSin intervalos evaluables el contraste de §5.5(c) no se ejecuta.")
        return 0

    # --- §5.5(b): IC bootstrap por bloques sobre EVENTOS ---------------------
    print(f"\nIC 95 % por bloques sobre EVENTOS (enmienda M), {N_BOOT} replicas:")
    por_ev_solo = defaultdict(list)
    for r in rows:
        por_ev_solo[r["event_id"]].append(r)
    bloques = list(por_ev_solo)
    boots = {b: [] for b in evaluables}
    for _ in range(N_BOOT):
        muestra = [x for e in rng.choices(bloques, k=len(bloques)) for x in por_ev_solo[e]]
        cb = curva(muestra)
        for b in evaluables:
            boots[b].append(cb[b][0] if b in cb else float("nan"))
    ic = {}
    for b in evaluables:
        v = sorted(x for x in boots[b] if x == x)
        ic[b] = (v[int(0.025*len(v))], v[int(0.975*len(v))])
        d = c[b][0]
        umbral = SEMIDIF_MEDIA[b] + fee_d19(c[b][2])
        print(f"  bin {b}:  d_b = {d:+.4f}   IC [{ic[b][0]:+.4f}, {ic[b][1]:+.4f}]   "
              f"excluye 0: {'SI' if ic[b][0]*ic[b][1] > 0 else 'no'}")
        print(f"          §5.5(d/J)  |d_b| = {abs(d):.4f}   umbral = "
              f"{SEMIDIF_MEDIA[b]:.4f} (media) + {fee_d19(c[b][2]):.4f} (fees D19) "
              f"= {umbral:.4f}   ->  {'SUPERA' if abs(d) > umbral else 'NO supera'}")
        print(f"          (mediana del semidiferencial {SEMIDIF_MEDIANA[b]:.4f}, "
              f"media {SEMIDIF_MEDIA[b]:.4f}, n filas del intervalo {c[b][3]})")

    # --- §5.5(c/K): T = max|d_b| y la nula que respeta la particion ----------
    if POBLACION != "particion":
        print("\n§5.5(c) NO se ejecuta sobre la poblacion completa: la nula sortea "
              "un ganador por grupo y 1 837 de 2 571 grupos no tienen ninguno.")
        return 0
    T_obs = max(abs(c[b][0]) for b in evaluables)
    b_max = max(evaluables, key=lambda b: abs(c[b][0]))
    print(f"\nT observado = max_b |d_b| = {T_obs:.4f}   (intervalo {b_max})")

    pesos = {}
    for e, v in por_evento.items():
        s = sum(x["p_mid"] for x in v)
        pesos[e] = [x["p_mid"]/s for x in v] if s > 0 else None
    ge = 0
    for _ in range(N_NULL):
        sim = []
        for e, v in por_evento.items():
            w = pesos[e]
            if w is None:
                continue
            k = rng.choices(range(len(v)), weights=w, k=1)[0]
            for i, x in enumerate(v):
                sim.append({"_b": x["_b"], "p_mid": x["p_mid"], "won": 1.0 if i == k else 0.0})
        cs = curva(sim)
        ge += (max(abs(cs[b][0]) for b in evaluables if b in cs) >= T_obs)
    p_val = (ge + 1) / (N_NULL + 1)
    print(f"nula «el mercado esta calibrado», {N_NULL} replicas:  "
          f"p = {p_val:.4f}   ->  {'MAL CALIBRADO (p < 0,05)' if p_val < ALFA else 'NO se rechaza la calibracion'}")

    # --- §5.3: el signo del intervalo del maximo sobrevive los dos borrados --
    print(f"\n§5.3 sobre el intervalo del maximo (bin {b_max}), signo observado "
          f"{'+' if c[b_max][0] > 0 else '-'}:")
    for etiqueta, sub in (("sin " + str(est_mayor), sin_est), ("sin " + mes_mayor, sin_mes)):
        cb = curva(sub)
        d2 = cb[b_max][0] if b_max in cb else float("nan")
        print(f"  {etiqueta:<18} d_b = {d2:+.4f}   "
              f"{'signo SOBREVIVE' if d2 * c[b_max][0] > 0 else 'signo NO sobrevive'}")
    return 0

sys.exit(main())
