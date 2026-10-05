/* The global Top Ten at lines.rembi.sh (cloudflare/): the browser build only. Every call starts a
 * request and returns at once; the *_status calls say how it went. Natively all of it is off. */
#ifndef NET_H
#define NET_H

#include <stdint.h>

enum { NET_PENDING, NET_OK, NET_TAKEN, NET_FAILED };

void net_claim(const char *name);
int net_claim_status(void);

void net_new_game(void);
/* the server's seed for the next game, if it came */
int net_game_seed(uint32_t *seed);

/* moves_json: [[fx,fy,tx,ty,t0,t1],...] */
void net_submit(const char *name, const char *moves_json);
/* NET_OK: buf = "score rank\n" then "score name\n" per Top Ten entry; else buf = the reason */
int net_result(char *buf, int max);
/* the Top Ten: NET_OK with "score name\n" lines */
void net_top(void);
int net_top_result(char *buf, int max);

#endif
