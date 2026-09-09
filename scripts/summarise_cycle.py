#!/usr/bin/env python3
"""Render paper-cycle summaries as a Markdown table for the Actions job summary.

A separate script rather than an inline `python - <<PY` inside the workflow: a
heredoc's body sits at column 0, which terminates the surrounding YAML block
scalar and makes the whole workflow file unparseable. That failure is invisible
locally and only shows up as "workflow file issue" in the Actions UI, so the
logic lives here where it can be tested.

Usage:  python scripts/summarise_cycle.py <dir-with-cycle-json> [...]
"""
from __future__ import annotations

import glob
import json
import os
import sys

SKIP_KEYS = {"stage", "status", "traceback"}
MAX_DETAIL = 160


def rows_for(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        summary = json.load(fh)
    out = []
    for stage in summary.get("stages", []):
        detail = " ".join(
            f"{k}={v}" for k, v in stage.items() if k not in SKIP_KEYS
        )
        # Escape the cell separator: a JSON detail containing '|' would otherwise
        # silently split into extra columns.
        detail = detail.replace("|", "\\|")[:MAX_DETAIL]
        out.append(f"| `{stage.get('stage')}` | {stage.get('status')} | {detail} |")
    return out


def main(argv: list[str]) -> int:
    targets: list[str] = []
    for arg in argv or ["results/"]:
        if os.path.isdir(arg):
            targets.extend(sorted(glob.glob(os.path.join(arg, "*.json"))))
        else:
            targets.append(arg)
    if not targets:
        print("| (no cycle summary found) | | |")
        return 0
    for path in targets:
        try:
            for line in rows_for(path):
                print(line)
        except (OSError, ValueError) as exc:
            print(f"| `{os.path.basename(path)}` | UNREADABLE | {exc} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
