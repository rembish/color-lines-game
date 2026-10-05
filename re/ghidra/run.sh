#!/bin/sh
# Import LINES.EXE into a headless Ghidra project and dump decompiled C to lines_decomp.c.
# Needs GHIDRA (default ~/tools/ghidra_*).
set -e
cd "$(dirname "$0")"
GHIDRA=${GHIDRA:-$(ls -d ~/tools/ghidra_*_PUBLIC | tail -1)}
mkdir -p proj
touch names.txt
"$GHIDRA/support/analyzeHeadless" "$PWD/proj" lines -import "$PWD/../../original/LINES.EXE" -overwrite \
    -scriptPath "$PWD" -postScript ApplyNames.java "$PWD/names.txt" \
    -postScript DumpAll.java "$PWD/lines_decomp.c" > headless.log 2>&1
echo "lines: $(grep -c '=====' lines_decomp.c) functions"
