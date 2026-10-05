/* Run one Real48 operation (for tests/real48.py, which checks it against the original's System
 * routines in the emulator).  real48 OP A B   A, B: 12 hex digits (the 6 bytes, as in memory);
 * OP: add sub mul div cmp long round trunc (long takes a decimal integer as A). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ln_real48.h"

static ln_real parse(const char *s)
{
    ln_real x;
    for (int i = 0; i < 6; i++) {
        unsigned v = 0;
        sscanf(s + 2 * i, "%2x", &v);
        x.b[i] = (uint8_t)v;
    }
    return x;
}

static void show(ln_real x)
{
    for (int i = 0; i < 6; i++) printf("%02x", x.b[i]);
    printf("\n");
}

int main(int argc, char **argv)
{
    char line[256], op[16], a[64], b[64];
    (void)argc;
    (void)argv;
    while (fgets(line, sizeof line, stdin)) { /* OP A B per line */
        b[0] = 0;
        if (sscanf(line, "%15s %63s %63s", op, a, b) < 2) continue;
        if (!strcmp(op, "add"))
            show(ln_real_add(parse(a), parse(b)));
        else if (!strcmp(op, "sub"))
            show(ln_real_sub(parse(a), parse(b)));
        else if (!strcmp(op, "mul"))
            show(ln_real_mul(parse(a), parse(b)));
        else if (!strcmp(op, "div"))
            show(ln_real_div(parse(a), parse(b)));
        else if (!strcmp(op, "cmp"))
            printf("%d\n", ln_real_cmp(parse(a), parse(b)));
        else if (!strcmp(op, "long"))
            show(ln_real_from_long((int32_t)strtol(a, 0, 10)));
        else if (!strcmp(op, "round"))
            printf("%ld\n", (long)ln_real_round(parse(a)));
        else if (!strcmp(op, "trunc"))
            printf("%ld\n", (long)ln_real_trunc(parse(a)));
    }
    return 0;
}
