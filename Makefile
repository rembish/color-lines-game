# Everyday commands. The game builds with CMake alone; this only gathers the usual steps.
# `make help` lists them. The emulator checks need your copy of Color Lines in original/.

BUILD     ?= build
BUILD_WEB ?= build-web
EMSDK_ENV ?= $(HOME)/tools/emsdk/emsdk_env.sh
UV        ?= uv
CMAKE     ?= cmake
C_FILES    = core/*.c core/*.h src/*.c src/*.h tests/*.c
PY_DIRS    = re tests

.PHONY: help build web run test record difftest mutants format format-check tidy py-sync py-format py-check server check

help: ## This list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-13s %s\n", $$1, $$2}'

build: ## The game and the test tools (warnings are errors)
	$(CMAKE) -S . -B $(BUILD) -DLN_WERROR=ON
	$(CMAKE) --build $(BUILD) -j

web: SHELL := /bin/bash # emsdk_env.sh finds its folder only from bash
web: ## The browser version and the server's core (cloudflare/public, cloudflare/lib/core.wasm)
	. $(EMSDK_ENV) >/dev/null && cloudflare/build.sh

run: build ## Play, with the game's files from original/
	./$(BUILD)/lines original

test: build ## The recorded games in tests/fixtures through the core (no game files needed)
	tests/fixtures.sh $(BUILD)

record: ## Record games from the original in the emulator (re/emu/logs; SEEDS="1 2 3", ~100 s each)
	$(UV) run re/emu/record.py $(or $(SEEDS),1 2 3)

difftest: build ## The core against every recorded game in re/emu/logs, Real48 against the original
	$(UV) run tests/difftest.py $(BUILD)/replay
	$(UV) run tests/real48.py

mutants: ## The difftest catches each of the core's deliberate breakages
	$(UV) run tests/mutants.py


format: ## Format the C code (clang-format 21) and the Python (ruff)
	clang-format -i $(C_FILES)
	$(UV) run ruff format $(PY_DIRS)

format-check: ## Check formatting only
	clang-format --dry-run --Werror $(C_FILES)
	$(UV) run ruff format --check $(PY_DIRS)

tidy: build ## clang-tidy on the C code (.clang-tidy)
	clang-tidy -p $(BUILD) --quiet core/*.c src/*.c tests/*.c

py-sync: ## The Python environment (.venv) for the tools in re/
	$(UV) sync --extra dev

py-format: ## Format the Python
	$(UV) run ruff format $(PY_DIRS)

py-check: ## Python: format check, lint, strict types
	$(UV) run ruff format --check $(PY_DIRS)
	$(UV) run ruff check $(PY_DIRS)
	$(UV) run mypy

server: web ## The server's tests (cloudflare/test.mjs)
	node --test cloudflare/test.mjs

check: format-check py-check tidy test ## What CI checks (the server's tests need `make server`)
