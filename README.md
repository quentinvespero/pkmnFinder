# Pokemon Finder

Autonomous GBA Pokemon shiny hunter with multi-instance support.

Runs multiple headless mGBA emulator instances in parallel to hunt for a
target Pokemon (optionally shiny-only) in FireRed/LeafGreen, Ruby/Sapphire,
and Emerald. A PyQt6 GUI shows per-instance stats in real time and opens
a dialog when the target is found.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- mGBA Python bindings (see below)
- A legally-owned GBA ROM (.gba)

## Installing dependencies

```bash
uv sync
```

## Installing mGBA Python bindings

The `mgba` Python package must be installed separately — choose one of the
options below based on your platform.

### Option A: PyPI wheel (try first)

```bash
uv add mgba
```

This works on some platforms. If it fails, use Option B or C.

### Option B: pokebot-gen3 pre-built wheel (most reliable for macOS arm64)

Download the wheel from the
[pokebot-gen3 releases page](https://github.com/40Cakes/pokebot-gen3/releases)
and install it:

```bash
# Example for macOS arm64, Python 3.12:
uv pip install libmgba_py-0.2.0-cp312-cp312-macosx_14_0_arm64.whl
```

### Option C: Build from source (macOS)

```bash
brew install cmake ffmpeg libzip sdl2 libedit lua pkg-config

git clone https://github.com/hanzi/libmgba-py /tmp/libmgba-py
cd /tmp/libmgba-py
./build_mac.sh

# Then install the built wheel:
uv pip install dist/mgba-*.whl
```

## Running

```bash
uv run python main.py
```

Or without uv:

```bash
python main.py
```

## Usage

1. Click **Browse…** to select your `.gba` ROM file (place ROMs in the `roms/`
   directory for convenience — it is git-ignored).
2. Select the target species using the search box and dropdown.
3. Check **Shiny only** if you want only shiny specimens.
4. Choose the hunt method:
   - **Wild encounters**: the emulator walks in grass, fleeing from non-target
     or non-shiny Pokemon.
   - **Soft resets**: requires a pre-positioned save state (`.ss1`) saved just
     before the encounter is generated (starter selection screen or in front of
     a legendary). Browse to the state file.
5. Set the number of parallel instances (4 is a good starting point; more
   instances = faster hunting but higher CPU usage).
6. Click **Start Hunt**.

When the target is found, a dialog displays the Pokemon's stats and the
winning save state is written to `saves/`.

## Running tests

```bash
uv run pytest
```

## Project structure

```
pokemon-finder/
├── main.py                        # Entry point
├── pokefinder/
│   ├── emulator/                  # mGBA wrapper
│   ├── games/                     # Per-game profiles + .sym files
│   ├── memory/                    # Symbol table + typed memory reader
│   ├── pokemon/                   # Gen 3 struct decoder + shiny formula
│   ├── game_state/                # Battle / player / encounter readers
│   ├── automation/                # Frame-counted state machines
│   ├── hunt/                      # Config, instance (QRunnable), coordinator
│   └── gui/                       # PyQt6 interface
├── data/
│   └── species_names.json         # National Dex ID → name
├── roms/                          # Place .gba files here (git-ignored)
└── saves/                         # Winning save states (git-ignored)
```

## Architecture notes

### mGBA + GIL
mGBA releases the GIL during `run_frame()`, allowing true CPU parallelism
across multiple `QThreadPool` worker threads. If you observe serialization
(all instances running at the same speed as one), switch each instance to a
`multiprocessing.Process` and replace Qt signals with `multiprocessing.Queue`.

### Pokemon decryption
Gen 3 party slots are XOR-encrypted with `PID ^ OT_ID`. The 4 substructures
(Growth, Attacks, EVs, Misc) are arranged in one of 24 orderings determined
by `PID % 24`. The decoder in `pokefinder/pokemon/decoder.py` implements the
full Bulbapedia specification with unit tests for all 24 orderings.

### Symbol tables
Memory addresses are looked up by symbol name from `.sym` files (sourced from
the [pret](https://github.com/pret) decompilation projects). This avoids
hardcoded addresses that would break across ROM revisions.

### Soft reset positioning
For soft-reset hunts, save the state at the **last frame before** the game
generates the encounter (i.e., the frame before you press A on the starter
ball or legendary). The automation presses A once after loading the state,
then waits for `gMain.callback1 == BattleMainCB1`.

## Supported games

| Game | ROM code | .sym source |
|------|----------|------------|
| Pokemon Emerald | BPEE | pokeemerald |
| Pokemon Ruby | AXVE | pokeruby |
| Pokemon Sapphire | AXPE | pokesapphire |
| Pokemon FireRed | BPRE | pokefirered |
| Pokemon LeafGreen | BPGE | pokeleafgreen |
