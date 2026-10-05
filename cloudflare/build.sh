#!/bin/sh
# Builds what the Pages project serves: the web game into public/, the core into lib/core.wasm.
# Needs Emscripten (source emsdk_env.sh first).
set -e
cd "$(dirname "$0")/.."
emcmake cmake -S . -B build-web -DCMAKE_BUILD_TYPE=Release > /dev/null
cmake --build build-web -j --target lines
emcc -O2 -Icore core/ln_core.c core/ln_real48.c core/ln_wasm.c -sSTANDALONE_WASM --no-entry \
    -o cloudflare/lib/core.wasm
rm -rf cloudflare/public
mkdir -p cloudflare/public
cp build-web/lines.html cloudflare/public/index.html
cp build-web/lines.js build-web/lines.wasm cloudflare/public/
cp LICENSE cloudflare/public/LICENSE.txt
