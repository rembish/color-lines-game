/* A whole game for any seed, played by a greedy bot through the core: a valid submission for
 * testing the server. Prints the moves as JSON ([[fx,fy,tx,ty,t0,t1],...], one second of
 * thought each, from T0) and the score.  botmoves SEED [T0] */
#include <stdio.h>
#include <stdlib.h>

#include "ln_core.h"

static ln_time at(long c)
{
    c %= 24L * 360000L;
    ln_time t = { (uint16_t)(c / 360000), (uint16_t)(c / 6000 % 60), (uint16_t)(c / 100 % 60),
                  (uint16_t)(c % 100) };
    return t;
}

static int line_len(const ln_game *g, int fx, int fy, int u, int v, int c)
{
    static const int dirs[4][2] = { { 1, 0 }, { 0, 1 }, { 1, 1 }, { 1, -1 } };
    int best = 0;
    for (int d = 0; d < 4; d++) {
        int m = 1;
        for (int s = -1; s <= 1; s += 2)
            for (int k = 1;; k++) {
                int a = u + s * k * dirs[d][0], b = v + s * k * dirs[d][1];
                if (a < 1 || a > 9 || b < 1 || b > 9 || (a == fx && b == fy) || g->board[a][b] != c) break;
                m++;
            }
        if (m > best) best = m;
    }
    return best;
}

int main(int argc, char **argv)
{
    static ln_game g;
    ln_new_game(&g, argc > 1 ? (uint32_t)strtoul(argv[1], 0, 0) : 1);
    long clock = argc > 2 ? atol(argv[2]) : 3600L * 100;
    printf("[");
    for (int n = 0; !ln_game_over(&g); n++) {
        int best = -1, bx = 0, by = 0, tx = 0, ty = 0;
        for (int y = 1; y <= 9; y++)
            for (int x = 1; x <= 9; x++)
                if (g.board[x][y])
                    for (int v = 1; v <= 9; v++)
                        for (int u = 1; u <= 9; u++)
                            if (ln_reachable(&g, x, y, u, v)) {
                                int len = line_len(&g, x, y, u, v, g.board[x][y]);
                                if (len > best) best = len, bx = x, by = y, tx = u, ty = v;
                            }
        if (best < 0) break;
        long t0 = clock, t1 = clock + 100;
        clock = t1 + 50;
        ln_move(&g, bx, by, tx, ty, at(t0), at(t1));
        printf("%s[%d,%d,%d,%d,%ld,%ld]", n ? "," : "", bx, by, tx, ty, t0 % (24L * 360000L),
               t1 % (24L * 360000L));
    }
    printf("]\n%u\n", g.score);
    return 0;
}
