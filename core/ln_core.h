/* Color Lines game logic, reconstructed from LINES.EXE (Gamos, 1992).
 *
 * Deterministic and free of I/O. A game is the seed and the moves; each move carries the two
 * clock readings the original takes around it (the score depends on how long the player
 * thought).
 *
 *     ln_new_game(g, seed);
 *     while (!ln_game_over(g))
 *         ln_move(g, fx, fy, tx, ty, t0, t1);    returns 0 (nothing happens) if not legal
 */
#ifndef LN_CORE_H
#define LN_CORE_H

#include <stdint.h>

#define LN_SIZE    9
#define LN_COLOURS 7

/* a clock reading as GetTime gives it */
typedef struct {
    uint16_t hour, minute, second, hundredths;
} ln_time;

typedef struct {
    uint32_t seed;                           /* Turbo Pascal RandSeed */
    int16_t board[LN_SIZE + 1][LN_SIZE + 1]; /* board[x][y], x, y = 1..9, 0 empty, 1..7 colour */
    int16_t free_cells;
    int16_t balls; /* placed so far (ds:343c) */
    uint16_t score;
    int16_t next[4]; /* next colours [1..next_count] */
    int16_t next_count;
    int16_t colour;         /* the ball last moved or placed (ds:34a2) */
    int16_t last_x, last_y; /* the cell last placed (ds:39e4, ds:39e6) */
    int16_t line_count;     /* cells in lines at the last check (ds:326c) */
} ln_game;

uint16_t ln_random(ln_game *g, uint16_t n);

void ln_new_game(ln_game *g, uint32_t seed);
int ln_game_over(const ln_game *g);
/* 1 if (tx, ty) is empty and reachable from the ball at (fx, fy) through empty cells */
int ln_reachable(const ln_game *g, int fx, int fy, int tx, int ty);
/* a move; 0 (and no change) unless ln_reachable */
int ln_move(ln_game *g, int fx, int fy, int tx, int ty, ln_time t0, ln_time t1);
/* the points a line of `count` cells earns when the move was thought over from t0 to t1
 * (Turbo Pascal 6-byte Reals, bit for bit: core/ln_real48.c) */
int ln_points(int count, ln_time t0, ln_time t1);

#endif
