/* Color Lines (1992) for SDL2: the original's rules from core/, its pictures from the player's
 * own LINES.LIB, on the original's 640x350 screen. Positions and sprite cells are the ones
 * LINES.EXE sets up in init (1000:346f); see re/NOTES.md. */
#include <SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif

#include "audio.h"
#include "ln_core.h"
#include "pics.h"
#include "store.h"
#include "top.h"

#define SCALE 3

enum { SC_TITLE, SC_GAME, SC_HELP, SC_NAME, SC_TOP };
enum { AN_NONE, AN_MOVE, AN_VANISH, AN_GROW };

static SDL_Window *win;
static SDL_Renderer *ren;
static SDL_Texture *screen;
static int running = 1, sc = SC_TITLE;
static Uint32 now;

static ln_game G;
static ln_game shown;                  /* what the board shows while an animation runs */
static int cur_x = 5, cur_y = 5;       /* keyboard cursor, cells 1..9 */
static int sel_x, sel_y;               /* selected ball, 0 = none */
static ln_time t0;                     /* read at the top of each turn */
static int sound_on = 1, next_on = 1;
static int anim, anim_step;
static Uint32 anim_t;
static int path_x[82], path_y[82], path_n;
static int demo;
static top_table top;
static char name_buf[TOP_NAME + 1];
static int new_rank;                   /* 1..10 where the new score went, 0 none */
static int ignore_text;

/* the original's screen positions (init, 346f) */
#define CELL_X(x) (170 + 34 * ((x) - 1))
#define CELL_Y(y) (60 + 24 * ((y) - 1))
#define BALL_X 43                      /* sprite sheet: the ball on its cell */
#define TINY_X 77
#define SMALL_X 111
#define SQUASH_X 145
#define GONE1_X 179
#define GONE2_X 213
#define ROW_Y(c) (170 + 24 * ((c) - 1))
#define EMPTY_X 247                    /* an empty cell */
#define EMPTY_Y 314
#define PANEL_X 204
#define PANEL_Y 84

static ln_time clock_now(void)
{
    time_t t = time(NULL);
    struct tm *tm = localtime(&t);
    ln_time c = { (uint16_t)tm->tm_hour, (uint16_t)tm->tm_min, (uint16_t)tm->tm_sec,
                  (uint16_t)(SDL_GetTicks() / 10 % 100) };
    return c;
}

static void beep(int hz, int ms)
{
    if (sound_on) audio_beep(hz, ms);
}

/* ---- drawing ---- */

static void ball(int c, int sx, int x, int y, int dy)
{
    if (c) pics_draw(PIC_SPRITES, sx, ROW_Y(c) + dy, 34, 24 - dy, CELL_X(x), CELL_Y(y));
}

static void digits(unsigned v, int right, int y)
{
    for (int k = 1; k <= 7; k++) {
        int x = right - 9 * k;
        if (v || k == 1)
            pics_draw(PIC_SPRITES, 462 + 9 * (int)(v % 10), 304, 9, 8, x, y);
        else
            pics_draw(PIC_SPRITES, 281, 314, 9, 8, x, y);
        v /= 10;
    }
}

/* the sheet's font: ASCII 32..122 in three rows of 9-pixel cells */
static int text(const char *s, int x, int y)
{
    for (; *s; s++, x += 9) {
        int c = (unsigned char)*s;
        if (c < 32 || c > 122) c = '?';
        int row = c <= 0x40 ? 305 : c <= 0x60 ? 317 : 329, base = c <= 0x40 ? 32 : c <= 0x60 ? 0x41 : 0x61;
        if (c != ' ') pics_draw(PIC_SPRITES, 318 + 9 * (c - base), row, 9, 10, x, y);
    }
    return x;
}

static void labels(void)
{
    static const int at[4] = { 138, 271, 405, 538 };
    int lit[4] = { sc == SC_HELP, sound_on, next_on, 0 };
    for (int j = 0; j < 4; j++) pics_draw(PIC_SPRITES, 148 * j + 74 * lit[j], 340, 72, 10, at[j], 323);
}

static void draw_board(void)
{
    const ln_game *b = anim ? &shown : &G;
    for (int y = 1; y <= 9; y++)
        for (int x = 1; x <= 9; x++) {
            int c = b->board[x][y];
            if (!c) continue;
            int dy = 0;
            if (x == sel_x && y == sel_y && !anim) {
                static const int bounce[8] = { 0, 1, 2, 3, 3, 2, 1, 0 };
                dy = bounce[now / 60 % 8];
            }
            pics_draw(PIC_SPRITES, EMPTY_X, EMPTY_Y, 34, 24, CELL_X(x), CELL_Y(y));
            ball(c, BALL_X, x, y, dy);
        }
}

static void draw_game(void)
{
    pics_draw(PIC_FIELD, 0, 0, SCREEN_W, SCREEN_H, 0, 0);
    draw_board();
    if (anim == AN_MOVE) {
        int c = shown.colour;
        int k = anim_step < path_n ? anim_step : path_n - 1;
        pics_draw(PIC_SPRITES, BALL_X, ROW_Y(c), 34, 24, CELL_X(path_x[k]), CELL_Y(path_y[k]));
    }
    if (anim == AN_VANISH || anim == AN_GROW) {
        for (int y = 1; y <= 9; y++)
            for (int x = 1; x <= 9; x++) {
                int a = shown.board[x][y], b = G.board[x][y];
                if (anim == AN_VANISH && a && !b)
                    pics_draw(PIC_SPRITES, anim_step ? GONE2_X : GONE1_X, ROW_Y(a), 34, 24, CELL_X(x), CELL_Y(y));
                if (anim == AN_GROW && !a && b)
                    pics_draw(PIC_SPRITES, anim_step == 0 ? TINY_X : anim_step == 1 ? SMALL_X : BALL_X, ROW_Y(b),
                              34, 24, CELL_X(x), CELL_Y(y));
            }
    }
    for (int i = 1; i <= 3; i++) {
        int x = 271 + 34 * (i - 1);
        if (next_on && i <= G.next_count)
            pics_draw(PIC_SPRITES, SMALL_X, ROW_Y(G.next[i]), 34, 24, x, 4);
        else
            pics_draw(PIC_SPRITES, EMPTY_X, EMPTY_Y, 34, 24, x, 4);
    }
    digits(top.score[0], 120, 12);
    digits(G.score, 572, 12);
    labels();
    if (!demo) { /* the keyboard cursor */
        SDL_SetRenderDrawColor(ren, 255, 255, 85, 255);
        SDL_Rect r = { CELL_X(cur_x), CELL_Y(cur_y), 34, 24 };
        SDL_RenderDrawRect(ren, &r);
    }
}

static void draw_top(void)
{
    pics_draw(PIC_SPRITES, 0, 0, 239, 169, PANEL_X, PANEL_Y);
    for (int k = 0; k < TOP_N; k++) {
        int y = PANEL_Y + 31 + 10 * k;
        text(top.name[k], PANEL_X + 52, y);
        char s[8];
        snprintf(s, sizeof s, "%5u", top.score[k]);
        text(s, PANEL_X + 209 - 45, y);
    }
    if (sc == SC_NAME) {
        int x = text(name_buf, PANEL_X + 120, PANEL_Y + 148);
        if (now / 300 % 2) pics_fill(x, PANEL_Y + 157, 8, 1, 255, 255, 85);
    }
}

static void render(void)
{
    SDL_SetRenderTarget(ren, screen);
    SDL_RenderSetScale(ren, SCALE, SCALE);
    if (sc == SC_TITLE)
        pics_draw(PIC_TITLE, 0, 0, SCREEN_W, SCREEN_H, 0, 0);
    else {
        draw_game();
        if (sc == SC_HELP) pics_draw(PIC_SPRITES, 238, 0, 239, 169, PANEL_X, PANEL_Y);
        if (sc == SC_NAME || sc == SC_TOP) draw_top();
    }
    SDL_RenderSetScale(ren, 1, 1);
}

static void present(void)
{
    SDL_SetRenderTarget(ren, NULL);
    SDL_SetRenderDrawColor(ren, 0, 0, 0, 255);
    SDL_RenderClear(ren);
    int w, h;
    SDL_GetRendererOutputSize(ren, &w, &h);
    int dw = w, dh = w * 3 / 4;
    if (dh > h) {
        dh = h;
        dw = h * 4 / 3;
    }
    SDL_Rect d = { (w - dw) / 2, (h - dh) / 2, dw, dh };
    SDL_RenderCopy(ren, screen, NULL, &d);
    SDL_RenderPresent(ren);
}

/* ---- game ---- */

static void new_game(uint32_t seed)
{
    ln_new_game(&G, seed);
    sel_x = sel_y = 0;
    anim = AN_NONE;
    t0 = clock_now();
    sc = SC_GAME;
}

static void game_over(void)
{
    new_rank = top_rank(&top, G.score);
    if (new_rank) {
        name_buf[0] = 0;
        ignore_text = 1;
        SDL_StartTextInput();
        sc = SC_NAME;
    } else
        sc = SC_TOP;
}

/* the route the ball takes (cosmetic, like the original's: breadth-first from the ball, the
 * neighbours up, down, left, right) */
static void route(int fx, int fy, int tx, int ty)
{
    int px[10][10], py[10][10], seen[10][10] = { { 0 } }, qx[81], qy[81], h = 0, t = 0;
    static const int dx[4] = { 0, 0, -1, 1 }, dy[4] = { -1, 1, 0, 0 };
    qx[t] = fx, qy[t++] = fy;
    seen[fx][fy] = 1;
    while (h < t) {
        int x = qx[h], y = qy[h++];
        for (int d = 0; d < 4; d++) {
            int nx = x + dx[d], ny = y + dy[d];
            if (nx < 1 || nx > 9 || ny < 1 || ny > 9 || seen[nx][ny] || G.board[nx][ny]) continue;
            seen[nx][ny] = 1;
            px[nx][ny] = x, py[nx][ny] = y;
            qx[t] = nx, qy[t++] = ny;
        }
    }
    int rx[82], ry[82], n = 0, x = tx, y = ty;
    while (!(x == fx && y == fy) && n < 81) {
        rx[n] = x, ry[n++] = y;
        int ox = px[x][y];
        y = py[x][y];
        x = ox;
    }
    rx[n] = fx, ry[n++] = fy;
    path_n = n;
    for (int k = 0; k < n; k++) path_x[k] = rx[n - 1 - k], path_y[k] = ry[n - 1 - k];
}

static void click_cell(int x, int y)
{
    if (anim) return;
    if (G.board[x][y]) { /* (re)select */
        sel_x = x, sel_y = y;
        return;
    }
    if (!sel_x) return;
    if (!ln_reachable(&G, sel_x, sel_y, x, y)) {
        beep(220, 200);
        return;
    }
    ln_time t1 = clock_now();
    shown = G;
    route(sel_x, sel_y, x, y);
    shown.colour = G.board[sel_x][sel_y];
    shown.board[sel_x][sel_y] = 0;
    ln_move(&G, sel_x, sel_y, x, y, t0, t1);
    sel_x = sel_y = 0;
    anim = AN_MOVE;
    anim_step = 0;
    anim_t = now;
}

static void animate(void)
{
    Uint32 step = anim == AN_MOVE ? (demo ? 10u : 30u) : (demo ? 30u : 90u);
    if (now - anim_t < step) return;
    anim_t = now;
    anim_step++;
    if (anim == AN_MOVE && anim_step >= path_n) {
        shown.board[path_x[path_n - 1]][path_y[path_n - 1]] = shown.colour;
        if (sound_on) audio_beep(40, 20);
        int gone = 0, grown = 0;
        for (int y = 1; y <= 9; y++)
            for (int x = 1; x <= 9; x++) {
                gone += shown.board[x][y] && !G.board[x][y];
                grown += !shown.board[x][y] && G.board[x][y];
            }
        anim = gone ? AN_VANISH : grown ? AN_GROW : AN_NONE;
        anim_step = 0;
        if (gone) beep(40, 20);
    } else if (anim == AN_VANISH && anim_step >= 2) {
        for (int y = 1; y <= 9; y++)
            for (int x = 1; x <= 9; x++)
                if (shown.board[x][y] && !G.board[x][y]) shown.board[x][y] = 0;
        int grown = 0;
        for (int y = 1; y <= 9; y++)
            for (int x = 1; x <= 9; x++) grown += !shown.board[x][y] && G.board[x][y];
        anim = grown ? AN_GROW : AN_NONE;
        anim_step = 0;
    } else if (anim == AN_GROW && anim_step >= 3)
        anim = AN_NONE;
    if (anim == AN_NONE) {
        t0 = clock_now(); /* the top of the next turn */
        if (ln_game_over(&G)) game_over();
    }
}

/* the demo plays like the bot in re/emu/record.py: the longest line it can make */
static void demo_move(void)
{
    int best = -1, bx = 0, by = 0, tx = 0, ty = 0, n = 0;
    for (int y = 1; y <= 9; y++)
        for (int x = 1; x <= 9; x++) {
            int c = G.board[x][y];
            if (!c) continue;
            for (int v = 1; v <= 9; v++)
                for (int u = 1; u <= 9; u++) {
                    if (!ln_reachable(&G, x, y, u, v)) continue;
                    int len = 0;
                    static const int dirs[4][2] = { { 1, 0 }, { 0, 1 }, { 1, 1 }, { 1, -1 } };
                    for (int d = 0; d < 4; d++) {
                        int m = 1;
                        for (int s = -1; s <= 1; s += 2)
                            for (int k = 1;; k++) {
                                int a = u + s * k * dirs[d][0], b = v + s * k * dirs[d][1];
                                if (a < 1 || a > 9 || b < 1 || b > 9 || (a == x && b == y) || G.board[a][b] != c) break;
                                m++;
                            }
                        if (m > len) len = m;
                    }
                    if (len > best || (len == best && rand() % ++n == 0)) {
                        if (len > best) n = 1;
                        best = len, bx = x, by = y, tx = u, ty = v;
                    }
                }
        }
    if (best < 0) return;
    sel_x = bx, sel_y = by;
    click_cell(tx, ty);
}

/* ---- input ---- */

static void key(SDL_Keysym ks)
{
    if (ks.sym == SDLK_F11 || (ks.sym == SDLK_RETURN && (ks.mod & KMOD_ALT))) {
        Uint32 fs = SDL_GetWindowFlags(win) & SDL_WINDOW_FULLSCREEN_DESKTOP;
        SDL_SetWindowFullscreen(win, fs ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP);
        return;
    }
    switch (sc) {
    case SC_TITLE:
        if (ks.sym == SDLK_ESCAPE)
            running = 0;
        else
            new_game((uint32_t)time(NULL) ^ (uint32_t)SDL_GetPerformanceCounter());
        break;
    case SC_HELP: sc = SC_GAME; break;
    case SC_TOP: sc = SC_TITLE; break;
    case SC_NAME:
        if (ks.sym == SDLK_BACKSPACE && name_buf[0])
            name_buf[strlen(name_buf) - 1] = 0;
        else if (ks.sym == SDLK_RETURN || ks.sym == SDLK_KP_ENTER) {
            SDL_StopTextInput();
            top_insert(&top, new_rank, name_buf[0] ? name_buf : "Anonymous", G.score);
            top_save(&top);
            sc = SC_TOP;
        }
        break;
    case SC_GAME:
        switch (ks.sym) {
        case SDLK_LEFT: if (cur_x > 1) cur_x--; break;
        case SDLK_RIGHT: if (cur_x < 9) cur_x++; break;
        case SDLK_UP: if (cur_y > 1) cur_y--; break;
        case SDLK_DOWN: if (cur_y < 9) cur_y++; break;
        case SDLK_SPACE: case SDLK_RETURN: click_cell(cur_x, cur_y); break;
        case SDLK_F1: sc = SC_HELP; break;
        case SDLK_F2: sound_on = !sound_on; break;
        case SDLK_F3: next_on = !next_on; break;
        case SDLK_F4: if (!anim) game_over(); break; /* restart: the Top Ten all the same */
        case SDLK_ESCAPE: sc = SC_TITLE; break;
        default: break;
        }
        break;
    default: break;
    }
}

static void click(int wx, int wy)
{
    int w, h, ww, wh;
    SDL_GetRendererOutputSize(ren, &w, &h);
    SDL_GetWindowSize(win, &ww, &wh);
    int dw = w, dh = w * 3 / 4;
    if (dh > h) {
        dh = h;
        dw = h * 4 / 3;
    }
    float k = (float)w / (float)ww;
    int x = (int)((wx * k - (float)(w - dw) / 2) * SCREEN_W / (float)dw);
    int y = (int)((wy * k - (float)(h - dh) / 2) * SCREEN_H / (float)dh);
    if (sc == SC_GAME) {
        int cx = (x - 0x88) / 0x22, cy = (y - 0x24) / 0x18; /* as the original computes it */
        if (x >= 170 && y >= 60 && cx >= 1 && cx <= 9 && cy >= 1 && cy <= 9) {
            cur_x = cx, cur_y = cy;
            click_cell(cx, cy);
        } else if (y >= 315 && y < 340) { /* the F-key buttons */
            static const int at[4] = { 98, 231, 365, 498 };
            for (int j = 0; j < 4; j++)
                if (x >= at[j] && x < at[j] + 112) {
                    SDL_Keysym ks = { 0 };
                    ks.sym = SDLK_F1 + j;
                    key(ks);
                }
        }
    } else if (sc != SC_NAME) {
        SDL_Keysym ks = { 0 };
        ks.sym = SDLK_SPACE;
        key(ks);
    }
}

static void text_input(const char *t)
{
    if (sc != SC_NAME || ignore_text) return;
    for (; *t; t++)
        if ((unsigned char)*t >= 32 && (unsigned char)*t <= 122 && strlen(name_buf) < TOP_NAME) {
            size_t n = strlen(name_buf);
            name_buf[n] = *t;
            name_buf[n + 1] = 0;
        }
}

static void frame(void)
{
    SDL_Event e;
    while (SDL_PollEvent(&e)) {
        if (e.type == SDL_QUIT) running = 0;
        if (e.type == SDL_KEYDOWN) {
            audio_resume();
            key(e.key.keysym);
        }
        if (e.type == SDL_TEXTINPUT) text_input(e.text.text);
        if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) {
            audio_resume();
            click(e.button.x, e.button.y);
        }
    }
    ignore_text = 0;
    now = SDL_GetTicks();
    if (sc == SC_GAME) {
        if (anim) animate();
        else if (demo && now - anim_t > 150) demo_move();
    }
    if (demo && sc == SC_TOP && now - anim_t > 3000) new_game((uint32_t)rand());
    if (demo && sc == SC_NAME) {
        snprintf(name_buf, sizeof name_buf, "Demo");
        SDL_Keysym ks = { 0 };
        ks.sym = SDLK_RETURN;
        key(ks);
        anim_t = now;
    }
    render();
    present();
#ifdef __EMSCRIPTEN__
    if (!running) emscripten_cancel_main_loop();
#endif
}

/* --shot FILE WHAT: a screen to a BMP (title, game, top, help) */
static int shot(const char *file, const char *what)
{
    now = 1000;
    top_readonly = 1;
    new_game(7);
    if (!strcmp(what, "title")) sc = SC_TITLE;
    if (!strcmp(what, "help")) sc = SC_HELP;
    if (!strcmp(what, "top")) sc = SC_TOP;
    if (!strncmp(what, "game", 4)) {
        demo = 1;
        for (int i = 0; i < atoi(what + 4 + (what[4] == ':')) * 200 && sc == SC_GAME; i++) {
            now += 20;
            if (anim)
                animate();
            else
                demo_move();
        }
        demo = 0;
    }
    render();
    SDL_SetRenderTarget(ren, screen);
    SDL_Surface *s = SDL_CreateRGBSurfaceWithFormat(0, SCREEN_W * SCALE, SCREEN_H * SCALE, 32, SDL_PIXELFORMAT_ARGB8888);
    SDL_RenderReadPixels(ren, NULL, SDL_PIXELFORMAT_ARGB8888, s->pixels, s->pitch);
    int r = SDL_SaveBMP(s, file);
    SDL_FreeSurface(s);
    return r;
}

int main(int argc, char **argv)
{
    const char *shot_file = NULL, *shot_what = "title", *dir = NULL;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--shot") && i + 2 < argc) {
            shot_file = argv[i + 1];
            shot_what = argv[i + 2];
            i += 2;
        } else if (!strcmp(argv[i], "--demo"))
            demo = 1;
        else if (argv[i][0] != '-')
            dir = argv[i];
    }
    if (shot_file) SDL_SetHint(SDL_HINT_VIDEODRIVER, "dummy");
    if (SDL_Init(SDL_INIT_VIDEO | (shot_file ? 0 : SDL_INIT_AUDIO)) != 0) {
        fprintf(stderr, "SDL: %s\n", SDL_GetError());
        return 1;
    }
    store_init();
    top_load(&top);
    const char *dirs[4] = { dir ? dir : "original", "original", ".", NULL };
    int ok = 0;
    for (int i = 0; dirs[i] && !ok; i++) ok = pics_load_dir(dirs[i]) == 0;
    if (!ok) {
        fprintf(stderr, "lines: LINES.LIB from your copy of the game is needed (%s)\n", pics_error());
        return 1;
    }
    win = SDL_CreateWindow("Color Lines", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, 1280, 960,
                           SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI | (shot_file ? SDL_WINDOW_HIDDEN : 0));
    ren = SDL_CreateRenderer(win, -1,
                             shot_file ? SDL_RENDERER_SOFTWARE : SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    if (!ren) ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_SOFTWARE);
    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "nearest");
    pics_init(ren);
    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "linear");
    screen = SDL_CreateTexture(ren, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_TARGET, SCREEN_W * SCALE,
                               SCREEN_H * SCALE);
    if (shot_file) return shot(shot_file, shot_what) == 0 ? 0 : 1;
    audio_init();
    srand((unsigned)time(NULL));
    if (demo) new_game((uint32_t)time(NULL));
#ifdef __EMSCRIPTEN__
    emscripten_set_main_loop(frame, 0, 1);
#else
    while (running) frame();
#endif
    SDL_Quit();
    return 0;
}
