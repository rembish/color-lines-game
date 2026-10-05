/* A PC speaker: a queue of square-wave tones, like the original's Sound / Delay / NoSound. */
#ifndef AUDIO_H
#define AUDIO_H

void audio_init(void);
void audio_resume(void);
void audio_beep(int hz, int ms);
/* without a device (recording a clip): queue tones anyway and render them on demand */
void audio_offline(void);
void audio_render(short *out, int samples);
#define AUDIO_RATE 44100

#endif
