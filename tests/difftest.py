"""Compare the core (build/replay) with the original's games (re/emu/logs, made by record.py).

    python3 tests/difftest.py [build/replay] [SEED...]      default: every log there is
"""

import glob
import json
import os
import subprocess
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELDS = ["seed", "board", "next", "score", "free", "balls"]


def moves(log: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if "inject" in log:
        out += ["B"] + [str(c) for row in log["inject"] for c in row]
    for t in log["turns"]:
        if "move" in t:
            out += [str(v) for v in t["move"]] + [str(v) for v in t["t"]]
    return out


def check(exe: str, path: str) -> str | None:
    log = json.load(open(path))
    r = subprocess.run([exe, str(log["seed"]), *moves(log)], capture_output=True, text=True)
    if r.returncode or r.stderr:
        return f"replay failed: {r.stderr.strip()}"
    mine = [json.loads(line) for line in r.stdout.splitlines()]
    want = log["turns"] + [log["end"]]
    for n, (a, b) in enumerate(zip(want, mine, strict=False), 1):
        for f in FIELDS:
            if f in a and a[f] != b[f]:
                return f"turn {n}: {f} differs\n  original {a[f]}\n  core     {b[f]}"
    if len(mine) != len(want):
        return f"{len(mine)} states, original {len(want)}"
    return None


if __name__ == "__main__":
    args = sys.argv[1:]
    exe = args.pop(0) if args and not args[0].isdigit() else os.path.join(ROOT, "build", "replay")
    paths = [os.path.join(ROOT, "re", "emu", "logs", f"seed-{s}.json") for s in args] or sorted(
        glob.glob(os.path.join(ROOT, "re", "emu", "logs", "seed-*.json"))
    )
    bad = 0
    for p in paths:
        err = check(exe, p)
        print(os.path.basename(p), "OK" if err is None else "FAIL: " + err)
        bad += err is not None
    sys.exit(1 if bad else 0)
