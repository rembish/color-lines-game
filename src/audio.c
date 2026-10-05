#include "audio.h"

#include <SDL.h>

#define RATE 44100
#define QLEN 256

static SDL_AudioDeviceID dev;
static struct {
    int hz, samples;
} q[QLEN];
static int qhead, qtail;
static double phase;
static int offline;

static void callback(void *u, Uint8 *stream, int len)
{
    (void)u;
    Sint16 *out = (Sint16 *)stream;
    int n = len / 2;
    for (int i = 0; i < n; i++) {
        while (qhead != qtail && q[qhead].samples <= 0) qhead = (qhead + 1) % QLEN;
        if (qhead == qtail) {
            out[i] = 0;
            continue;
        }
        q[qhead].samples--;
        int hz = q[qhead].hz;
        if (hz <= 0) {
            out[i] = 0;
            continue;
        }
        phase += (double)hz / RATE;
        if (phase >= 1) phase -= 1;
        out[i] = phase < 0.5 ? 2400 : -2400;
    }
}

void audio_init(void)
{
    SDL_AudioSpec want = { 0 }, have;
    want.freq = RATE;
    want.format = AUDIO_S16SYS;
    want.channels = 1;
    want.samples = 512;
    want.callback = callback;
    dev = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);
    if (dev) SDL_PauseAudioDevice(dev, 0);
}

void audio_resume(void)
{
    if (dev) SDL_PauseAudioDevice(dev, 0);
}

void audio_offline(void) { offline = 1; }

void audio_render(short *out, int samples) { callback(NULL, (Uint8 *)out, samples * 2); }

static void push(int hz, int ms)
{
    if (offline) {
        int next = (qtail + 1) % QLEN;
        if (next != qhead) {
            q[qtail].hz = hz;
            q[qtail].samples = RATE * ms / 1000;
            qtail = next;
        }
        return;
    }
    if (!dev) return;
    SDL_LockAudioDevice(dev);
    int next = (qtail + 1) % QLEN;
    if (next != qhead) {
        q[qtail].hz = hz;
        q[qtail].samples = RATE * ms / 1000;
        qtail = next;
    }
    SDL_UnlockAudioDevice(dev);
}

void audio_beep(int hz, int ms) { push(hz, ms); }
