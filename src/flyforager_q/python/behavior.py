"""Turn a decision into wheel pulses. Pure, so it is testable.

This is the presentation layer between the circuit and the wheels --
a designed policy, not a measured one (the circuit itself only says
eat or refuse, through MN9):

  search    food unseen: turn in place, scanning
  approach  food seen but not near: drive at it, steering by the
            left/right coverage imbalance of the frame
  eat       at the food and the circuit ate: stop and feed
  reject    at the food and the circuit refused: arc backwards away

Pulses are (right, left), -255..255, held by the sketch until the
next decision.
"""

from __future__ import annotations

from config import (
    BACK_LEFT,
    BACK_RIGHT,
    CRUISE_PULSE,
    FOOD_VISIBLE,
    NEAR_FILL,
    SEARCH_PULSE,
    STEER_GAIN,
)


def _clamp(pulse: float) -> int:
    return int(round(max(-255.0, min(255.0, pulse))))


def decide_motion(
    fill: float, fill_left: float, fill_right: float, eat: bool
) -> tuple[str, int, int]:
    """(mode, right pulse, left pulse) for one decision cycle."""
    if fill < FOOD_VISIBLE:
        return "search", SEARCH_PULSE, -SEARCH_PULSE
    if fill >= NEAR_FILL:
        if eat:
            return "eat", 0, 0
        return "reject", BACK_RIGHT, BACK_LEFT
    total = fill_left + fill_right
    err = (fill_right - fill_left) / total if total > 0 else 0.0
    right = _clamp(CRUISE_PULSE - STEER_GAIN * err)
    left = _clamp(CRUISE_PULSE + STEER_GAIN * err)
    return "approach", right, left
