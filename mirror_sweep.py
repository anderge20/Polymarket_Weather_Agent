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

AND IT PRINTS HOW FAR THE MIRROR REACHES, because a periodic sweep fixes "never
mirrored" and does NOT fix "mirrored late" -- and the unmirrored tail is ALWAYS
the newest content. Session B found exactly that on 2026-09-12: five entries from
the previous two hours were local-only, and they held the D16 violation and four
misattributed facts. The exposure window is not random, it covers precisely what
was just learned. Naming the reach is the same demand we make of an
[UNMEASURABLE] result: silence must not read as "everything is here".

    python3 mirror_sweep.py                 # exits 1 if anything is missing or stale
"""
from __future__ import annotations

import datetime
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


def mirror_reach() -> tuple[str | None, str | None]:
    """When the mirror was last written, and when the corpus last changed.

    THE SWEEP FIXES "NEVER MIRRORED" AND NOT "MIRRORED LATE". Those are different
    defects and only the first one ends: the unmirrored tail is always the NEWEST
    material, so the exposure window covers exactly what was most recently learned
    -- on 2026-09-12 it was five entries from the previous two hours, holding a
    D16 violation and four facts misattributed to the wrong host. Reporting the
    reach does not close the window; it stops the reader of the mirror from
    assuming there isn't one.
    """
    head = subprocess.run(["git", "log", "-1", "--format=%cI", REF],
                          capture_output=True, text=True)
    mirrored = head.stdout.strip() if head.returncode == 0 else None
    files = [p for p in SOURCE.iterdir() if p.is_file() and p.suffix in SUFFIXES]
    newest = max((p.stat().st_mtime for p in files), default=None)
    if newest is not None:
        newest = datetime.datetime.fromtimestamp(
            newest, datetime.timezone.utc).isoformat(timespec="seconds")
    return mirrored, newest


def main() -> int:
    if not SOURCE.is_dir():
        print(f"no source corpus at {SOURCE}", file=sys.stderr)
        return 2
    # WITHOUT THIS THE SWEEP COMPARES AGAINST A STALE REF and reports identical
    # against whatever was fetched last — a false pass, and the quietest kind.
    subprocess.run(["git", "fetch", "-q", "origin", REF.split("/", 1)[1]],
                   capture_output=True)
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

    mirrored, newest = mirror_reach()
    print(f"corpus {SOURCE}: {len(names)} files against {REF}")
    print(f"  mirror reaches {mirrored or '?'}   newest local change {newest or '?'}")
    print(f"  identical {len(names) - len(missing) - len(stale)}"
          f"   MISSING {len(missing)}   STALE {len(stale)}")
    for n in missing:
        print(f"    MISSING  {n}")
    for n in stale:
        print(f"    STALE    {n}")
    return 1 if (missing or stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
