# LINES.EXE reverse-engineering notes

Addresses are Ghidra `segment:offset` with the image loaded at segment `1000`. Symbol names live
in `ghidra/names.txt`. Items marked **[verify]** still need a check in the emulator. The rules below are checked by
`tests/difftest.py` on 120 games played by the original in `re/emu` (20 from the opening, 40 from
crafted boards with long lines and crosses, 60 crafted with thinking times at rounding ties).

## The original

"Color Lines", Gamos Ltd., Moscow, 1992 ("GAMOS Logical Serial. Issue No. Two"). Programming:
Olga Demina; graphics: Igor Ivkin & Gennady Denisov.

```
bfa7f909c6360eb3a0586a43d44238f876e188788a7fc0cb2b7092a76ca13607  LINES.EXE
e49c81cd16e4bf5253e4272a131c3f4817370f3f635923f36fb3b1e93a521f53  LINES.LIB
```

- Turbo Pascal (the same runtime as KING, see `../king`, every System routine 0x309 bytes
  later), Graph with the EGAVGA driver and a stroked font linked in, Genus Microprogramming's
  PCX Programmer's Toolkit, a TurboPower-style Crt. Not packed, no overlays.
- Segments: `1000` main program (46 routines, 17 KB), `17fe` ?, `18e0` Crt (TPCRT), `19c2` Dos
  (`GetTime`), `19d1` PCX toolkit / mouse, `1fc8` ?, `24ad` Graph, `27da` System. DGROUP `2938`.
  **[verify]** the exact unit split of `17fe`, `19d1`, `1fc8`.
- `LINES.LIB`: a Genus "pcxLib" archive. A header (`pcxLib`, copyright 1988-89), then entries:
  84 bytes (`0x01`, the 8.3 name NUL-padded to 13, u32 size, date, time, unused) and the PCX
  file. Five 16-colour planar PCX pictures: `FL_LNS20` the field (640x350), `RS_LNS20` the
  sprites (balls, kings, font, buttons, Top Ten and Help panels), `RS_ZST20` the trumpeters,
  `ZS_LNS20` the title, `FL20_BUF` a strip of empty cells. `re/tools/lines.py` lists and
  extracts them (Pillow cannot read 1-bit x 4-plane PCX; the tool decodes it).
- `Lines.res` (written by the game): the Top Ten.

## Random numbers

Turbo Pascal's: `Randomize` (`27da:0d1b`, from the DOS time) once at start (`init`, `346f`);
`NextRand` (`27da:0ce3`) `RandSeed = RandSeed * 0x08088405 + 1` (`RandSeed` = `ds:07b0`);
`Random(N)` (`27da:0c94`) = `(RandSeed >> 16) mod N`.

Only four calls, all in the game logic, none in the input loop (confirmed by a byte search for
`lcall 27da:0c94` over the whole image: 1000:1070, 109c, 11bd, 1228; one `Randomize`, 3c33):

| Where | Call | For |
|-------|------|-----|
| `next_colors` `103b` | `Random(7) + 1` per ball | the "next" colours, `min(free, 3)` of them (`ds:35e6[1..3]`) |
| `place_next` `1092` | `Random(80)` | the position of next ball `i` |
| `place_random` `11b3` | `Random(80)`, then `Random(7) + 1` | position, then colour (the five starting balls) |

**Position:** `k = Random(80)`, cell `x = k mod 9 + 1`, `y = k div 9 + 1`; while that cell is
taken, `k + 1`, and 81 wraps to 0. `Random(80)` never gives 80, so the bottom-right cell
(9, 9) is never drawn directly, only reached by probing from a taken (8, 9) and the cells
before it. The port keeps this.

The bounce of a selected ball runs on the clock (`Dos.GetTime`), not on random numbers.

## Board

`board[x][y]` words at `ds:3490 + 18x + 2y`, x, y = 1..9 (x is the column), 0 = empty, 1..7 =
colour. `ds:343e` free cells, `ds:343c` balls placed, `ds:3438` score (word), `ds:343a` the best
score (Top Ten #1, the king to beat).

## A game (`play_game`, `1ee2`)

1. Clear the board, free = 81, score = 0. `next_colors`.
2. Repeat `place_random` and `check_lines` at the new ball until free = 76 (five balls; a line
   formed now is removed and replaced).
3. Each turn: read the time (`GetTime`, `t0`); wait for input. Keyboard: arrows move the cursor
   by a cell, Space selects / moves; mouse: click. F1 help, F2 sound on/off, F3 "next" shown /
   hidden (display only: the random numbers are the same either way), F4 restart, Esc quit.
   Selecting a ball, then an empty cell: `find_paths` (`1b3d`, breadth-first over empty cells,
   neighbours in the order up, down, left, right from tables `ds:019a`/`01a2`) decides whether
   it is reachable; if not, a beep and nothing changes. Selecting another ball just reselects.
4. On a move: read the time (`t1`), move the ball (the path animation follows the BFS parents:
   cosmetic), `check_lines` at the destination.
5. No line (`count < 5`): for i = 1..`min(free,3)` (the count from `next_colors`): if free > 0,
   `place_next(i)`; `check_lines` at the last placed cell (when free was 0 this re-checks the
   previous cell, with the previous colour). Then `next_colors`.
6. A line: score += `Round(((count - 5)^2 + 5) * f)`, `f = 2.0 - (t / 6000.0) * 0.2`, 0 if
   negative, all in Turbo Pascal 6-byte Reals; `t` = seconds from `t0` to `t1` (below).
   Nothing is placed after a line.
7. The game ends when free = 0, F4 (restart) or Esc (quit). After the end and after F4 alike,
   `game_loop` (`2e76`) offers the Top Ten with the score so far; only Esc skips it.

`check_lines(x, y)` (`153d`): for the row, the column and both diagonals through (x, y), take the
9 cells of that line (off-board cells of a diagonal as 0) and collect every run of 5 or more of
the colour `ds:34a2` (the ball just moved or placed) anywhere along it (`14b9`). `count`
(`ds:326c`) is the total of all runs: **the centre cell is counted once per direction** (a
cross of two lines of 5 counts 10, not 9). Each collected cell is emptied once (free + 1).

Elapsed time (`1000:0000`): each `GetTime` reading becomes
`Real(hour * 3600 + minute * 60 + second as a 16-bit unsigned sum) + hundredths * 0.01`
(**the 16-bit sum wraps from 18:12:16 on**); `t = t1 - t0`, plus 86400 if negative.
So a 5-line is 10 points, 6 = 12, 7 = 18, 8 = 28, 9 = 42 (cross lines count more), less only
after ~50 minutes of thought.

**The Reals matter.** With doubles, 3 of 60 games thought to a rounding tie
(`t = 30000 (2 - (j + 1/2) / points)`) scored one point off. `core/ln_real48.c` transliterates
the System routines (add/sub `0984`, mul `0a5a`, div `0ad7`, cmp `0b83`, long to Real `0bad`,
Round/Trunc `0bec`) register by register; `tests/real48.py` checks it against the original's
routines in the emulator on 50,000 random operands (all equal), and the difftest's tie games
match.

## Top Ten (`Lines.res`)

`file of` 16-byte records, 10 of them at `ds:07da + 16k` (k = 1..10): `string[13]` name, word
score. Missing file: #1 "Handicap" 100 points, the rest "- Empty -" 0. After a game with
a score above #10 the player types a name (up to 13 chars) and the table is shifted and saved.
`ds:343a` = #1's score: the king on the left is the record holder, the pretender on the right
grows with `score * 20 / best` (`0a72`) and takes the crown when the score passes it.
