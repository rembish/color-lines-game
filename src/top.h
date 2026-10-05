/* The Top Ten, as Lines.res keeps it: ten names and scores, #1 "Handicap" 100 at first. */
#ifndef LINES_TOP_H
#define LINES_TOP_H

#define TOP_N    10
#define TOP_NAME 10 /* characters the panel shows (the original's 90-pixel field) */

typedef struct {
    char name[TOP_N][TOP_NAME + 1];
    unsigned score[TOP_N];
} top_table;

extern int top_readonly;
void top_load(top_table *t);
int top_save(const top_table *t);
/* 1..10: where a score would go (above the first strictly lower one), 0 if not in */
int top_rank(const top_table *t, unsigned score);
void top_insert(top_table *t, int rank, const char *name, unsigned score);

#endif
