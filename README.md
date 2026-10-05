# Color Lines (1992) — decompilation & multiplatform port

«Color Lines» by Gamos (Moscow, 1992) — the game of every mom and dad in the 90s: a 9x9 board,
balls of seven colours, three new ones after every move, and lines of five or more vanish.
Programming Olga Demina, graphics Igor Ivkin & Gennady Denisov. This repo is a
reverse-engineered port of `LINES.EXE` to portable C + SDL2: it runs natively and in a browser.

**Play in the browser:** <https://lines.rembi.sh/> — with a global Top Ten. The page downloads the
original's pictures for you from the Internet Archive (one click), or takes your own copy.

[<img src="https://github.com/rembish/color-lines-game/releases/download/v0.1.0/lines.gif" width="480" alt="The pretender takes the king's crown">](https://github.com/rembish/color-lines-game/releases/download/v0.1.0/lines.mp4)

*Click for the video with the PC speaker: the demo plays at a human's pace until the pretender
passes the king's 100 points and takes his crown. Made with `tools/clips.sh` from your own copy
of the game; the clips live in the releases, never in the repository.*

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

## Playing

Click a ball, then a free cell it can reach (or the arrow keys and Space). Five or more of one
colour in a row — across, down or diagonal — vanish and score; otherwise the three balls shown
under *Next* arrive. F1 help, F2 sound, F3 the next balls shown or not, F4 start again (the Top
Ten all the same, as in the original), Esc the title, F11 full screen.

On lines.rembi.sh every game is dealt by the server with a signed seed. At the end the browser
sends the moves with the two clock readings of each; the server replays them with the same C
core compiled to WebAssembly and books the score it gets itself (`cloudflare/`). Names are
unique (the first browser to take one keeps it). Natively, and when the server does not answer,
the Top Ten stays on this computer.

## Building

```sh
cmake -S . -B build && cmake --build build -j
./build/lines            # looks for LINES.LIB in original/ or a folder you name
make help                # the everyday commands; `make check` is what CI runs
tools/clips.sh 75 3 62   # the clip above (needs ffmpeg and original/)
uv run --with numpy tools/trailer.py   # a 10-second comic trailer (ffmpeg, original/)
```

Browser: `make web` (Emscripten; the web build and the server's core into `cloudflare/`),
`node --test cloudflare/test.mjs` for the server.

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

## Code quality

The core builds with `-Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wsign-conversion` and more,
clean under gcc and clang, and is kept clean under clang-tidy and clang-format 21; the Python
tooling under ruff and `mypy --strict`. CI runs all of it on every push, with the sanitizers, the
web build, the server's tests and three games recorded from the original (`tests/fixtures`);
the deploy waits for it.

## Credits

«Color Lines» © 1992 Gamos Ltd.: Olga Demina, Igor Ivkin, Gennady Denisov. This is an
unofficial fan reimplementation for preservation; no original game files are distributed.

The code of this port is under the [BSD 3-Clause License](LICENSE).
