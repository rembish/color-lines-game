#!/bin/sh
# The three games in tests/fixtures/games.json (recorded from the original LINES.EXE) through the
# core (build/replay): the final score must be the original's. No game files needed: CI runs it.
set -e
BUILD=${1:-build}
python3 - "$BUILD" <<'PY'
import json, subprocess, sys
build, bad = sys.argv[1], 0
for g in json.load(open('tests/fixtures/games.json')):
    args = [str(v) for m in g['moves'] for v in m]
    out = subprocess.run([f'{build}/replay', str(g['seed']), *args], capture_output=True, text=True)
    score = json.loads(out.stdout.splitlines()[-1])['score'] if out.returncode == 0 else None
    print(f"game {g['seed']}:", 'OK' if score == g['score'] else f'FAIL {score} != {g["score"]} {out.stderr}')
    bad += score != g['score']
sys.exit(bad)
PY
