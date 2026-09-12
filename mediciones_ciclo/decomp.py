import sys, json, subprocess
REPO = "/Users/mariaaleu/workspace/Polymarket_Weather_Agent"

def sh(*a):
    return subprocess.run(a, cwd=REPO, capture_output=True, text=True).stdout

files = [f for f in sh("git","ls-tree","-r","origin/paper-state","--name-only").splitlines()
         if "cycle_params" in f]
files.sort()

rows = []
for f in files[-6:]:
    raw = subprocess.run(["git","show",f"origin/paper-state:{f}"], cwd=REPO,
                         capture_output=True).stdout
    import gzip, io
    for line in gzip.decompress(raw).decode().splitlines():
        d = json.loads(line)
        prof = d.get("stage_profile")
        if not prof:
            continue
        p = json.loads(prof) if isinstance(prof, str) else prof
        el = {x["stage"]: (x.get("elapsed_s") or 0) for x in p}
        cat = sum(v for k,v in el.items() if k.startswith("load:") and
                  any(t in k for t in ("markets","outcomes","fee_schedule")))
        led = sum(v for k,v in el.items() if k.startswith("load:") and
                  any(t in k for t in ("orderbook","price_history")))
        tot = sum(el.values())
        rows.append((d.get("session_id",""), tot, cat, led, el))

rows.sort(key=lambda r: r[0])
print(f"{'session':<22}{'total min':>10}{'CATALOGO':>11}{'lib+prec':>11}{'resto':>9}")
prev = None
for sid, tot, cat, led, el in rows:
    print(f"{sid:<22}{tot/60:10.2f}{cat:10.1f}s{led:10.1f}s{tot-cat-led:8.1f}s")
    if prev:
        dc, dl = cat-prev[0], led-prev[1]
        share = 100*dc/(dc+dl) if (dc+dl) else float('nan')
        print(f"{'  delta':<22}{(tot-prev[2])/60:+10.2f}{dc:+10.1f}s{dl:+10.1f}s"
              f"   catalogo={share:.0f}% del crecimiento de carga")
    prev = (cat, led, tot)

if rows:
    print("\netapas del ultimo ciclo, mas caras primero:")
    for k,v in sorted(rows[-1][4].items(), key=lambda kv:-kv[1])[:10]:
        print(f"  {k:<34}{v:8.1f}s")
