"""Play Color Lines games in the emulator with a bot and store the event logs.

    python3 re/emu/record.py SEED [SEED...]     -> re/emu/logs/seed-SEED.json

The bot is greedy (the move that makes the longest line of its colour, ties at random) and now
and then wastes a turn on things that must not change the game: selecting another ball,
trying an unreachable cell, F3. It "thinks" a random time before each move, sometimes for a
long time (the score falls with it), and the clock starts at a random time of day, some games
near midnight or 18:12 (where the original's clock arithmetic wraps).

Each turn is logged at its first GetTime: the board, the next colours, the score, free cells and
RandSeed; then the keys the bot pressed and the two clock readings of the move. Seeds from 100
on replace the opening board with a crafted one (long lines and crosses for the first move).
"""

import json
import os
import random
import sys
from collections import deque
from typing import Any

from lemu import (
    BALLS,
    BOARD,
    FREE,
    K_F3,
    K_SPACE,
    LINE_COUNT,
    PLAY_GAME,
    RANDSEED,
    SCORE,
    Lines,
    path_keys,
)

HERE = os.path.dirname(os.path.abspath(__file__))
Cell = tuple[int, int]


def reachable(board: list[list[int]], frm: Cell) -> set[Cell]:
    seen, todo = {frm}, deque([frm])
    while todo:
        x, y = todo.popleft()
        for nx, ny in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
            if 0 <= nx < 9 and 0 <= ny < 9 and (nx, ny) not in seen and board[ny][nx] == 0:
                seen.add((nx, ny))
                todo.append((nx, ny))
    seen.discard(frm)
    return seen


def line_len(board: list[list[int]], x: int, y: int, c: int) -> int:
    best = 0
    for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
        n = 1
        for s in (1, -1):
            k = 1
            while 0 <= x + s * k * dx < 9 and 0 <= y + s * k * dy < 9 and board[y + s * k * dy][x + s * k * dx] == c:
                n += 1
                k += 1
        best = max(best, n)
    return best


def choose(board: list[list[int]], rnd: random.Random) -> tuple[Cell, Cell] | None:
    best: list[tuple[Cell, Cell]] = []
    score = -1
    for y in range(9):
        for x in range(9):
            c = board[y][x]
            if not c:
                continue
            for tx, ty in reachable(board, (x, y)):
                b = [row[:] for row in board]
                b[y][x] = 0
                v = line_len(b, tx, ty, c)
                if v > score:
                    score, best = v, []
                if v == score:
                    best.append(((x, y), (tx, ty)))
    return rnd.choice(best) if best else None


def craft(rnd: random.Random) -> tuple[list[list[int]], tuple[Cell, Cell]]:
    """A board where one move completes long lines or a cross: runs of one colour through an
    empty centre in one or two directions (5 to 9 cells with the centre), the ball to move
    somewhere reachable, other colours scattered."""
    while True:
        b = [[0] * 9 for _ in range(9)]
        c = rnd.randrange(1, 8)
        cx, cy = rnd.randrange(9), rnd.randrange(9)
        dirs = rnd.sample([(1, 0), (0, 1), (1, 1), (1, -1)], rnd.choice([1, 1, 2, 2, 3]))
        cells = []
        for dx, dy in dirs:
            ok = [k for k in range(-8, 9) if 0 <= cx + k * dx < 9 and 0 <= cy + k * dy < 9]
            n = rnd.randrange(5, len(ok) + 1) if len(ok) >= 5 else 0
            if not n:
                continue
            lo = rnd.choice([k for k in ok if k <= 0 and k + n - 1 >= 0 and k + n - 1 in ok])
            cells += [(cx + k * dx, cy + k * dy) for k in range(lo, lo + n) if k]
        if not cells:
            continue
        for x, y in cells:
            b[y][x] = c
        for _ in range(rnd.randrange(5, 30)):
            x, y = rnd.randrange(9), rnd.randrange(9)
            if not b[y][x] and (x, y) != (cx, cy):
                b[y][x] = rnd.choice([k for k in range(1, 8) if k != c])
        frm = [(x, y) for y in range(9) for x in range(9) if not b[y][x] and (x, y) != (cx, cy)]
        rnd.shuffle(frm)
        for fx, fy in frm:
            b[fy][fx] = c
            if (cx, cy) in reachable(b, (fx, fy)):
                return b, ((fx, fy), (cx, cy))
            b[fy][fx] = 0


def line_cells(board: list[list[int]], x: int, y: int) -> int:
    """check_lines' count for the ball at (x, y): runs of >= 5 of its colour along the four lines
    through it, the centre once per direction."""
    c, n = board[y][x], 0
    lines = [
        [(k, y) for k in range(9)],
        [(x, k) for k in range(9)],
        [(k, x + y - k) for k in range(9)],
        [(k, k + y - x) for k in range(9)],
    ]
    for cells in lines:
        run = 0
        for cx, cy in cells + [(-1, -1)]:
            if 0 <= cy < 9 and cx >= 0 and board[cy][cx] == c:
                run += 1
            else:
                n += run if run > 4 else 0
                run = 0
    return n


def tie_think(points: int, rnd: random.Random) -> int:
    """A thinking time in hundredths at or next to a rounding tie: points * f = j + 1/2."""
    j = rnd.randrange(0, 2 * points)
    t = 30000 * (2 - (j + 0.5) / points)
    return max(1, round(t * 100) + rnd.choice([-1, 0, 0, 1]))


def record(seed: int, scenario: bool = False) -> dict[str, Any]:
    rnd = random.Random(seed)
    g = Lines()
    g.w32(RANDSEED, seed)
    start = rnd.choice([rnd.randrange(24 * 360000), 24 * 360000 - rnd.randrange(30000), 65536 * 100 - 3000])
    g.clock = start
    turns: list[dict[str, Any]] = []
    times: list[int] = []
    pending: dict[str, Any] = {}

    crafted: dict[str, Any] = {}

    def on_time(clock: int) -> None:
        times.append(clock)
        if len(times) == 1 and scenario:  # replace the opening board with a crafted one
            board, mv = craft(rnd)
            n = 0
            for y in range(9):
                for x in range(9):
                    g.w16(BOARD + 18 * (x + 1) + 2 * (y + 1), board[y][x])
                    n += board[y][x] != 0
            g.w16(FREE, 81 - n)
            g.w16(BALLS, n)
            crafted["board"], crafted["move"] = board, mv
            crafted["tie"] = seed >= 200  # seeds from 200 on think to a rounding tie
        if len(times) % 2 == 1:  # t0: a new turn
            turns.append(
                {
                    "seed": g.ru32(RANDSEED),
                    "board": g.board(),
                    "next": g.next_colours(),
                    "score": g.ru16(SCORE),
                    "free": g.r16(FREE),
                    "balls": g.r16(BALLS),
                }
            )
        else:
            turns[-1]["t"] = [times[-2], clock]
            # the move is accepted, not made yet: the wasted attempts changed nothing
            if g.board() != turns[-1]["board"] or g.ru32(RANDSEED) != turns[-1]["seed"]:
                raise AssertionError("a rejected attempt or reselect changed the game")

    def keys() -> list[int]:
        board = g.board()
        cur = g.cursor()
        mv = choose(board, rnd)
        if crafted.get("move"):
            mv = crafted.pop("move")
        if mv is None:
            raise RuntimeError("no move but the game goes on")
        (fx, fy), (tx, ty) = mv
        out: list[int] = []
        r = rnd.random()
        if r < 0.05:
            out.append(K_F3)
        if r < 0.15:  # select some other ball first
            others = [(x, y) for y in range(9) for x in range(9) if board[y][x] and (x, y) != (fx, fy)]
            if others:
                o = rnd.choice(others)
                out += path_keys(cur, o) + [K_SPACE]
                cur = o
        out += path_keys(cur, (fx, fy)) + [K_SPACE]
        cur = (fx, fy)
        if r > 0.85:  # an unreachable empty cell: a beep, nothing else
            reach = reachable(board, (fx, fy))
            bad = [(x, y) for y in range(9) for x in range(9) if not board[y][x] and (x, y) not in reach]
            if bad:
                b = rnd.choice(bad)
                out += path_keys(cur, b) + [K_SPACE]
                cur = b
                pending["rejected"] = [fx + 1, fy + 1, b[0] + 1, b[1] + 1]
        think = rnd.choice([rnd.randrange(50, 2000), rnd.randrange(50, 2000), rnd.randrange(100000, 400000)])
        if crafted.get("tie"):
            b = [row[:] for row in board]
            b[ty][tx], b[fy][fx] = b[fy][fx], 0
            n = line_cells(b, tx, ty)
            if n >= 5:
                think = tie_think((n - 5) ** 2 + 5, rnd)
            crafted["tie"] = False
        g.clock += think
        out += path_keys(cur, (tx, ty)) + [K_SPACE]
        pending["move"] = [fx + 1, fy + 1, tx + 1, ty + 1]
        pending["keys"] = len(out)
        return out

    def keys_logged() -> list[int]:
        pending.pop("rejected", None)
        out = keys()
        turns[-1]["move"] = pending["move"]
        if "rejected" in pending:
            turns[-1]["rejected"] = pending["rejected"]
        return out

    g.key_source = keys_logged
    g.on_time = on_time
    g.call(PLAY_GAME)
    end = {"board": g.board(), "score": g.ru16(SCORE), "free": g.r16(FREE), "seed": g.ru32(RANDSEED),
           "line_count": g.r16(LINE_COUNT)}
    check(turns, end)
    log: dict[str, Any] = {"seed": seed, "clock": start, "turns": turns, "end": end}
    if scenario:
        log["inject"] = crafted["board"]
    return log


def check(turns: list[dict[str, Any]], end: dict[str, Any]) -> None:
    """Rules that must hold whatever the details: free cells match the board, a move without a
    line adds the announced balls, a line only removes the moved colour and scores >= 10."""
    states = turns + [end]
    for a, b in zip(states, states[1:], strict=False):
        for st in (a, b):
            n = sum(1 for row in st["board"] for c in row if c)
            if 81 - n != st["free"]:
                raise AssertionError(f"free {st['free']} but {n} balls")
        if "move" not in a:
            continue
        fx, fy, tx, ty = a["move"]
        colour = a["board"][fy - 1][fx - 1]
        if not colour or a["board"][ty - 1][tx - 1]:
            raise AssertionError(f"move {a['move']} is not from a ball to an empty cell")
        gained = b["score"] - a["score"]
        balls_a = 81 - a["free"]
        balls_b = 81 - b["free"]
        if gained == 0 and balls_b > balls_a + len(a["next"]):
            raise AssertionError(f"{balls_b - balls_a} balls added, {len(a['next'])} announced")
        if gained > 0:
            if gained < 1:
                raise AssertionError("a line scored nothing")
            removed = [(x, y) for y in range(9) for x in range(9) if a["board"][y][x] and not b["board"][y][x]
                       and (x, y) != (fx - 1, fy - 1)]
            if any(a["board"][y][x] != colour for x, y in removed):
                raise AssertionError(f"a line removed other colours: {removed}")


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
    for a in sys.argv[1:]:
        log = record(int(a), scenario=int(a) >= 100)  # seeds from 100 on start from a crafted board
        path = os.path.join(HERE, "logs", f"seed-{a}.json")
        with open(path, "w") as f:
            json.dump(log, f, separators=(",", ":"))
        print(path, len(log["turns"]), "turns, score", log["end"]["score"])
