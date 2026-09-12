import subprocess, gzip, json, collections
REPO="/Users/mariaaleu/workspace/Polymarket_Weather_Agent"
def load(p):
    raw=subprocess.run(["git","show",f"origin/paper-state:{p}"],cwd=REPO,capture_output=True).stdout
    return [json.loads(l) for l in gzip.decompress(raw).decode().splitlines()]
for table,a,b in [
  ("markets","paper_state/markets/2026/09/12/markets__col_20260912T000705Z_b58b50__0000.ndjson.gz",
             "paper_state/markets/2026/09/12/markets__col_20260912T024005Z_dffd86__0000.ndjson.gz"),
  ("outcomes","paper_state/outcomes/2026/09/12/outcomes__col_20260912T000705Z_b58b50__0000.ndjson.gz",
              "paper_state/outcomes/2026/09/12/outcomes__col_20260912T024005Z_dffd86__0000.ndjson.gz")]:
    A,B=load(a),load(b)
    key=("market_id","dataset_version","record_version") if table=="markets" else ("token_id","dataset_version","record_version")
    idk=lambda r: tuple(str(r.get(c)) for c in key)
    ka,kb={idk(r) for r in A},{idk(r) for r in B}
    ca={k for r in A for k in r}; cb={k for r in B for k in r}
    print(f"=== {table}: {len(A)} -> {len(B)} filas")
    print(f"  claves iguales? {ka==kb}   (solo en A:{len(ka-kb)}  solo en B:{len(kb-ka)})")
    print(f"  columnas iguales? {ca==cb}  dif={ca^cb}")
    pa={idk(r):r for r in A}
    dif=collections.Counter(); ejemplo={}
    for r in B:
        p=pa.get(idk(r))
        if p is None: continue
        for c in cb:
            if p.get(c)!=r.get(c):
                dif[c]+=1
                ejemplo.setdefault(c,(p.get(c),r.get(c)))
    print(f"  filas comunes con algun valor distinto: "
          f"{len({1 for r in B if pa.get(idk(r)) and any(pa[idk(r)].get(c)!=r.get(c) for c in cb)})}"
          if False else "")
    n=sum(1 for r in B if pa.get(idk(r)) and any(pa[idk(r)].get(c)!=r.get(c) for c in cb))
    print(f"  filas comunes con algun valor distinto: {n} de {len(B)}")
    for c,k in dif.most_common(8):
        v=ejemplo[c]
        print(f"    {c:<26} {k:5d} filas   {str(v[0])[:40]!r} -> {str(v[1])[:40]!r}")
    if not dif: print("    NINGUN valor cambia")
    print()
