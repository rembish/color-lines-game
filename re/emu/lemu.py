"""Run the game of the original LINES.EXE headless under Unicorn.

The image is loaded at segment 0x1000 (same addresses as the Ghidra project) and relocated.
`play_game` (1000:1ee2) runs as it is; drawing, animation, sound, delays and the mouse are
stubbed. The keyboard is a script of key words (scan << 8 | ascii) and `GetTime` reads a
virtual clock the script advances, so the time a move took (and with it the score) is exact.

Pascal calling convention: arguments are pushed in source order and the callee pops them.
"""

import os
import struct
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_INSN, UC_HOOK_INTR, UC_MODE_16
from unicorn.x86_const import (
    UC_X86_INS_IN,
    UC_X86_INS_OUT,
    UC_X86_REG_AX,
    UC_X86_REG_BP,
    UC_X86_REG_CS,
    UC_X86_REG_DS,
    UC_X86_REG_ES,
    UC_X86_REG_IP,
    UC_X86_REG_SP,
    UC_X86_REG_SS,
)

if TYPE_CHECKING:
    # The same class as unicorn.Uc, which mypy sees untyped (as in ../king and ../elite-plus).
    from unicorn.unicorn_py3.unicorn import Uc as Uc
else:
    from unicorn import Uc as Uc

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, "..", "..", "original", "LINES.EXE")

CS = 0x1000
DS = 0x2938
CRT, DOS, MOUSE, BLIT = 0x18E0, 0x19C2, 0x19D1, 0x17FE
STACK_SEG = 0x2EDA  # SS:SP from the EXE header
STACK_TOP = 0x2000
SENTINEL = (0x9000, 0x0000)

# Replaced by a bare return (bytes popped): drawing, animation, the PC speaker, delays, the
# mouse unit. None writes a variable the game logic reads (checked in the decompiled code): the
# bounce (0c15, 0dfa) and select (0bef) keep only their own frame counters and clock.
STUBS: dict[tuple[int, int], tuple[str, int]] = {
    (CS, 0x04D1): ("press_button", 0),
    (CS, 0x0778): ("music", 0),
    (CS, 0x0A72): ("draw_score_and_kings", 4),
    (CS, 0x0BEF): ("select_bounce_start", 0),
    (CS, 0x0C15): ("bounce", 0),
    (CS, 0x0DFA): ("bounce_settle", 0),
    (CS, 0x0F59): ("draw_next", 0),
    (CS, 0x0FF3): ("hide_next", 0),
    (CS, 0x1779): ("animate_move", 0),
    (CS, 0x1D24): ("help", 0),
    (BLIT, 0x0000): ("blit", 0x10),
    (BLIT, 0x008B): ("blit2", 0x10),
    (CRT, 0x0CD7): ("Delay", 2),
    (CRT, 0x0D58): ("Sound", 2),
    (CRT, 0x0D85): ("NoSound", 0),
    (MOUSE, 0x01DC): ("mouse_01dc", 4),
    (MOUSE, 0x0210): ("mouse_0210", 0x0E),
    (MOUSE, 0x03B1): ("mouse_03b1", 0x0C),
    (MOUSE, 0x0586): ("mouse_0586", 0x0C),
    (MOUSE, 0x07CC): ("mouse_07cc", 4),
    (MOUSE, 0x07FF): ("mouse_07ff", 0x0C),
    (MOUSE, 0x08AF): ("mouse_08af", 6),
}

PLAY_GAME = 0x1EE2
KEYPRESSED, READKEY, GETTIME = 0x0B4B, 0x0B5D, 0x0036

# DGROUP
RANDSEED = 0x07B0
SOUND_ON, NEXT_SHOWN, MOUSE_PRESENT = 0x07C2, 0x07C3, 0x4384
CURSOR_X, CURSOR_Y = 0x325A, 0x325C
SCORE, BEST, BALLS, FREE = 0x3438, 0x343A, 0x343C, 0x343E
BOARD = 0x3490  # + 18x + 2y, x, y = 1..9
NEXT_COLOUR, NEXT_COUNT = 0x35E6, 0x35FA
LINE_COUNT = 0x326C

# key words: scan << 8 | ascii
K_LEFT, K_RIGHT, K_UP, K_DOWN = 0x4B00, 0x4D00, 0x4800, 0x5000
K_SPACE, K_F3, K_F4, K_ESC = 0x3920, 0x3D00, 0x3E00, 0x011B

Clock = tuple[int, int, int, int]  # hour, minute, second, hundredths
Record = dict[str, Any]


class Stop(Exception):
    pass


class Lines:
    def __init__(self) -> None:
        raw = open(EXE, "rb").read()
        hdr = struct.unpack("<H", raw[8:10])[0] * 16
        img = bytearray(raw[hdr:])
        nrel = struct.unpack("<H", raw[6:8])[0]
        rtab = struct.unpack("<H", raw[0x18:0x1A])[0]
        for k in range(nrel):
            off, seg = struct.unpack("<HH", raw[rtab + 4 * k : rtab + 4 * k + 4])
            p = seg * 16 + off
            v = struct.unpack("<H", img[p : p + 2])[0]
            img[p : p + 2] = struct.pack("<H", (v + CS) & 0xFFFF)
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_16)
        mu.mem_map(0, 0x100000)
        mu.mem_write(CS * 16, bytes(img))
        self.keys: list[int] = []
        self.key_source: Callable[[], list[int]] | None = None
        self.clock = 0  # hundredths of a second since midnight (may pass 24 h: wraps)
        self.on_time: Callable[[int], None] | None = None  # each GetTime, with the clock
        self.error: BaseException | None = None
        self.max_insns = 2_000_000_000
        for (seg, off), (_name, n) in STUBS.items():
            mu.mem_write(seg * 16 + off, b"\xca" + struct.pack("<H", n) if n else b"\xcb")
        self.pyfuncs: dict[tuple[int, int], tuple[Callable[[list[int]], int], int]] = {
            (CRT, KEYPRESSED): (self.keypressed, 0),
            (CRT, READKEY): (self.readkey, 0),
            (DOS, GETTIME): (self.gettime, 16),
        }
        for seg, off in self.pyfuncs:
            a = seg * 16 + off
            mu.hook_add(UC_HOOK_CODE, self._py, begin=a, end=a)
        mu.hook_add(UC_HOOK_INTR, self._intr)
        mu.hook_add(UC_HOOK_INSN, self._io, None, 1, 0, UC_X86_INS_OUT)
        mu.hook_add(UC_HOOK_INSN, self._io, None, 1, 0, UC_X86_INS_IN)
        self.w8(MOUSE_PRESENT, 0)
        self.w8(SOUND_ON, 1)
        self.w8(NEXT_SHOWN, 1)

    # ---- memory (DGROUP) ----
    def rb(self, off: int, n: int = 1) -> bytes:
        return bytes(self.mu.mem_read(DS * 16 + off, n))

    def r16(self, off: int) -> int:
        v: int = struct.unpack("<h", self.rb(off, 2))[0]
        return v

    def ru16(self, off: int) -> int:
        v: int = struct.unpack("<H", self.rb(off, 2))[0]
        return v

    def ru32(self, off: int) -> int:
        v: int = struct.unpack("<I", self.rb(off, 4))[0]
        return v

    def wb(self, off: int, data: bytes) -> None:
        self.mu.mem_write(DS * 16 + off, bytes(data))

    def w8(self, off: int, v: int) -> None:
        self.wb(off, bytes([v & 0xFF]))

    def w16(self, off: int, v: int) -> None:
        self.wb(off, struct.pack("<H", v & 0xFFFF))

    def w32(self, off: int, v: int) -> None:
        self.wb(off, struct.pack("<I", v & 0xFFFFFFFF))

    def board(self) -> list[list[int]]:
        """board[y][x] for x, y = 0..8 (the game's x, y = 1..9)."""
        return [[self.r16(BOARD + 18 * (x + 1) + 2 * (y + 1)) for x in range(9)] for y in range(9)]

    def cursor(self) -> tuple[int, int]:
        """The cell under the cursor, x, y = 0..8 (the game computes 1..9 the same way)."""
        return (self.r16(CURSOR_X) - 0x88) // 0x22 - 1, (self.r16(CURSOR_Y) - 0x24) // 0x18 - 1

    def next_colours(self) -> list[int]:
        return [self.r16(NEXT_COLOUR + 2 * i) for i in range(1, self.r16(NEXT_COUNT) + 1)]

    # ---- replaced routines ----
    def keypressed(self, args: list[int]) -> int:
        if not self.keys and self.key_source:
            self.keys += self.key_source()
        return 1 if self.keys else 0

    def readkey(self, args: list[int]) -> int:
        if not self.keys:
            raise RuntimeError("ReadKey without a scripted key")
        return self.keys.pop(0)

    def gettime(self, args: list[int]) -> int:
        """GetTime(var Hour, Minute, Second, Sec100: Word): four far pointers, source order."""
        c = self.clock % (24 * 360000)
        vals = (c // 360000, c // 6000 % 60, c // 100 % 60, c % 100)
        for k, v in enumerate(vals):
            off, seg = args[2 * k + 1], args[2 * k]
            self.mu.mem_write(seg * 16 + off, struct.pack("<H", v))
        if self.on_time:
            self.on_time(self.clock)
        return 0

    def _intr(self, mu: Uc, intno: int, _: object) -> None:
        cs, ip = mu.reg_read(UC_X86_REG_CS), mu.reg_read(UC_X86_REG_IP)
        raise RuntimeError(f"unhandled int {intno:02x} at {cs:04x}:{ip:04x}")

    def _io(self, mu: Uc, port: int, size: int, value: object = None, _: object = None) -> None:
        cs, ip = mu.reg_read(UC_X86_REG_CS), mu.reg_read(UC_X86_REG_IP)
        raise RuntimeError(f"port I/O {port:x} at {cs:04x}:{ip:04x}: a routine is not stubbed")

    def _py(self, mu: Uc, addr: int, size: int, _: object) -> None:
        seg = mu.reg_read(UC_X86_REG_CS)
        fn, nbytes = self.pyfuncs[(seg, addr - seg * 16)]
        sp, ss = mu.reg_read(UC_X86_REG_SP), mu.reg_read(UC_X86_REG_SS)

        def rd(o: int) -> int:
            v: int = struct.unpack("<H", bytes(mu.mem_read(ss * 16 + ((sp + o) & 0xFFFF), 2)))[0]
            return v

        ip, cs = rd(0), rd(2)
        args = [rd(4 + nbytes - 2 - 2 * k) for k in range(nbytes // 2)]  # source order
        try:
            ax = fn(args)
        except (Stop, RuntimeError, AssertionError) as e:  # reported by call()
            self.error = e
            mu.emu_stop()
            return
        mu.reg_write(UC_X86_REG_AX, (ax or 0) & 0xFFFF)
        mu.reg_write(UC_X86_REG_SP, (sp + 4 + nbytes) & 0xFFFF)
        mu.reg_write(UC_X86_REG_CS, cs)
        mu.reg_write(UC_X86_REG_IP, ip)

    def call(self, off: int, *args: int, seg: int = CS) -> int:
        """Far call seg:off with Pascal arguments (source order)."""
        mu = self.mu
        mu.reg_write(UC_X86_REG_DS, DS)
        mu.reg_write(UC_X86_REG_ES, DS)
        mu.reg_write(UC_X86_REG_SS, STACK_SEG)
        sp = STACK_TOP

        def push(v: int) -> None:
            nonlocal sp
            sp -= 2
            mu.mem_write(STACK_SEG * 16 + sp, struct.pack("<H", v & 0xFFFF))

        for a in args:
            push(a)
        push(SENTINEL[0])
        push(SENTINEL[1])
        mu.reg_write(UC_X86_REG_SP, sp)
        mu.reg_write(UC_X86_REG_BP, 0)
        mu.reg_write(UC_X86_REG_CS, seg)
        self.error = None
        mu.emu_start(seg * 16 + off, SENTINEL[0] * 16 + SENTINEL[1], count=self.max_insns)
        if self.error:
            raise self.error
        here = mu.reg_read(UC_X86_REG_CS) * 16 + mu.reg_read(UC_X86_REG_IP)
        if here != SENTINEL[0] * 16 + SENTINEL[1]:
            raise RuntimeError(f"call {seg:04x}:{off:04x} stopped at {here:05x}")
        ax: int = mu.reg_read(UC_X86_REG_AX)
        return ax


def call_regs(game: Lines, seg: int, off: int, regs: dict[str, int]) -> tuple[dict[str, int], int]:
    """Far call seg:off with registers in and out (the System unit's Real routines take their
    operands in AX:BX:DX and CX:SI:DI). Returns the registers and EFLAGS."""
    from unicorn.x86_const import (
        UC_X86_REG_BX,
        UC_X86_REG_CX,
        UC_X86_REG_DI,
        UC_X86_REG_DX,
        UC_X86_REG_EFLAGS,
        UC_X86_REG_SI,
    )

    names = {
        "ax": UC_X86_REG_AX,
        "bx": UC_X86_REG_BX,
        "cx": UC_X86_REG_CX,
        "dx": UC_X86_REG_DX,
        "si": UC_X86_REG_SI,
        "di": UC_X86_REG_DI,
    }
    mu = game.mu
    mu.reg_write(UC_X86_REG_DS, DS)
    mu.reg_write(UC_X86_REG_SS, STACK_SEG)
    sp = STACK_TOP - 4
    mu.mem_write(STACK_SEG * 16 + sp, struct.pack("<HH", SENTINEL[1], SENTINEL[0]))
    mu.reg_write(UC_X86_REG_SP, sp)
    mu.reg_write(UC_X86_REG_BP, 0)
    for k, v in regs.items():
        mu.reg_write(names[k], v)
    mu.reg_write(UC_X86_REG_CS, seg)
    mu.emu_start(seg * 16 + off, SENTINEL[0] * 16 + SENTINEL[1], count=100000)
    out = {k: int(mu.reg_read(r)) for k, r in names.items()}
    flags: int = mu.reg_read(UC_X86_REG_EFLAGS)
    return out, flags


def path_keys(frm: tuple[int, int], to: tuple[int, int]) -> list[int]:
    """Arrow keys that move the cursor from cell frm to cell to (x, y = 0..8)."""
    dx, dy = to[0] - frm[0], to[1] - frm[1]
    return [K_RIGHT if dx > 0 else K_LEFT] * abs(dx) + [K_DOWN if dy > 0 else K_UP] * abs(dy)
