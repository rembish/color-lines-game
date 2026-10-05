cmake_minimum_required(VERSION 3.16)
project(lines C)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_library(lncore STATIC core/ln_core.c core/ln_real48.c)
target_include_directories(lncore PUBLIC core)

option(LN_WERROR "Treat warnings as errors (CI)" OFF)
if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(lncore PRIVATE -Wall -Wextra -Wpedantic -Wshadow -Wconversion
    -Wsign-conversion -Wcast-qual -Wstrict-prototypes -Wmissing-prototypes)
  if(LN_WERROR)
    target_compile_options(lncore PRIVATE -Werror)
  endif()
endif()

# Replays a game from a seed and the moves; tests/difftest.py checks it against the original's
# games from re/emu/record.py.
add_executable(replay tests/replay.c)
target_link_libraries(replay PRIVATE lncore)

# One Real48 operation per input line; tests/real48.py checks it against the original's System.
add_executable(real48 tests/real48.c)
target_link_libraries(real48 PRIVATE lncore)

# The game. It reads LINES.LIB from the player's own copy at run time.
add_executable(lines src/main.c src/pics.c src/top.c src/store.c src/audio.c src/net.c)
target_link_libraries(lines PRIVATE lncore)
if(EMSCRIPTEN)
  target_compile_options(lines PRIVATE -sUSE_SDL=2)
  target_link_options(lines PRIVATE -sUSE_SDL=2 -sALLOW_MEMORY_GROWTH=1 -sINVOKE_RUN=0 -sEXIT_RUNTIME=0
    -sFORCE_FILESYSTEM=1 -lidbfs.js "-sEXPORTED_RUNTIME_METHODS=['callMain','FS','IDBFS']"
    --shell-file ${CMAKE_CURRENT_SOURCE_DIR}/web/shell.html)
  set_target_properties(lines PROPERTIES SUFFIX ".html")
else()
  find_package(SDL2 REQUIRED)
  target_link_libraries(lines PRIVATE SDL2::SDL2)
  if(TARGET SDL2::SDL2main)
    target_link_libraries(lines PRIVATE SDL2::SDL2main)
  endif()
endif()
if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
  foreach(t lines replay real48)
    target_compile_options(${t} PRIVATE -Wall -Wextra -Wpedantic -Wshadow)
    if(LN_WERROR)
      target_compile_options(${t} PRIVATE -Werror)
    endif()
  endforeach()
endif()
