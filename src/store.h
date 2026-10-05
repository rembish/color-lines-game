/* Persistent small files: a per-user data folder natively, localStorage on the web. */
#ifndef STORE_H
#define STORE_H

void store_init(void);
int store_read(const char *name, void *buf, int max); /* bytes read, -1 if missing */
int store_write(const char *name, const void *buf, int len);
const char *store_location(void);

#endif
