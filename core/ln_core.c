/* Color Lines game logic, reconstructed from LINES.EXE. Addresses: see re/NOTES.md. */
#include "ln_core.h"
#include "ln_real48.h"

#include <string.h>

/* System.Random (27da:0c94) */
uint16_t ln_random(ln_game *g, uint16_t n)
{
    g->seed = g->seed * 0x08088405u + 1u;
    return n ? (uint16_t)((g->seed >> 16) % n) : 0;
}

/* next_colors (103b) */
static void next_colours(ln_game *g)
{
    g->next_count = g->free_cells < 3 ? g->free_cells : 3;
    for (int i = 1; i <= g->next_count; i++) {
        g->colour = (int16_t)(ln_random(g, 7) + 1);
        g->next[i] = g->colour;
    }
}

/* the position part of place_next / place_random: Random(80), then the next free cell */
static void free_position(ln_game *g)
{
    int k = ln_random(g, 80);
    for (;;) {
        g->last_x = (int16_t)(k % 9 + 1);
        g->last_y = (int16_t)(k / 9 + 1);
        if (!g->board[g->last_x][g->last_y]) break;
        if (++k == 81) k = 0;
    }
}

static void put(ln_game *g)
{
    g->board[g->last_x][g->last_y] = g->colour;
    g->balls++;
    g->free_cells--;
}

/* place_next (1092) */
static void place_next(ln_game *g, int i)
{
    free_position(g);
    g->colour = g->next[i];
    put(g);
}

/* place_random (11b3) */
static void place_random(ln_game *g)
{
    free_position(g);
    g->colour = (int16_t)(ln_random(g, 7) + 1);
    put(g);
}

/* check_lines (153d): runs of >= 5 of g->colour along the row, column and diagonals through
 * (x, y); the centre is collected once per direction */
static void check_lines(ln_game *g, int x, int y)
{
    int16_t cx[4 * LN_SIZE], cy[4 * LN_SIZE];
    g->line_count = 0;
    for (int d = 0; d < 4; d++) {
        /* the 9 cells of the line, k = 1..9 as the original walks them */
        int lx[LN_SIZE + 1], ly[LN_SIZE + 1], c[LN_SIZE + 1];
        for (int k = 1; k <= LN_SIZE; k++) {
            if (d == 0) lx[k] = k, ly[k] = y;                 /* line_row (12c9) */
            else if (d == 1) lx[k] = x, ly[k] = k;            /* line_column (131d) */
            else if (d == 2) lx[k] = k, ly[k] = x + y - k;    /* anti-diagonal (1391) */
            else lx[k] = k, ly[k] = k + (y - x);              /* diagonal (1436) */
            c[k] = (ly[k] >= 1 && ly[k] <= LN_SIZE) ? g->board[lx[k]][ly[k]] : 0;
        }
        int run = 0;
        for (int k = 1; k <= LN_SIZE + 1; k++) { /* collect_runs (14b9) */
            if (k <= LN_SIZE && c[k] == g->colour) {
                cx[g->line_count + run] = (int16_t)lx[k];
                cy[g->line_count + run] = (int16_t)ly[k];
                run++;
            } else {
                if (run > 4) g->line_count = (int16_t)(g->line_count + run);
                run = 0;
            }
        }
    }
    for (int i = 0; i < g->line_count; i++)
        if (g->board[cx[i]][cy[i]]) {
            g->board[cx[i]][cy[i]] = 0;
            g->free_cells++;
        }
}

void ln_new_game(ln_game *g, uint32_t seed)
{
    memset(g, 0, sizeof *g);
    g->seed = seed;
    g->free_cells = 81;
    next_colours(g);
    do {
        place_random(g);
        check_lines(g, g->last_x, g->last_y);
    } while (g->free_cells != 76);
}

int ln_game_over(const ln_game *g) { return g->free_cells == 0; }

/* find_paths (1b3d): breadth-first over empty cells */
int ln_reachable(const ln_game *g, int fx, int fy, int tx, int ty)
{
    if (fx < 1 || fx > 9 || fy < 1 || fy > 9 || tx < 1 || tx > 9 || ty < 1 || ty > 9) return 0;
    if (!g->board[fx][fy] || g->board[tx][ty]) return 0;
    static const int dx[4] = { 0, 0, -1, 1 }, dy[4] = { -1, 1, 0, 0 };
    uint8_t seen[LN_SIZE + 2][LN_SIZE + 2] = { { 0 } };
    int qx[81], qy[81], head = 0, tail = 0;
    qx[tail] = fx, qy[tail++] = fy;
    seen[fx][fy] = 1;
    while (head < tail) {
        int x = qx[head], y = qy[head++];
        for (int d = 0; d < 4; d++) {
            int nx = x + dx[d], ny = y + dy[d];
            if (nx < 1 || nx > 9 || ny < 1 || ny > 9 || seen[nx][ny] || g->board[nx][ny]) continue;
            if (nx == tx && ny == ty) return 1;
            seen[nx][ny] = 1;
            qx[tail] = nx, qy[tail++] = ny;
        }
    }
    return 0;
}

/* elapsed_seconds (1000:0000), in 6-byte Reals: Real(whole seconds, a 16-bit sum) + hundredths *
 * 0.01; t1 - t0, plus 86400 if t1 is before t0 */
static ln_real seconds_of(ln_time t)
{
    uint16_t whole = (uint16_t)(t.hour * 3600u + t.minute * 60u + t.second);
    ln_real hundredths = ln_real_mul(ln_real_from_long(t.hundredths), ln_real_const(0x717a, 0x0a3d, 0x23d7));
    return ln_real_add(ln_real_from_long(whole), hundredths);
}

static ln_real elapsed(ln_time t0, ln_time t1)
{
    ln_real b = seconds_of(t0), a = seconds_of(t1);
    if (ln_real_cmp(a, b) < 0) return ln_real_add(ln_real_sub(a, b), ln_real_const(0x0091, 0, 0x28c0));
    return ln_real_sub(a, b);
}

/* the score in play_game (1000:236e): Round(((n - 5)^2 + 5) * f), f = 2 - t / 6000 * 0.2, f >= 0 */
int ln_points(int count, ln_time t0, ln_time t1)
{
    ln_real q = ln_real_div(elapsed(t0, t1), ln_real_const(0x008d, 0, 0x3b80));
    ln_real r = ln_real_mul(q, ln_real_const(0xcd7e, 0xcccc, 0x4ccc));
    ln_real f = ln_real_sub(ln_real_const(0x0082, 0, 0), r);
    if (ln_real_cmp(f, ln_real_const(0, 0, 0)) < 0) f = ln_real_const(0, 0, 0);
    int16_t k = (int16_t)((int16_t)((count - 5) * (count - 5)) + 5); /* imul ax: 16 bits */
    return (int)ln_real_round(ln_real_mul(ln_real_from_long(k), f));
}

int ln_move(ln_game *g, int fx, int fy, int tx, int ty, ln_time t0, ln_time t1)
{
    if (!ln_reachable(g, fx, fy, tx, ty)) return 0;
    g->colour = g->board[fx][fy];
    g->board[fx][fy] = 0;
    g->board[tx][ty] = g->colour;
    check_lines(g, tx, ty);
    if (g->line_count < 5) {
        int n = g->next_count;
        for (int i = 1; i <= n; i++) {
            if (g->free_cells != 0) place_next(g, i);
            check_lines(g, g->last_x, g->last_y); /* the previous cell again if nothing was placed */
        }
        next_colours(g);
    } else
        g->score = (uint16_t)(g->score + ln_points(g->line_count, t0, t1));
    return 1;
}
