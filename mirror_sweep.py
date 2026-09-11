#!/usr/bin/env python3
"""Compare the research corpus against its mirror — by LIST and by CONTENT.

WHY THIS EXISTS AND NOT A REMINDER. On 2026-09-11 the base preregistration of
R30, seven of its ten amendments and the index that orders them were never
pushed: only amendments A, B and C were reachable, each citing a base nobody
could open. It was found by a THIRD session that tried to open a document being
cited and said "I cannot, and I am declaring that rather than accepting it".

Neither of the two working sessions could have found it. Both had the files on
disk, so the path always worked for them.

    Same instrument, different observer  -> catches a wrong OBJECT
    Different instrument                 -> catches a broken INSTRUMENT
    DIFFERENT ACCESS                     -> catches the corpus's REACH

And A-106 had already recorded the same failure once, with 13 files local-only.
The lesson was written down and the practice did not change, which is why this
is a script and not another note: **the remedy is never more discipline, it is a
mechanical comparison of sets.**

Checks CONTENT, not presence: a file that is mirrored but stale is the defect
that looks fixed.

    python3 mirror_sweep.py                 # exits 1 if anything is missing or stale
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

SOURCE = pathlib.Path(os.path.expanduser("~/pmw-e2"))
REF = "origin/research/modelsel-artifacts"
SUFFIXES = {".md", ".sha256", ".json", ".py", ".txt", ".csv"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if not SOURCE.is_dir():
        print(f"no source corpus at {SOURCE}", file=sys.stderr)
        return 2
    names = sorted(p.name for p in SOURCE.iterdir()
                   if p.is_file() and p.suffix in SUFFIXES)
    missing, stale = [], []
    for name in names:
        got = subprocess.run(["git", "show", f"{REF}:{name}"],
                             capture_output=True)
        if got.returncode != 0:
            missing.append(name)
        elif digest(got.stdout) != digest((SOURCE / name).read_bytes()):
            stale.append(name)

    print(f"corpus {SOURCE}: {len(names)} files against {REF}")
    print(f"  identical {len(names) - len(missing) - len(stale)}"
          f"   MISSING {len(missing)}   STALE {len(stale)}")
    for n in missing:
        print(f"    MISSING  {n}")
    for n in stale:
        print(f"    STALE    {n}")
    return 1 if (missing or stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
