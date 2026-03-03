"""Atomic automation primitives: press buttons, wait, soft-reset, run away.

All actions operate on a LibmgbaEmulator and advance frame-by-frame.
A threading.Event (stop_event) is checked between frames so the hunt
coordinator can halt a worker cleanly.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from pokefinder.emulator import buttons

if TYPE_CHECKING:
    from pokefinder.emulator.core import LibmgbaEmulator


class StopRequested(Exception):
    """Raised when the stop_event is set during an action."""


def _check_stop(stop_event: threading.Event | None) -> None:
    if stop_event is not None and stop_event.is_set():
        raise StopRequested()


# ---------------------------------------------------------------------------
# Button presses
# ---------------------------------------------------------------------------

def press_button(
    emulator: "LibmgbaEmulator",
    key: int,
    hold_frames: int = 1,
    release_frames: int = 1,
    stop_event: threading.Event | None = None,
) -> None:
    """Press *key* for *hold_frames* frames, then release for *release_frames* frames."""
    emulator.set_inputs(key)
    for _ in range(hold_frames):
        _check_stop(stop_event)
        emulator.run_frame()

    emulator.clear_inputs()
    for _ in range(release_frames):
        _check_stop(stop_event)
        emulator.run_frame()


def press_a(emulator: "LibmgbaEmulator", **kwargs) -> None:
    press_button(emulator, buttons.A, **kwargs)


def press_b(emulator: "LibmgbaEmulator", **kwargs) -> None:
    press_button(emulator, buttons.B, **kwargs)


def press_start(emulator: "LibmgbaEmulator", **kwargs) -> None:
    press_button(emulator, buttons.START, **kwargs)


def press_select(emulator: "LibmgbaEmulator", **kwargs) -> None:
    press_button(emulator, buttons.SELECT, **kwargs)


def dpad(
    emulator: "LibmgbaEmulator",
    direction: int,
    hold_frames: int = 16,
    stop_event: threading.Event | None = None,
) -> None:
    """Hold a D-pad direction for *hold_frames* frames."""
    press_button(emulator, direction, hold_frames=hold_frames, release_frames=2, stop_event=stop_event)


# ---------------------------------------------------------------------------
# Waiting
# ---------------------------------------------------------------------------

def wait_frames(
    emulator: "LibmgbaEmulator",
    count: int,
    stop_event: threading.Event | None = None,
) -> None:
    """Advance *count* frames with no inputs."""
    emulator.clear_inputs()
    for _ in range(count):
        _check_stop(stop_event)
        emulator.run_frame()


def wait_until(
    emulator: "LibmgbaEmulator",
    condition_fn,
    max_frames: int = 600,
    poll_interval: int = 4,
    stop_event: threading.Event | None = None,
) -> bool:
    """Advance frames until *condition_fn()* returns True or *max_frames* elapsed.

    Returns True if the condition was met, False if we timed out.
    """
    emulator.clear_inputs()
    for i in range(max_frames):
        _check_stop(stop_event)
        emulator.run_frame()
        if i % poll_interval == 0 and condition_fn():
            return True
    return condition_fn()  # final check


# ---------------------------------------------------------------------------
# Soft reset
# ---------------------------------------------------------------------------

def soft_reset(
    emulator: "LibmgbaEmulator",
    stop_event: threading.Event | None = None,
) -> None:
    """Perform a GBA soft reset (A+B+Select+Start simultaneously for 2 frames)."""
    emulator.set_inputs(buttons.START_SELECT_A_B)
    for _ in range(2):
        _check_stop(stop_event)
        emulator.run_frame()
    emulator.clear_inputs()
    # Wait for the reset animation to finish (~90 frames)
    wait_frames(emulator, 90, stop_event=stop_event)


def load_state_reset(
    emulator: "LibmgbaEmulator",
    state_path,
    stop_event: threading.Event | None = None,
) -> None:
    """Load a save state as a faster alternative to soft reset.

    This is the preferred method for soft-reset hunting: save state at the
    last controllable moment before the encounter is generated, then reload.
    """
    _check_stop(stop_event)
    emulator.load_state(state_path)
    # Give the emulator a few frames to stabilize
    wait_frames(emulator, 4, stop_event=stop_event)


# ---------------------------------------------------------------------------
# Battle escape
# ---------------------------------------------------------------------------

def run_away(
    emulator: "LibmgbaEmulator",
    stop_event: threading.Event | None = None,
) -> None:
    """Navigate the battle menu to select Run and escape the encounter.

    Menu layout (Fight / Bag / Pokemon / Run):
    - Run is the bottom-right option. From default cursor position:
      press Down + Right to reach Run, then A to confirm.

    This uses a fixed-frame approach: wait long enough for the menu to
    appear, then navigate it deterministically.
    """
    # Wait for battle menu to fully appear (fighting menu visible)
    wait_frames(emulator, 20, stop_event=stop_event)

    # Navigate to RUN (bottom right of 2×2 menu grid):
    # Default position is top-left (Fight). Press Down then Right.
    press_button(emulator, buttons.DOWN, hold_frames=2, release_frames=4, stop_event=stop_event)
    press_button(emulator, buttons.RIGHT, hold_frames=2, release_frames=4, stop_event=stop_event)

    # Press A to select RUN
    press_button(emulator, buttons.A, hold_frames=2, release_frames=8, stop_event=stop_event)

    # Wait for the run escape animation and return to overworld
    wait_frames(emulator, 60, stop_event=stop_event)


def spam_b(
    emulator: "LibmgbaEmulator",
    count: int = 10,
    stop_event: threading.Event | None = None,
) -> None:
    """Press B repeatedly to skip dialogue."""
    for _ in range(count):
        press_button(emulator, buttons.B, hold_frames=2, release_frames=6, stop_event=stop_event)
