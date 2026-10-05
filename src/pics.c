#include "pics.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *names[PIC_COUNT] = { "FL_LNS20.PCX", "RS_LNS20.PCX", "RS_ZST20.PCX", "ZS_LNS20.PCX",
                                        "FL20_BUF.PCX" };
static struct {
    int w, h;
    Uint32 *rgba; /* w * h */
} pic[PIC_COUNT];
static SDL_Texture *tex[PIC_COUNT];
static SDL_Renderer *ren;
static char err[200];

const char *pics_error(void) { return err; }

static unsigned rd16(const unsigned char *p) { return (unsigned)(p[0] | p[1] << 8); }

/* a 16-colour planar PCX (1 bit x 4 planes, RLE, palette in the header) */
static int decode(int k, const unsigned char *d, size_t len)
{
    if (len < 128 || d[0] != 0x0a) return -1;
    int w = (int)(rd16(d + 8) - rd16(d + 4) + 1), h = (int)(rd16(d + 10) - rd16(d + 6) + 1);
    int planes = d[65], bpl = (int)rd16(d + 66);
    if (w <= 0 || h <= 0 || w > 1024 || h > 1024 || planes != 4) return -1;
    size_t need = (size_t)h * (size_t)planes * (size_t)bpl;
    unsigned char *raw = malloc(need);
    size_t n = 0, p = 128;
    while (n < need && p < len) {
        unsigned c = d[p++];
        if (c >= 0xc0) {
            unsigned run = c - 0xc0;
            unsigned char v = p < len ? d[p++] : 0;
            while (run-- && n < need) raw[n++] = v;
        } else
            raw[n++] = (unsigned char)c;
    }
    Uint32 pal[16];
    for (int i = 0; i < 16; i++)
        pal[i] =
            (Uint32)d[16 + 3 * i] | (Uint32)d[17 + 3 * i] << 8 | (Uint32)d[18 + 3 * i] << 16 | 0xff000000u;
    free(pic[k].rgba);
    pic[k].w = w;
    pic[k].h = h;
    pic[k].rgba = malloc((size_t)w * (size_t)h * 4);
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            int c = 0;
            for (int pl = 0; pl < planes; pl++)
                if (raw[((size_t)y * (size_t)planes + (size_t)pl) * (size_t)bpl + (size_t)(x >> 3)] &
                    (0x80 >> (x & 7)))
                    c |= 1 << pl;
            pic[k].rgba[y * w + x] = pal[c];
        }
    free(raw);
    return 0;
}

int pics_load(const unsigned char *lib, size_t len)
{
    if (len < 8 || memcmp(lib, "pcxLib", 6) != 0) {
        snprintf(err, sizeof err, "LINES.LIB: not a pcxLib archive");
        return -1;
    }
    int found = 0;
    for (size_t at = 0; at + 84 < len; at++) { /* entries: 0x01, 8.3 name, u32 size, ... 84 bytes */
        if (lib[at] != 1) continue;
        for (int k = 0; k < PIC_COUNT; k++) {
            size_t nl = strlen(names[k]);
            if (memcmp(lib + at + 1, names[k], nl) != 0 || lib[at + 1 + nl] != 0) continue;
            size_t size = (size_t)lib[at + 14] | (size_t)lib[at + 15] << 8 | (size_t)lib[at + 16] << 16 |
                          (size_t)lib[at + 17] << 24;
            if (at + 84 + size > len || decode(k, lib + at + 84, size) != 0) {
                snprintf(err, sizeof err, "LINES.LIB: %s is damaged", names[k]);
                return -1;
            }
            found |= 1 << k;
            at += 84 + size - 1;
            break;
        }
    }
    if (found != (1 << PIC_COUNT) - 1) {
        snprintf(err, sizeof err, "LINES.LIB: pictures missing");
        return -1;
    }
    return 0;
}

int pics_load_dir(const char *dir)
{
    const char *variants[2] = { "LINES.LIB", "lines.lib" };
    for (int v = 0; v < 2; v++) {
        char path[1100];
        snprintf(path, sizeof path, "%s/%s", dir, variants[v]);
        FILE *f = fopen(path, "rb");
        if (!f) continue;
        unsigned char *buf = malloc(1 << 20);
        size_t n = fread(buf, 1, 1 << 20, f);
        fclose(f);
        int r = pics_load(buf, n);
        free(buf);
        return r;
    }
    snprintf(err, sizeof err, "LINES.LIB not found in %s", dir);
    return -1;
}

void pics_init(SDL_Renderer *r)
{
    ren = r;
    for (int k = 0; k < PIC_COUNT; k++) {
        if (tex[k]) SDL_DestroyTexture(tex[k]);
        SDL_Surface *s = SDL_CreateRGBSurfaceWithFormatFrom(pic[k].rgba, pic[k].w, pic[k].h, 32, pic[k].w * 4,
                                                            SDL_PIXELFORMAT_RGBA32);
        tex[k] = SDL_CreateTextureFromSurface(r, s);
        SDL_FreeSurface(s);
    }
}

void pics_draw(int pic_id, int sx, int sy, int w, int h, int x, int y)
{
    if (pic_id < 0 || pic_id >= PIC_COUNT || !tex[pic_id]) return;
    SDL_Rect s = { sx, sy, w, h }, d = { x, y, w, h };
    SDL_RenderCopy(ren, tex[pic_id], &s, &d);
}

void pics_fill(int x, int y, int w, int h, Uint8 r, Uint8 g, Uint8 b)
{
    SDL_SetRenderDrawColor(ren, r, g, b, 255);
    SDL_Rect d = { x, y, w, h };
    SDL_RenderFillRect(ren, &d);
}
