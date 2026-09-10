"""Desbiasing V2/V3 (PREREG §9 / V5 §7): historia = misma estación y modelo, target_date <= D-2 días,
pooled sobre leads; |historia|<10 -> NO EVALUABLE; bias_hat = media(f - Y); residual = (f - bias_hat) - Y."""
from datetime import date, timedelta
import collections
def debias(rows, key_model=lambda r: r['model']):
    """rows: dicts con icao, target_date, lead, f, y. Devuelve lista nueva con bias_hat/residual o None."""
    by=collections.defaultdict(list)
    for r in rows:
        if r['f'] is None or r['y'] is None: continue
        by[(r['icao'],key_model(r))].append(r)
    out=[]
    for r in rows:
        if r['f'] is None or r['y'] is None:
            out.append(dict(r,bias_hat=None,residual=None,evaluable=False,motivo='f_o_y_nulo')); continue
        D=date.fromisoformat(r['target_date']); cut=D-timedelta(days=2)
        hist=[h for h in by[(r['icao'],key_model(r))] if date.fromisoformat(h['target_date'])<=cut]
        if len(hist)<10:
            out.append(dict(r,bias_hat=None,residual=None,evaluable=False,motivo=f'historia={len(hist)}<10')); continue
        b=sum(h['f']-h['y'] for h in hist)/len(hist)
        out.append(dict(r,bias_hat=b,residual=(r['f']-b)-r['y'],evaluable=True,motivo=None,n_hist=len(hist)))
    return out
if __name__=="__main__":
    import json
    RAW=json.load(open('MODELSEL_GEOVAL_V3_RAW.json')); EV=json.load(open('MODELSEL_GEOVAL_V3_EVAL.json'))
    mine=debias(RAW)
    idx={(r['event_id'],r['icao'],r['lead'],r['model']):r for r in mine if r['evaluable']}
    n=len(EV); ok=0; maxd=0.0; missing=0
    for e in EV:
        m=idx.get((e['event_id'],e['icao'],e['lead'],e['model']))
        if not m: missing+=1; continue
        d=max(abs(m['bias_hat']-e['bias_hat']),abs(m['residual']-e['residual'])); maxd=max(maxd,d)
        if d<1e-9: ok+=1
    extra=len(idx)-(n-missing)
    print(f"VALIDACIÓN contra MODELSEL_GEOVAL_V3_EVAL.json: {ok}/{n} filas idénticas (tol 1e-9), "
          f"max|Δ|={maxd:.2e}, filas de V3 sin equivalente={missing}, filas evaluables extra={extra}")
