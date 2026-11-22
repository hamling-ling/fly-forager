"""Knobs for the foraging robot.

States are the Experiment D parameter sets, measured on the full brain
and reproduced by the extracted subcircuit. A state is only a pair
(k_p, g_gaba): peripheral input gain and GABAergic brake tone. The
presets are the measured points; "auto" mode interpolates between
them (the intermediate points were measured in silico on 2026-11-22).
"""

from __future__ import annotations

from pathlib import Path

# (k_p, g_gaba) per state. H3 = hunger, S3 = satiety (Experiment D).
STATES = {
    "base": (1.0, 1.0),
    "hungry": (1.5, 0.7),
    "satiated": (0.67, 1.3),
}
DEFAULT_STATE = "base"

# Eat when the mean MN9 rate over the decision trials reaches this.
# The 10 Hz proboscis threshold is Experiment D's pre-registered readout.
EAT_THRESHOLD_HZ = 10.0

# Kernel trials per decision. One trial is 1 s of brain time and takes
# about 0.2 s of wall time on the Uno Q, so 3 trials cost ~0.6 s.
TRIALS = 3

# Pause between decisions, seconds.
DECISION_S = 2.0

# Fixed seed base for the kernel, so the same food in the same state
# gives the same decision every time (demo reproducibility).
KERNEL_SEED = 1000

# Bench mode: a float fixes the nominal input rate and the camera is
# not opened. None means the camera decides.
MANUAL_RATE: float | None = None

# Food sensing (v1 proxy, not a measured mapping): the nominal input
# rate is NOMINAL_MAX at FILL_FULL coverage of the frame's centre.
NOMINAL_MAX = 150.0
FILL_FULL = 0.25
# Arrival at the food, feeding layer's scale: centre coverage this
# high means the sheet is at the mouth, so approach stops (it eats
# in place). fly-car's safety stop (both eyes at 0.75) stays as the
# outer guard; with the 90-degree camera a hand-held sheet rarely
# covers the frame corners enough to reach it (eyes sit near 0.5).
ARRIVE_FILL = 0.60
ROI_FRACTION = 0.6

# Food colour in OpenCV HSV (H 0-179). Default is red, in two bands
# because red wraps around hue 0. Saturation/value floors keep dim
# background out.
FOOD_HSV = (
    (0, 10, 90, 255, 60, 255),
    (170, 179, 90, 255, 60, 255),
)

# Frames to drop before the first decision. Exposure is still climbing.
WARMUP_FRAMES = 20

# The live state is read from this file next to app.yaml on every
# decision, so a demo can flip it with:  echo hungry > state.txt
# The file may also say "auto": the robot then feeds itself full (see
# the satiety dynamics below) and gets hungry again over time.
STATE_FILE = Path(__file__).resolve().parents[1] / "state.txt"

# Satiety dynamics for "auto" mode. These are presentation-layer
# design numbers, NOT measured fly physiology: the measured parts are
# the endpoint parameter sets and the dose-response curves. The level
# runs 0 (hungry) to 1 (satiated); each EAT adds 1/EATS_TO_FULL, and
# the level drains back to 0 over HUNGER_RETURN_S seconds.
EATS_TO_FULL = 5
HUNGER_RETURN_S = 600.0

# Demo timing overrides live OUTSIDE git, in tuning.txt next to
# state.txt (the app root). Deploys copy this tree over the board's
# app dir but never delete files that are not in the tree, and the
# file is gitignored, so tuned values survive pulls and deploys --
# editing the constants above used to clobber them on every pull.
TUNING_FILE = Path(__file__).resolve().parents[1] / "tuning.txt"


def parse_tuning(text: str) -> dict:
    """'KEY = value' lines -> overrides for the two timings. Pure."""
    out: dict = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        try:
            if key == "EATS_TO_FULL":
                out[key] = int(value)
            elif key == "HUNGER_RETURN_S":
                out[key] = float(value)
        except ValueError:
            continue
    return out


def _apply_tuning() -> None:
    global EATS_TO_FULL, HUNGER_RETURN_S
    try:
        text = TUNING_FILE.read_text()
    except OSError:
        return
    applied = parse_tuning(text)
    if "EATS_TO_FULL" in applied:
        EATS_TO_FULL = applied["EATS_TO_FULL"]
    if "HUNGER_RETURN_S" in applied:
        HUNGER_RETURN_S = applied["HUNGER_RETURN_S"]
    if applied:
        print(f"config: tuning.txt overrides {applied}")


_apply_tuning()


def read_state(path: Path = STATE_FILE) -> str:
    """State name (or "auto") from the state file, or DEFAULT_STATE."""
    try:
        name = path.read_text().strip().lower()
    except OSError:
        return DEFAULT_STATE
    if name == "auto":
        return name
    return name if name in STATES else DEFAULT_STATE


def params_at(level: float) -> tuple[float, float]:
    """(k_p, g_gaba) at a satiety level, interpolated through the
    measured sets: level 0 = hungry (H3), 0.5 = base, 1 = satiated
    (S3). Only those three points are measured; between them is a
    straight line, a display device like the binary states were."""
    level = min(1.0, max(0.0, level))
    if level <= 0.5:
        a, b, t = STATES["hungry"], STATES["base"], level * 2.0
    else:
        a, b, t = STATES["base"], STATES["satiated"], (level - 0.5) * 2.0
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# Satiety is hysteretic: once full, the robot stays full -- satiated
# parameters, full LED gauge, no interest -- until the underlying
# level drains to FULL_RELEASE. Without the latch the level only
# touches 1.00 for an instant and falls back to ~0.97, so "full"
# never lasts long enough to read as a state.
FULL_RELEASE = 0.6


class Satiety:
    """Feeding fills it, time drains it. Level 0..1, latched full."""

    def __init__(self) -> None:
        self.level = 0.0
        self.full = False

    def eat(self) -> None:
        self.level = min(1.0, self.level + 1.0 / EATS_TO_FULL)
        if self.level >= 1.0:
            self.full = True

    def elapse(self, seconds: float) -> None:
        self.level = max(0.0, self.level - seconds / HUNGER_RETURN_S)
        if self.full and self.level <= FULL_RELEASE:
            self.full = False

    @property
    def effective_level(self) -> float:
        """The level the circuit and the LED see: pinned at 1 while full."""
        return 1.0 if self.full else self.level


# Drive: fly-car's model lives in plant.py (equations and constants
# ported from flycar.behavior) and pulse.py (flycar.pulse). The one
# addition is the feeding gate sigma on the approach term, set from
# each decision in main.py. Wheel commands are held by the MCU until
# the next decision (2 s); the sketch's 3 s watchdog stops the wheels
# if Python dies.
