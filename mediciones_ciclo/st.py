import subprocess, gzip, json, collections, ast
REPO="/Users/mariaaleu/workspace/Polymarket_Weather_Agent"
def load(p):
    raw=subprocess.run(["git","show",f"origin/paper-state:{p}"],cwd=REPO,capture_output=True).stdout
    return [json.loads(l) for l in gzip.decompress(raw).decode().splitlines()]
A=load("paper_state/markets/2026/09/12/markets__col_20260912T000705Z_b58b50__0000.ndjson.gz")
B=load("paper_state/markets/2026/09/12/markets__col_20260912T024005Z_dffd86__0000.ndjson.gz")
k=lambda r:(r["market_id"],r["dataset_version"],r["record_version"])
pa={k(r):r for r in A}
def norm(v):
    if isinstance(v,str):
        try: return json.loads(v)
        except Exception:
            try: return ast.literal_eval(v)
            except Exception: return v
    return v
cnt=collections.Counter(); ej={}
for r in B:
    p=pa.get(k(r))
    if not p: continue
    x,y=norm(p.get("source_timestamps")),norm(r.get("source_timestamps"))
    if x==y: continue
    if isinstance(x,dict) and isinstance(y,dict):
        for f in set(x)|set(y):
            if x.get(f)!=y.get(f):
                cnt[f]+=1; ej.setdefault(f,(x.get(f),y.get(f)))
    else:
        cnt["__no_dict__"]+=1; ej.setdefault("__no_dict__",(type(x),type(y)))
print("campos de source_timestamps que cambian entre los dos ciclos:")
for f,n in cnt.most_common():
    print(f"  {f:<28}{n:5d} filas   {ej[f][0]!r} -> {ej[f][1]!r}")
if not cnt: print("  ninguno tras normalizar -> el cambio era de SERIALIZACION")
