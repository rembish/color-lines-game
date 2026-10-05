/* The core as a standalone WebAssembly module for the server (cloudflare/functions): the page
 * writes the moves into ln_wasm_buffer() as int32 (fx, fy, tx, ty, t0, t1 per move; t0, t1 in
 * hundredths of a second since midnight) and calls verify. */
#include "ln_core.h"

#define LN_WASM_MOVES 4096

static int32_t buffer[LN_WASM_MOVES * 6];
static ln_game game;
static int32_t thought; /* total thinking time of the moves, hundredths */

static ln_time clock_of(int32_t c)
{
    c %= 24 * 360000;
    if (c < 0) c += 24 * 360000;
    ln_time t = { (uint16_t)(c / 360000), (uint16_t)(c / 6000 % 60), (uint16_t)(c / 100 % 60), (uint16_t)(c % 100) };
    return t;
}

__attribute__((export_name("buffer"))) int32_t *ln_wasm_buffer(void) { return buffer; }
__attribute__((export_name("capacity"))) int ln_wasm_capacity(void) { return LN_WASM_MOVES; }

/* the score, or -1 if a move is not legal (or the game was over before it) */
__attribute__((export_name("verify"))) int ln_wasm_verify(uint32_t seed, int moves)
{
    if (moves < 0 || moves > LN_WASM_MOVES) return -1;
    ln_new_game(&game, seed);
    thought = 0;
    for (int i = 0; i < moves; i++) {
        const int32_t *m = buffer + 6 * i;
        if (ln_game_over(&game)) return -1;
        if (!ln_move(&game, m[0], m[1], m[2], m[3], clock_of(m[4]), clock_of(m[5]))) return -1;
        int32_t d = (m[5] - m[4]) % (24 * 360000);
        thought += d < 0 ? d + 24 * 360000 : d;
    }
    return game.score;
}

__attribute__((export_name("thought"))) int32_t ln_wasm_thought(void) { return thought; }
__attribute__((export_name("over"))) int ln_wasm_over(void) { return ln_game_over(&game); }
