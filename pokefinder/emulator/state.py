"""Save state helpers: load/save emulator state snapshots."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pokefinder.emulator.core import LibmgbaEmulator

SAVES_DIR = Path(__file__).parent.parent.parent / "saves"


def snapshot_path(species_name: str, instance_id: int) -> Path:
    """Return a timestamped path for a winning save state."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = species_name.replace(" ", "_").lower()
    return SAVES_DIR / f"{ts}_{safe_name}_inst{instance_id}.ss1"


def save_snapshot(emulator: LibmgbaEmulator, species_name: str, instance_id: int) -> Path:
    """Save a snapshot of *emulator* and return the path written."""
    path = snapshot_path(species_name, instance_id)
    emulator.save_state(path)
    return path


def load_snapshot(emulator: LibmgbaEmulator, path: Path | str) -> None:
    """Load a previously saved snapshot into *emulator*."""
    emulator.load_state(Path(path))
