"""The Real48 port (core/ln_real48.c, via build/real48) against the original's System routines
in the emulator, on random operands and on the values the score uses.

    python3 tests/real48.py [COUNT]       needs original/LINES.EXE
"""

import os
import random
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "re", "emu"))
from lemu import Lines, call_regs  # noqa: E402

SYSTEM = 0x27DA
OPS = {"add": 0x0C48, "sub": 0x0C4E, "mul": 0x0C5A, "div": 0x0C60, "cmp": 0x0C6A}


def words(b: bytes) -> tuple[int, int, int]:
    a, x, d = struct.unpack("<3H", b)
    return a, x, d


def original(g: Lines, op: str, a: bytes, b: bytes | int) -> str:
    if op == "long":
        assert isinstance(b, int)
        v = b & 0xFFFFFFFF
        out, _ = call_regs(g, SYSTEM, 0x0C6E, {"ax": v & 0xFFFF, "dx": v >> 16})
        return struct.pack("<3H", out["ax"], out["bx"], out["dx"]).hex()
    ax, bx, dx = words(a)
    if op in ("round", "trunc"):
        out, flags = call_regs(g, SYSTEM, 0x0C7A if op == "round" else 0x0C72, {"ax": ax, "bx": bx, "dx": dx})
        v = out["dx"] << 16 | out["ax"]
        return str(v - (1 << 32) if v >> 31 else v)
    assert isinstance(b, bytes)
    cx, si, di = words(b)
    out, flags = call_regs(g, SYSTEM, OPS[op], {"ax": ax, "bx": bx, "dx": dx, "cx": cx, "si": si, "di": di})
    if op == "cmp":
        return "-1" if flags & 1 else "0" if flags & 0x40 else "1"
    return struct.pack("<3H", out["ax"], out["bx"], out["dx"]).hex()


def real(rnd: random.Random, lo: int = 0x70, hi: int = 0x98) -> bytes:
    if rnd.random() < 0.05:
        return bytes(6)
    m = bytearray(rnd.randbytes(5))
    if rnd.random() < 0.3:  # short mantissas: exact values, ties
        for i in range(rnd.randrange(0, 5)):
            m[i] = 0
    return bytes([rnd.randrange(lo, hi)]) + bytes(m)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    rnd = random.Random(48)
    g = Lines()
    cases: list[tuple[str, bytes, bytes | int]] = []
    for _ in range(n):
        op = rnd.choice(["add", "sub", "mul", "div", "cmp", "long", "round", "trunc"])
        a, b = real(rnd), real(rnd)
        if op in ("add", "sub", "cmp") and rnd.random() < 0.5:
            b = bytes([min(0xFE, max(1, a[0] + rnd.randrange(-3, 4)))]) + b[1:]  # close exponents
        if op == "div" and b[0] == 0:
            b = bytes([0x81]) + b[1:]
        if op in ("round", "trunc"):
            a = bytes([rnd.randrange(0x78, 0x9F)]) + a[1:]
        cases.append((op, a, rnd.randrange(-(1 << 31), 1 << 31) if op == "long" else b))
    lines = []
    for op, a, arg in cases:
        if isinstance(arg, int):
            lines.append(f"long {arg} 0")
        else:
            lines.append(f"{op} {a.hex()} {arg.hex()}")
    exe = os.path.join(ROOT, "build", "real48")
    mine = subprocess.run([exe], input="\n".join(lines) + "\n", capture_output=True, text=True).stdout.split()
    bad = 0
    for (op, a, arg), got in zip(cases, mine, strict=True):
        want = original(g, op, a, arg)
        if want != got:
            bad += 1
            if bad <= 10:
                shown = arg if isinstance(arg, int) else arg.hex()
                print(f"{op} {a.hex()} {shown}: original {want}, port {got}")
    print(f"{len(cases) - bad}/{len(cases)} equal")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
