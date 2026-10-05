/* The original's pictures (LINES.LIB, a Genus "pcxLib" archive of five 16-colour PCX files),
 * read at run time from the player's own copy of the game. Nothing of them is in this
 * repository. Everything is drawn in the original's 640x350 coordinates. */
#ifndef LINES_PICS_H
#define LINES_PICS_H

#include <SDL.h>
#include <stddef.h>

#define SCREEN_W 640
#define SCREEN_H 350

enum { PIC_FIELD, PIC_SPRITES, PIC_TRUMPETERS, PIC_TITLE, PIC_CELLS, PIC_COUNT };

int pics_load(const unsigned char *lib, size_t len); /* 0 on success, see pics_error() */
int pics_load_dir(const char *dir);                  /* LINES.LIB in dir, any case */
const char *pics_error(void);
void pics_init(SDL_Renderer *r);
/* part of a picture: (sx, sy, w, h) drawn with its top-left at (x, y) */
void pics_draw(int pic_id, int sx, int sy, int w, int h, int x, int y);
void pics_fill(int x, int y, int w, int h, Uint8 r, Uint8 g, Uint8 b);

/* The field as the original's screen: a copy of FL_LNS20 the kings are moved and redrawn on,
 * as LINES.EXE moves them with screen-to-screen copies (0a72, 086e). */
void pics_field_reset(void);
/* move the rectangle (x, y, w, h) of the field by (dx, dy) */
void pics_field_move(int x, int y, int w, int h, int dx, int dy);
/* draw part of a picture onto the field */
void pics_field_put(int pic_id, int sx, int sy, int w, int h, int x, int y);
void pics_field_draw(void);

#endif
