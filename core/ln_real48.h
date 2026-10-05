/* Turbo Pascal's 6-byte Real, bit for bit as LINES.EXE's System unit computes it (the score
 * depends on its rounding). Bytes as in memory: [0] exponent (bias 0x81, 0 = zero), [1..5]
 * mantissa low to high, bit 7 of [5] the sign. */
#ifndef LN_REAL48_H
#define LN_REAL48_H

#include <stdint.h>

typedef struct {
    uint8_t b[6];
} ln_real;

ln_real ln_real_add(ln_real a, ln_real b);
ln_real ln_real_sub(ln_real a, ln_real b);
ln_real ln_real_mul(ln_real a, ln_real b);
ln_real ln_real_div(ln_real a, ln_real b);
int ln_real_cmp(ln_real a, ln_real b); /* -1, 0, 1 */
ln_real ln_real_from_long(int32_t v);
int32_t ln_real_round(ln_real a);
int32_t ln_real_trunc(ln_real a);
/* a constant as the code loads it: CX, SI, DI */
ln_real ln_real_const(uint16_t cx, uint16_t si, uint16_t di);

#endif
