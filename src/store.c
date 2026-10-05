#include "store.h"
#include <SDL.h>
#include <stdio.h>
#include <string.h>

#ifdef __EMSCRIPTEN__
#include <emscripten.h>

/* clang-format off */

EM_JS(int, js_store_read, (const char *name, unsigned char *buf, int max), {
    try {
        var v = localStorage.getItem('lines:' + UTF8ToString(name));
        if (v === null) return -1;
        var s = atob(v), n = Math.min(s.length, max);
        for (var i = 0; i < n; i++) HEAPU8[buf + i] = s.charCodeAt(i);
        return n;
    } catch (e) { return -1; }
});

EM_JS(int, js_store_write, (const char *name, const unsigned char *buf, int len), {
    try {
        var s = '';
        for (var i = 0; i < len; i++) s += String.fromCharCode(HEAPU8[buf + i]);
        localStorage.setItem('lines:' + UTF8ToString(name), btoa(s));
        return len;
    } catch (e) { return -1; }
});

/* clang-format on */
void store_init(void) {}
int store_read(const char *name, void *buf, int max) { return js_store_read(name, buf, max); }
int store_write(const char *name, const void *buf, int len) { return js_store_write(name, buf, len); }
const char *store_location(void) { return "browser storage"; }

#else

static char base[1024];

void store_init(void)
{
    char *p = SDL_GetPrefPath("Lines", "Lines");
    if (p) {
        snprintf(base, sizeof base, "%s", p);
        SDL_free(p);
    }
}

static void path(char *out, size_t n, const char *name) { snprintf(out, n, "%s%s", base, name); }

int store_read(const char *name, void *buf, int max)
{
    char p[1200];
    path(p, sizeof p, name);
    FILE *f = fopen(p, "rb");
    if (!f) return -1;
    int n = (int)fread(buf, 1, (size_t)max, f);
    if (ferror(f)) n = -1;
    if (fclose(f) != 0) n = -1;
    return n;
}

int store_write(const char *name, const void *buf, int len)
{
    char p[1200], tmp[1210];
    path(p, sizeof p, name);
    snprintf(tmp, sizeof tmp, "%s.tmp", p);
    FILE *f = fopen(tmp, "wb");
    if (!f) return -1;
    int n = (int)fwrite(buf, 1, (size_t)len, f);
    if (fclose(f) != 0 || n != len) {
        (void)remove(tmp);
        return -1;
    }
#ifdef _WIN32
    (void)remove(p); /* rename() does not replace on Windows */
#endif
    if (rename(tmp, p) != 0) return -1;
    return n;
}

const char *store_location(void) { return base; }

#endif
