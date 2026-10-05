"""Give the difftest teeth: build the core with one deliberate change at a time and check that
tests/difftest.py notices. Each mutant is a (description, old, new) edit of core/ln_core.c.

    python3 tests/mutants.py [SEED...]
"""

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "core", "ln_core.c")
ONLY = os.environ.get("ONLY")

MUTANTS = [
    ("rng multiplier", "0x08088405u", "0x08088404u"),
    ("positions from Random(81)", "ln_random(g, 80)", "ln_random(g, 81)"),
    ("probe wraps at 80", "if (++k == 81) k = 0;", "if (++k == 80) k = 0;"),
    ("probe backwards", "if (++k == 81) k = 0;", "if (--k < 0) k = 80;"),
    ("six colours", "g->colour = (int16_t)(ln_random(g, 7) + 1);\n        g->next[i]",
     "g->colour = (int16_t)(ln_random(g, 6) + 1);\n        g->next[i]"),
    ("colour before position", "    free_position(g);\n    g->colour = (int16_t)(ln_random(g, 7) + 1);",
     "    g->colour = (int16_t)(ln_random(g, 7) + 1);\n    free_position(g);"),
    ("always three next", "g->next_count = g->free_cells < 3 ? g->free_cells : 3;", "g->next_count = 3;"),
    ("lines of four", "if (run > 4)", "if (run > 3)"),
    ("centre counted once", "g->line_count = (int16_t)(g->line_count + run);",
     "g->line_count = (int16_t)(g->line_count + run - (g->line_count > 0));"),
    ("no anti-diagonal", "else if (d == 2) lx[k] = k, ly[k] = x + y - k;",
     "else if (d == 2) lx[k] = k, ly[k] = 0;"),
    ("four starting balls", "} while (g->free_cells != 76);", "} while (g->free_cells != 77);"),
    ("next drawn after the start", "    next_colours(g);\n    do {", "    do {"),
    # Not a mutant: skipping the re-check of the previous cell when the board is full changes
    # nothing (that ball formed no line, or cells would be free), so no test can tell.
    ("new balls after a line", "if (g->line_count < 5) {", "if (1) {"),
    ("points (n-4)^2", "(int16_t)((count - 5) * (count - 5))", "(int16_t)((count - 4) * (count - 4))"),
    ("time factor /5000", "ln_real_const(0x008d, 0, 0x3b80)", "ln_real_const(0x008d, 0, 0x1c40)"),
    ("round down", "ln_real_round(ln_real_mul(", "ln_real_trunc(ln_real_mul("),
    ("no 16-bit wrap", "uint16_t whole = (uint16_t)(t.hour * 3600u", "int32_t whole = (int32_t)(t.hour * 3600u"),
    ("no midnight", "return ln_real_add(ln_real_sub(a, b), ln_real_const(0x0091, 0, 0x28c0));",
     "return ln_real_sub(a, b);"),
    ("hundredths ignored", "return ln_real_add(ln_real_from_long(whole), hundredths);",
     "return ln_real_from_long(whole);"),
]


def main() -> None:
    seeds = sys.argv[1:]
    tmp = tempfile.mkdtemp(prefix="ln-mut-")
    original = open(SRC).read()
    survived = []
    try:
        for name, old, new in MUTANTS:
            if ONLY and ONLY not in name:
                continue
            if old not in original:
                print(f"{name}: pattern not found")
                survived.append(name)
                continue
            src = os.path.join(tmp, "ln_core.c")
            open(src, "w").write(original.replace(old, new, 1))
            exe = os.path.join(tmp, "replay")
            subprocess.run(["cc", "-O2", "-std=c99", "-I", os.path.join(ROOT, "core"), "-o", exe, src,
                            os.path.join(ROOT, "core", "ln_real48.c"), os.path.join(ROOT, "tests", "replay.c")], check=True)
            try:
                r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "difftest.py"), exe, *seeds],
                                   capture_output=True, text=True, timeout=120)
                caught, how = r.returncode != 0, ""
            except subprocess.TimeoutExpired:
                caught, how = True, " (hangs)"
            print(f"{name}: {'caught' + how if caught else 'SURVIVED'}", flush=True)
            if not caught:
                survived.append(name)
    finally:
        shutil.rmtree(tmp)
    print(f"{len(MUTANTS) - len(survived)}/{len(MUTANTS)} caught")
    sys.exit(1 if survived else 0)


if __name__ == "__main__":
    main()
