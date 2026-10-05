#include "net.h"

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* clang-format off */
EM_JS(void, js_net_init, (void), {
    if (Module.linesNet) return;
    var id = null;
    try {
        id = localStorage.getItem('lines:id');
        if (!id) { id = crypto.randomUUID(); localStorage.setItem('lines:id', id); }
    } catch (e) { id = crypto.randomUUID(); }
    Module.linesNet = { id: id, claim: 0, game: null, result: 0, text: '', top: 0, toptext: '' };
});

EM_JS(void, js_net_post, (const char *path, const char *body, int what), {
    var net = Module.linesNet, p = UTF8ToString(path), b = JSON.parse(UTF8ToString(body));
    b.id = net.id;
    if (what === 2) b.token = net.token;
    fetch(p, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(b) })
        .then(function (r) { return r.json().then(function (j) { return [r.status, j]; }); })
        .then(function (x) {
            var st = x[0], j = x[1];
            if (what === 0) net.claim = st === 200 ? 1 : st === 409 ? 2 : 3;
            if (what === 1 && st === 200) { net.game = j.seed >>> 0; net.token = j.token; }
            if (what === 2) {
                if (st !== 200) { net.result = st === 409 ? 2 : 3; net.text = j.error || ('HTTP ' + st); return; }
                var t = j.score + ' ' + j.rank + '\n';
                j.top.forEach(function (r) { t += r.score + ' ' + r.name + '\n'; });
                net.text = t;
                net.result = 1;
            }
        })
        .catch(function (e) {
            if (what === 0) net.claim = 3;
            if (what === 2) { net.result = 3; net.text = String(e); }
        });
});

EM_JS(void, js_net_top, (void), {
    var net = Module.linesNet;
    net.top = 0;
    fetch('/api/top').then(function (r) { return r.json(); }).then(function (j) {
        var t = '';
        j.top.forEach(function (r) { t += r.score + ' ' + r.name + '\n'; });
        net.toptext = t;
        net.top = 1;
    }).catch(function () { net.top = 3; });
});

EM_JS(int, js_net_top_get, (char *buf, int max), {
    var net = Module.linesNet;
    if (net.top === 1) stringToUTF8(net.toptext, buf, max);
    return net.top;
});

EM_JS(int, js_net_get, (int what), {
    var net = Module.linesNet;
    return what === 0 ? net.claim : net.result;
});

EM_JS(int, js_net_seed, (uint32_t *seed), {
    var net = Module.linesNet;
    if (net.game === null) return 0;
    HEAPU32[seed >> 2] = net.game;
    net.game = null;
    return 1;
});

EM_JS(void, js_net_text, (char *buf, int max), { stringToUTF8(Module.linesNet.text, buf, max); });

EM_JS(void, js_net_reset, (int what), {
    var net = Module.linesNet;
    if (what === 0) net.claim = 0; else { net.result = 0; net.text = ''; }
});
/* clang-format on */

static void body(char *out, int max, const char *name, const char *moves_json)
{
    /* names are letters, digits and punctuation (the game's input), the moves are JSON numbers:
     * only quotes and backslashes need escaping */
    int n = 0;
    const char *parts[2] = { name, NULL };
    const char *keys[2] = { "name", "moves" };
    n += snprintf(out + n, (size_t)(max - n), "{");
    for (int k = 0; k < 2; k++) {
        if (!parts[k]) continue;
        n += snprintf(out + n, (size_t)(max - n), "%s\"%s\":\"", k && parts[0] ? "," : "", keys[k]);
        for (const char *s = parts[k]; *s && n < max - 4; s++) {
            if (*s == '"' || *s == '\\') out[n++] = '\\';
            out[n++] = *s;
        }
        out[n++] = '"';
    }
    if (moves_json) n += snprintf(out + n, (size_t)(max - n), ",\"moves\":%s", moves_json);
    snprintf(out + n, (size_t)(max - n), "}");
}

void net_claim(const char *name)
{
    char b[256];
    js_net_init();
    js_net_reset(0);
    body(b, sizeof b, name, NULL);
    js_net_post("/api/name", b, 0);
}
int net_claim_status(void) { return js_net_get(0); }

void net_new_game(void)
{
    js_net_init();
    js_net_post("/api/game", "{}", 1);
}
int net_game_seed(uint32_t *seed) { return js_net_seed(seed); }

void net_submit(const char *name, const char *moves_json)
{
    size_t max = strlen(moves_json) + 256;
    char *b = malloc(max);
    if (!b) return;
    js_net_reset(1);
    body(b, (int)max, name, moves_json);
    js_net_post("/api/result", b, 2);
    free(b);
}

void net_top(void)
{
    js_net_init();
    js_net_top();
}
int net_top_result(char *buf, int max) { return js_net_top_get(buf, max); }

int net_result(char *buf, int max)
{
    int r = js_net_get(1);
    if (r != NET_PENDING) js_net_text(buf, max);
    return r;
}

#else

void net_claim(const char *name) { (void)name; }
int net_claim_status(void) { return NET_FAILED; }
void net_new_game(void) {}
int net_game_seed(uint32_t *seed)
{
    *seed = 0;
    return 0;
}
void net_submit(const char *name, const char *moves_json)
{
    (void)name;
    (void)moves_json;
}
void net_top(void) {}
int net_top_result(char *buf, int max)
{
    if (max > 0) buf[0] = 0;
    return NET_FAILED;
}
int net_result(char *buf, int max)
{
    if (max > 0) buf[0] = 0;
    return NET_FAILED;
}

#endif
