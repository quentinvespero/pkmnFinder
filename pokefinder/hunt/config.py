"""HuntConfig: configuration for a single hunt session."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path


class HuntMethod(enum.Enum):
    WILD = "wild"          # Walk in grass, flee from non-targets
    SOFT_RESET = "soft_reset"  # Reload save state for starters/legendaries


@dataclass
class HuntConfig:
    """All parameters needed to start a hunt.

    Attributes
    ----------
    rom_path:
        Path to the .gba ROM file.
    target_species_id:
        National Dex ID of the species to hunt (1–386).
    target_species_name:
        Display name (filled in by the GUI from species lookup).
    shiny_only:
        If True, only stop when a *shiny* specimen is found.
    method:
        WILD for grass encounters, SOFT_RESET for starters/legendaries.
    num_instances:
        Number of parallel emulator instances to run.
    state_path:
        Save state for SOFT_RESET method. Must be pre-positioned.
        Unused for WILD method.
    save_dir:
        Directory to write winning save states to.
    """

    rom_path: Path
    target_species_id: int
    target_species_name: str = ""
    shiny_only: bool = True
    method: HuntMethod = HuntMethod.WILD
    num_instances: int = 4
    state_path: Path | None = None
    save_dir: Path = field(default_factory=lambda: Path("saves"))

    def __post_init__(self) -> None:
        self.rom_path = Path(self.rom_path)
        if self.state_path is not None:
            self.state_path = Path(self.state_path)
        self.save_dir = Path(self.save_dir)

    def validate(self) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        errors: list[str] = []
        if not self.rom_path.exists():
            errors.append(f"ROM not found: {self.rom_path}")
        if self.target_species_id < 1 or self.target_species_id > 386:
            errors.append(f"Invalid species ID: {self.target_species_id} (must be 1–386)")
        if self.num_instances < 1:
            errors.append("Number of instances must be ≥ 1")
        if self.method == HuntMethod.SOFT_RESET:
            if self.state_path is None:
                errors.append("Soft reset hunt requires a save state path.")
            elif not self.state_path.exists():
                errors.append(f"Save state not found: {self.state_path}")
        return errors
