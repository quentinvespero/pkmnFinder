# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Launch the GUI
uv run python main.py

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_pokemon_decoder.py

# Run a single test by name
uv run pytest tests/test_pokemon_decoder.py::test_shiny_detected

# Lint
uv run ruff check .

# Format
uv run ruff format .
```

## mgba Installation

The `mgba` Python package must be installed separately (no cp313 wheel on PyPI). On macOS arm64 with Python 3.13:

```bash
brew install cmake ffmpeg libzip pkg-config sdl2 libpng
uv pip install setuptools pytest-runner cached-property
git clone --depth=1 https://github.com/mgba-emu/mgba /tmp/mgba
mkdir /tmp/mgba-build && cd /tmp/mgba-build
cmake /tmp/mgba -DBUILD_PYTHON=ON \
  -DPYTHON_EXECUTABLE=$(uv run python -c "import sys; print(sys.executable)") \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_QT=OFF -DBUILD_SDL=OFF
make -j$(sysctl -n hw.logicalcpu) mgba-py
cp -r /tmp/mgba-build/python/lib.macosx-*/mgba .venv/lib/python3.13/site-packages/
```

## Architecture

The app runs N parallel headless mGBA instances that hunt for a target shiny Pokémon. When found, the GUI is notified via Qt signals and a winning save state is written to `saves/`.

### Data flow

```
ROM file → LibmgbaEmulator (emulator/core.py)
         → GameProfile.for_rom_code() selects game (games/base.py)
         → SymbolTable.from_file() loads .sym (memory/symbols.py)
         → MemoryReader provides typed reads (memory/reader.py)
         → BattleStateReader / EncounterReader / PlayerStateReader (game_state/)
         → WildHuntAutomation or SoftResetAutomation (automation/)
         → HuntInstance (QRunnable) wraps one emulator + automation (hunt/instance.py)
         → HuntCoordinator spawns N instances in QThreadPool (hunt/coordinator.py)
         → Qt signals → MainWindow / InstanceGrid (gui/)
```

### Threading model

- `HuntCoordinator` lives in the main thread and owns a `threading.Event` (`stop_event`)
- Each `HuntInstance` runs in a `QThreadPool` worker thread; it never touches Qt widgets
- mGBA releases the GIL during `run_frame()`, enabling true CPU parallelism
- All GUI updates happen via `pyqtSignal` with `AutoConnection` (queued across thread boundaries)
- Clean shutdown: `stop_event.set()` → each automation checks it between frames via `StopRequested`

### Pokemon decryption (pokemon/)

Gen 3 party slots (100 bytes) are XOR-encrypted. Decryption:
1. XOR key = `PID ^ OT_ID` repeated as a 4-byte little-endian pattern
2. The 4 substructures (G=Growth, A=Attacks, E=EVs, M=Misc), each 12 bytes, are permuted in one of 24 orderings determined by `PID % 24` using `_ORDER_TABLE` in `decoder.py`
3. Shiny check: `(TID XOR SID XOR (PID >> 16) XOR (PID & 0xFFFF)) < 8`

### Symbol tables (memory/)

Memory addresses are resolved by symbol name from `.sym` files sourced from the [pret](https://github.com/pret) decompilations, stored in `pokefinder/games/symbols/`. This avoids hardcoded addresses that break across ROM revisions. `SymbolTable` parses these files; `MemoryReader` wraps `LibmgbaEmulator` to provide typed reads by symbol name.

### Battle detection

`BattleStateReader.in_battle()` checks `gMain.callback1 == BattleMainCB1` (more reliable than flag-based checks).

### Soft-reset positioning

The save state (`.ss1`) must be taken at the **last frame before** the encounter is generated (i.e., one frame before pressing A on a starter ball or legendary). `SoftResetAutomation` loads the state, presses A once, then waits for `BattleMainCB1`.

### Game profiles (games/)

`GameProfile.for_rom_code(code)` maps a 4-char ROM code to the correct profile:

| ROM code | Game |
|----------|------|
| BPEE | Emerald |
| AXVE | Ruby |
| AXPE | Sapphire |
| BPRE | FireRed |
| BPGE | LeafGreen |
