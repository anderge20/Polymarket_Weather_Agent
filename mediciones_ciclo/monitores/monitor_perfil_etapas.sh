#!/bin/bash
# Monitor by5tofyq9, parado el 2026-09-13. Sin veredicto: solo reporta el perfil
# por etapas. Es el que NO tenia el defecto de B-120, y se publica al lado para
# que se vea la diferencia -- magnitudes sin conclusion.
cd /Users/mariaaleu/workspace/Polymarket_Weather_Agent
seen=""
while true; do
  git fetch -q origin paper-state 2>/dev/null || true
  for f in $(git ls-tree -r origin/paper-state --name-only 2>/dev/null | grep cycle_params | tail -6); do
    case "$seen" in *"$f"*) continue;; esac
    out=$(git show "origin/paper-state:$f" 2>/dev/null | gunzip 2>/dev/null | python3 -c "
import sys,json
for l in sys.stdin:
    d=json.loads(l); sp=d.get('stage_profile')
    if not sp: continue
    p=json.loads(sp)
    tot=sum(x.get('elapsed_s') or 0 for x in p)
    load=sum(x.get('elapsed_s') or 0 for x in p if x['stage'].startswith('load:'))
    dump=any('dump' in x['stage'] for x in p)
    top=sorted(p,key=lambda x:-(x.get('elapsed_s') or 0))[:3]
    print(f\"PERFIL {d['session_id']}: etapas={len(p)} incluye_dump={dump} suma={tot:.1f}s load={load:.1f}s ({100*load/tot:.1f}%) mayores=\" + ', '.join(f\"{x['stage']}={x.get('elapsed_s')}\" for x in top))
" 2>/dev/null)
    [ -n "$out" ] && echo "$out"
    seen="$seen $f"
  done
  sleep 420
done
