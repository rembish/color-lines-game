/* Replay a game through the core and print the state at the start of each turn and at the end,
 * in the form re/emu/record.py stores the original's (tests/difftest.py compares them).
 *
 *     replay SEED [B c1..c81] [X FX FY TX TY] FX FY TX TY T0 T1 ...
 *
 * T0, T1: hundredths of a second since midnight. B and 81 colours (row by row) replace the
 * opening board, as re/emu/record.py does for its crafted games. X and a move: an attempt the
 * original refused (an unreachable cell): the core must refuse it too and change nothing.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ln_core.h"

static ln_time clock_of(long c)
{
    c %= 24L * 360000L;
    ln_time t = { (uint16_t)(c / 360000), (uint16_t)(c / 6000 % 60), (uint16_t)(c / 100 % 60),
                  (uint16_t)(c % 100) };
    return t;
}

static void state(const ln_game *g, const char *end)
{
    printf("{\"seed\":%u,\"board\":[", g->seed);
    for (int y = 1; y <= LN_SIZE; y++) {
        printf("%s[", y > 1 ? "," : "");
        for (int x = 1; x <= LN_SIZE; x++) printf("%s%d", x > 1 ? "," : "", g->board[x][y]);
        printf("]");
    }
    printf("],\"next\":[");
    for (int i = 1; i <= g->next_count; i++) printf("%s%d", i > 1 ? "," : "", g->next[i]);
    printf("],\"score\":%u,\"free\":%d,\"balls\":%d}%s\n", g->score, g->free_cells, g->balls, end);
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: replay SEED [FX FY TX TY T0 T1]...\n");
        return 2;
    }
    static ln_game game;
    ln_game *g = &game;
    ln_new_game(g, (uint32_t)strtoul(argv[1], 0, 0));
    int a = 2;
    if (argc > 2 && argv[2][0] == 'B') {
        int n = 0;
        for (int k = 0; k < 81 && 3 + k < argc; k++) {
            g->board[k % 9 + 1][k / 9 + 1] = (int16_t)atoi(argv[3 + k]);
            n += g->board[k % 9 + 1][k / 9 + 1] != 0;
        }
        g->free_cells = (int16_t)(81 - n);
        g->balls = (int16_t)n;
        a = 84;
    }
    for (; a + 5 < argc; a += 6) {
        state(g, "");
        if (argv[a][0] == 'X') {
            static ln_game before;
            before = *g;
            if (ln_move(g, atoi(argv[a + 1]), atoi(argv[a + 2]), atoi(argv[a + 3]), atoi(argv[a + 4]),
                        clock_of(0), clock_of(0)) ||
                memcmp(&before, g, sizeof before)) {
                fprintf(stderr, "the core took a move the original refused\n");
                return 4;
            }
            a += 5;
        }
        int fx = atoi(argv[a]), fy = atoi(argv[a + 1]), tx = atoi(argv[a + 2]), ty = atoi(argv[a + 3]);
        if (!ln_move(g, fx, fy, tx, ty, clock_of(atol(argv[a + 4])), clock_of(atol(argv[a + 5])))) {
            fprintf(stderr, "illegal move %d,%d -> %d,%d\n", fx, fy, tx, ty);
            return 3;
        }
    }
    state(g, "");
    return 0;
}
