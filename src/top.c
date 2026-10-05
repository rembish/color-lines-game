#include "top.h"

#include <stdio.h>
#include <string.h>

#include "store.h"

int top_readonly;

static void defaults(top_table *t)
{
    for (int k = 0; k < TOP_N; k++) {
        snprintf(t->name[k], sizeof t->name[k], "%s", k ? "- Empty -" : "Handicap");
        t->score[k] = k ? 0 : 100;
    }
}

void top_load(top_table *t)
{
    unsigned char buf[TOP_N * 16];
    defaults(t);
    if (store_read("top.bin", buf, sizeof buf) != (int)sizeof buf) return;
    for (int k = 0; k < TOP_N; k++) {
        memcpy(t->name[k], buf + 16 * k, TOP_NAME);
        t->name[k][TOP_NAME] = 0;
        t->score[k] = (unsigned)(buf[16 * k + 14] | buf[16 * k + 15] << 8);
    }
}

int top_save(const top_table *t)
{
    if (top_readonly) return 0;
    unsigned char buf[TOP_N * 16] = { 0 };
    for (int k = 0; k < TOP_N; k++) {
        memcpy(buf + 16 * k, t->name[k], strlen(t->name[k]));
        buf[16 * k + 14] = (unsigned char)(t->score[k] & 0xff);
        buf[16 * k + 15] = (unsigned char)(t->score[k] >> 8);
    }
    return store_write("top.bin", buf, (int)sizeof buf);
}

int top_rank(const top_table *t, unsigned score)
{
    for (int k = 0; k < TOP_N; k++)
        if (t->score[k] < score) return k + 1;
    return 0;
}

void top_insert(top_table *t, int rank, const char *name, unsigned score)
{
    if (rank < 1 || rank > TOP_N) return;
    for (int k = TOP_N - 1; k >= rank; k--) {
        memcpy(t->name[k], t->name[k - 1], sizeof t->name[k]);
        t->score[k] = t->score[k - 1];
    }
    snprintf(t->name[rank - 1], sizeof t->name[rank - 1], "%s", name);
    t->score[rank - 1] = score;
}
