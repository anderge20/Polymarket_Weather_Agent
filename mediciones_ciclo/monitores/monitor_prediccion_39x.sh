#!/bin/bash
# Monitor bg9qqlnoy, parado el 2026-09-13. PUBLICADO PARA QUE B-120 SEA VERIFICABLE.
#
# EL DEFECTO, en la linea marcada: `v='CONFIRMADA' if load<=100 else 'REFUTADA'`.
# `load` es la suma de las etapas load:* EN SEGUNDOS; empezo en ~890 y llego a
# ~1.330. Solo libro+precios son ~1.200. El umbral de 100 no podia alcanzarse
# nunca, asi que el veredicto era una CONSTANTE: imprimio REFUTADA en todos los
# ciclos. El resto de la linea -- perfil, rows_loaded, rows_resident -- si era
# util, y de ahi salieron B-99, B-107 y B-118.
cd /Users/mariaaleu/workspace/Polymarket_Weather_Agent
seen=""
while true; do
  git fetch -q origin paper-state 2>/dev/null || true
  for f in $(git ls-tree -r origin/paper-state --name-only 2>/dev/null | grep cycle_params | tail -4); do
    case "$seen" in *"$f"*) continue;; esac
    seen="$seen $f"
    git show "origin/paper-state:$f" 2>/dev/null | gunzip 2>/dev/null | python3 -c "
import sys,json
for l in sys.stdin:
    d=json.loads(l); sp=d.get('stage_profile')
    if not sp: continue
    p=json.loads(sp)
    tot=sum(x.get('elapsed_s') or 0 for x in p)
    load=sum(x.get('elapsed_s') or 0 for x in p if x['stage'].startswith('load:'))
    dump=any('dump' in x['stage'] for x in p)
    rr=d.get('store_rows_resident'); rl=d.get('store_rows_loaded')
    v='CONFIRMADA' if load<=100 else 'REFUTADA'      # <-- EL DEFECTO: load nunca < 890
    print(f\"PERFIL {d['session_id']}: load={load:.1f}s total={tot:.1f}s ({100*load/tot:.0f}%) dump={dump} rows_loaded={rl} rows_resident={rr} -> prediccion 39x {v}\")
" 2>/dev/null
  done
  sleep 300
done
