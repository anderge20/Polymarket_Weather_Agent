import subprocess, re, collections
REPO="/Users/mariaaleu/workspace/Polymarket_Weather_Agent"
paths=subprocess.run(["git","ls-tree","-r","origin/paper-state","--name-only"],
                     cwd=REPO,capture_output=True,text=True).stdout.split()
bydir=collections.defaultdict(list)
for p in paths:
    if p.endswith(".ndjson.gz"):
        d,_,f=p.rpartition("/"); bydir[d].append(f)
print("directorios-dia con DOS generaciones de id conviviendo:\n")
bad=0
for d in sorted(bydir):
    fs=sorted(bydir[d])
    gens={("ts" if re.search(r"__col_\d{8}T",f) else
           "cyc" if "__cyc_" in f else
           "runid" if re.search(r"__col_\d{6,}_",f) else "?") for f in fs}
    if len(gens)>1:
        bad+=1
        print(f"  {d}   generaciones={sorted(gens)}")
        for f in fs: print(f"      {f}")
        print(f"      -> sorted()[-1] = {fs[-1]}\n")
print(f"total directorios con mezcla: {bad}")
