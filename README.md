# Color Lines (1992) — decompilation & multiplatform port

«Color Lines» by Gamos (Moscow, 1992) — the game of every mom and dad in the 90s: a 9x9 board,
balls of seven colours, three new ones after every move, and lines of five or more vanish.
Programming Olga Demina, graphics Igor Ivkin & Gennady Denisov. This repo is a
reverse-engineered port of `LINES.EXE` to portable C (+ SDL2 and WebAssembly, in progress).

The goal has two halves:

1. **Game logic: decompiled faithfully.** The Turbo Pascal random number generator and every
   call to it, where new balls land (and the probing that means the bottom-right cell is never
   drawn directly), the line check (a cross counts its centre once per direction), and the
   score, which depends on how long you thought about the move and is computed in Turbo
   Pascal's 6-byte Reals — reproduced bit for bit.
2. **Presentation: the original's own** pictures, read at run time from *your own copy* of
   `LINES.LIB`. Nothing of the original is in this repository.

## The original

The tools in `re/` need your own copy of the DOS release in `original/` (git-ignored, never
distributed):

```
bfa7f909c6360eb3a0586a43d44238f876e188788a7fc0cb2b7092a76ca13607  LINES.EXE
e49c81cd16e4bf5253e4272a131c3f4817370f3f635923f36fb3b1e93a521f53  LINES.LIB
```

- Turbo Pascal with the Graph unit's EGA driver and Genus Microprogramming's PCX Toolkit;
  `LINES.LIB` is a "pcxLib" archive of five 16-colour PCX pictures (`re/tools/lines.py`
  extracts them). `Lines.res`, written by the game, holds the Top Ten.

## How faithful is it?

- `re/emu/lemu.py` loads `LINES.EXE` into the Unicorn CPU emulator, stubs out only drawing,
  animation, sound, delays and the mouse, and runs the original's `play_game` with a scripted
  keyboard and a virtual clock. `re/emu/record.py` plays games with a bot (greedy lines, wasted
  reselects, unreachable targets, random and very long thinking times; games starting near
  midnight and at 18:12, where the original's clock arithmetic wraps; crafted boards with long
  lines and crosses; thinking times landing exactly on rounding ties) and checks the rules on
  every turn.
- `tests/difftest.py` replays those games through `core/` and compares every turn: the board,
  the next colours, free cells, the score and the random seed; the moves the original refused
  must be refused too. `tests/real48.py` checks the 6-byte Real arithmetic against the
  original's own System routines on 50,000 random operands. `tests/mutants.py` breaks the core
  in 20 ways and checks that the difftest catches each.

```sh
uv sync --extra dev
.venv/bin/python re/emu/record.py 1 2 3        # games from the original (needs original/)
cmake -S . -B build && cmake --build build
.venv/bin/python tests/difftest.py && .venv/bin/python tests/real48.py && .venv/bin/python tests/mutants.py
```

Findings and addresses are in [`re/NOTES.md`](re/NOTES.md).

## Credits

«Color Lines» © 1992 Gamos Ltd.: Olga Demina, Igor Ivkin, Gennady Denisov. This is an
unofficial fan reimplementation for preservation; no original game files are distributed.

The code of this port is under the [BSD 3-Clause License](LICENSE).
