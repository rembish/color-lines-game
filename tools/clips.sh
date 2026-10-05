#!/bin/sh
# A clip of the game into clips/ (git-ignored): lines.mp4 with the PC speaker, and lines.gif, a
# six-second preview. Uses the original's pictures from original/: the clips are attached to a
# GitHub release, never committed. Needs ffmpeg and build/lines.
#   tools/clips.sh [SECONDS] [SEED] [PREVIEW_START]
set -e
cd "$(dirname "$0")/.."
SECONDS_=${1:-45}
SEED=${2:-7}
AT=${3:-12}
mkdir -p clips
./build/lines original --record clips "$SECONDS_" "$SEED"
ffmpeg -loglevel error -y -f rawvideo -pix_fmt rgb24 -s 640x350 -r 30 -i clips/lines.rgb \
    -f s16le -ar 44100 -ac 1 -i clips/lines.s16 \
    -vf scale=960:720:flags=neighbor -c:v libx264 -pix_fmt yuv420p -crf 20 \
    -c:a aac -b:a 96k -shortest -movflags +faststart clips/lines.mp4
ffmpeg -loglevel error -y -ss "$AT" -t 6 -f rawvideo -pix_fmt rgb24 -s 640x350 -r 30 -i clips/lines.rgb \
    -vf "fps=15,scale=640:480:flags=neighbor,split[a][b];[a]palettegen=max_colors=32:stats_mode=full[p];[b][p]paletteuse=dither=none" \
    -loop 0 clips/lines.gif
rm clips/lines.rgb clips/lines.s16
ls -la clips/lines.mp4 clips/lines.gif
