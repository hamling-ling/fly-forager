"""Wheel speed in m/s to the servo pulse. Ported from flycar.pulse.

0.20 m/s maps to pulse 160; nothing here has been timed against the
real wheels (the m/s scale is nominal, as in fly-car). motion_pulse
applies the chassis dead band measured on the table: forward below
13 drops to 0, reverse is shifted by -36 so a slow reverse clears
the band. fly-car's left-only hinge straighten is not applied.
"""

from __future__ import annotations

CRUISE_MPS = 0.20
CRUISE_PULSE = 160
PULSE_LIMIT = 255

FORWARD_START = 13
REVERSE_START = 36


def wheel_pulse(meters_per_second: float) -> int:
    scaled = float(meters_per_second) / CRUISE_MPS * CRUISE_PULSE
    rounded = int(round(scaled))
    if rounded > PULSE_LIMIT:
        return PULSE_LIMIT
    if rounded < -PULSE_LIMIT:
        return -PULSE_LIMIT
    return rounded


def motion_pulse(pulse: int) -> int:
    """The pulse the chassis can follow, judged per wheel."""
    command = int(pulse)
    if command < 0:
        shifted = command - REVERSE_START
        if shifted < -PULSE_LIMIT:
            return -PULSE_LIMIT
        return shifted
    if command >= FORWARD_START:
        return command
    return 0


def wheel_pulses(v_left: float, v_right: float) -> tuple[int, int]:
    """(right, left) sendable pulses for wheel speeds in m/s."""
    return (
        motion_pulse(wheel_pulse(v_right)),
        motion_pulse(wheel_pulse(v_left)),
    )
