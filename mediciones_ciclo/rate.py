import subprocess, gzip, json, collections
REPO="/Users/mariaaleu/workspace/Polymarket_Weather_Agent"
PROV={"ingestion_timestamp","source_timestamps"}
def load(p):
    raw=subprocess.run(["git","show",f"origin/paper-state:{p}"],cwd=REPO,capture_output=True).stdout
    return [json.loads(l) for l in gzip.decompress(raw).decode().splitlines()]
def shards(t):
    ps=subprocess.run(["git","ls-tree","-r","origin/paper-state","--name-only"],cwd=REPO,
                      capture_output=True,text=True).stdout.split()
    return sorted(p for p in ps if f"/{t}/" in p)
for t,key in [("markets",("market_id","dataset_version","record_version")),
              ("outcomes",("token_id","dataset_version","record_version"))]:
    sh=shards(t); print(f"=== {t}")
    for a,b in zip(sh,sh[1:]):
        A,B=load(a),load(b)
        idk=lambda r: tuple(str(r.get(c)) for c in key)
        pa={idk(r):r for r in A}
        cols={c for r in B for c in r}
        real=collections.Counter(); prov=0; nuevas=0
        for r in B:
            p=pa.get(idk(r))
            if p is None: nuevas+=1; continue
            d=[c for c in cols if p.get(c)!=r.get(c)]
            if any(c not in PROV for c in d):
                for c in d:
                    if c not in PROV: real[c]+=1
            elif d: prov+=1
        print(f"  {a.split('__')[1][:22]:>22} -> {b.split('__')[1][:22]:<22}"
              f" nuevas={nuevas:5d}  solo-reloj={prov:5d}  contenido={sum(1 for _ in [0]) and ''}"
              f"{dict(real) if real else 'NADA'}")
