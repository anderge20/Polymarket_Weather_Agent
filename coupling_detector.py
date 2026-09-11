#!/usr/bin/env python3
"""Detector de ACOPLAMIENTO SEMANTICO entre PRs abiertos (sesion B, 2026-09-11).

QUE BUSCA: una clave de diccionario que P escribe o lee, presente en un fichero
de PRODUCCION que Q modifica y P no, y que no sea ubicua.

QUE NO BUSCA, declarado: acoplamiento por argumento posicional, por ORDEN DE
ETAPAS o por efecto lateral. El acoplamiento #25/#26 estuvo a punto de ir por
orden de etapas (#25 mueve stage_params detras de stage_dump) y ninguna version
de esto lo habria visto.

ORIGEN: el par #25/#26 —dos PRs correctos por separado que juntos metian un
cambio de definicion dentro del instrumento de medida— no lo habria encontrado
ninguna revision por PR. Lo encontro mirar el PAR, y eran 21.

NO ES UNA REGLA, ES UNA HEURISTICA, y con el umbral sin justificar: en un caso
conocido señala el par bueno para umbrales 2..8, y elegir el que lo AISLA (u=2,
un solo par) seria ajuste a posteriori sobre el unico positivo conocido. UN
VERDADERO POSITIVO NO ES UN CONJUNTO DE VALIDACION.

REPRODUCIBILIDAD: dos sesiones implementaron esta misma descripcion y sacaron
3 pares contra 16. Descartadas cinco causas — corpus con tests/, claves de los
.md, longitud minima de clave, limpieza de comentarios en linea, restringir el
diff a *.py: las cuatro ultimas dan resultados IDENTICOS (1,3,9 pares para
umbrales 2,3,6). La divergencia esta en la CONDICION DE ARISTA: aqui la clave
debe aparecer como LITERAL ENTRECOMILLADO en el cuerpo del fichero en
origin/main. Que la prosa no bastara para reconstruirlo es el motivo de que esto
sea un script y no un parrafo.

Uso:  python3 coupling_detector.py [umbral]     (por defecto barre 1..8)
"""
import subprocess, re, itertools, sys, collections

CWD = "/Users/mariaaleu/workspace/Polymarket_Weather_Agent"
PR = {24:'guard/settle-window-contract', 25:'fix/profile-covers-dump',
      26:'perf/load-shards-batch',       27:'test/real-iem-payload',
      28:'claude/polymarket-edge-research-wyxck0',
      29:'measure/spread-distribution',  30:'guard/no-exit-liquidity'}

def sh(c):
    return subprocess.run(c, shell=True, capture_output=True, text=True, cwd=CWD).stdout

# --- corpus de PRODUCCION: .py fuera de tests/ ------------------------------
ALLPY = [f for f in sh("git ls-tree -r origin/main --name-only").split()
         if f.endswith('.py') and not f.startswith('tests/')]
BODIES = {f: sh(f"git show origin/main:{f}") for f in ALLPY}

def ubicuidad(k):
    """En cuantos ficheros de produccion aparece la clave COMO LITERAL."""
    return sum(1 for b in BODIES.values() if re.search(rf'["\']{re.escape(k)}["\']', b))

# --- claves y ficheros por PR ----------------------------------------------
KEY_PATTERNS = (r'\[\s*["\']([a-z_][a-z0-9_]{2,})["\']\s*\]',   #  d["x"]
                r'["\']([a-z_][a-z0-9_]{2,})["\']\s*:',          #  "x": v
                r'\.get\(\s*["\']([a-z_][a-z0-9_]{2,})["\']')    #  d.get("x")

files, keys = {}, {}
for n, br in PR.items():
    files[n] = set(sh(f"git diff --name-only origin/main...origin/{br}").split())
    diff = sh(f"git diff origin/main...origin/{br} -- '*.py'")
    ks = set()
    for line in diff.split("\n"):
        if not line.startswith(('+', '-')) or line.startswith(('+++', '---')):
            continue
        code = re.sub(r'#.*$', '', line[1:])      # fuera comentarios de linea
        if not code.strip():
            continue
        for pat in KEY_PATTERNS:
            ks |= set(re.findall(pat, code))
    keys[n] = ks

def barrido(umbral, verbose=False):
    aristas, pares = 0, set()
    for p, q in itertools.permutations(PR, 2):
        for f in sorted(files[q] - files[p]):
            # OJO: los ficheros de tests quedan EXCLUIDOS como objetivo.
            if not f.endswith('.py') or f.startswith('tests/'):
                continue
            b = BODIES.get(f)
            if not b:
                continue
            c = sorted(k for k in keys[p]
                       if ubicuidad(k) <= umbral
                       and re.search(rf'["\']{re.escape(k)}["\']', b))
            if c:
                aristas += len(c); pares.add(frozenset((p, q)))
                if verbose:
                    print(f"  #{p} -> #{q}  via {f}\n      {', '.join(c)}")
    return aristas, pares

if __name__ == "__main__":
    if len(sys.argv) > 1:
        u = int(sys.argv[1]); print(f"umbral {u}:"); a, pr = barrido(u, True)
        print(f"\naristas {a}  pares (no ordenados) {len(pr)} de 21")
    else:
        print(f"{'umbral':>7} {'aristas':>8} {'pares/21':>9}  {'25<->26?':>9}")
        for u in range(1, 9):
            a, pr = barrido(u)
            print(f"{u:7} {a:8} {len(pr):9}  {'SI' if frozenset((25,26)) in pr else 'no':>9}")
