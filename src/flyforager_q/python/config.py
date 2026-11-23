"""Knobs for the foraging robot.

A state is only a pair (k_p, g_gaba): peripheral input gain and
GABAergic brake tone. "hungry" and "base" are the Experiment D
parameter sets, measured on the full brain and reproduced by the
extracted subcircuit. "satiated" sits on the same base->S3 line,
extended past S3 (which lies at level ~0.83 on this axis) so the
full state refuses across the camera's real input range; its
dose-response was measured in silico on 2026-11-23 (kernel + Brian2).
"auto" mode interpolates between the presets (the intermediate
points were measured in silico on 2026-11-22).
"""

from __future__ import annotations

from pathlib import Path

# (k_p, g_gaba) per state. H3 = hunger (Experiment D); satiated is
# the base->S3 ray extended to t=1.5 (see the module docstring).
STATES = {
    "base": (1.0, 1.0),
    "hungry": (1.5, 0.7),
    "satiated": (0.505, 1.45),
}
DEFAULT_STATE = "base"

# The gate opens when the current MN9 estimate reaches this.
# The 10 Hz proboscis threshold is Experiment D's pre-registered readout.
EAT_THRESHOLD_HZ = 10.0

# The gate on the approach term is a smooth sigmoid of the MN9
# estimate, centred on the threshold -- the same switch shape as
# fly-car's loom gain in the poster. SIGMA_WIDTH_HZ is its width in
# Hz: sigma is 0.5 at the threshold and nearly 1 a few widths above.
SIGMA_WIDTH_HZ = 2.0


def sigma_of(mn9_hz: float) -> float:
    """Feeding gate, 0..1, from the current MN9 estimate."""
    from math import exp

    z = (mn9_hz - EAT_THRESHOLD_HZ) / SIGMA_WIDTH_HZ
    return 1.0 / (1.0 + exp(-z))

# There is no decision cycle: the kernel thread runs 1 s trials back
# to back (one trial is ~0.2 s of wall time on the Uno Q) and the
# main loop reads the newest MN9 estimate. The loop's slice -- how
# often the plant advances and the wheels are re-commanded -- is
# LOOP_S; the LED and the log read the state out every LOG_S.
LOOP_S = 0.10
LOG_S = 1.0
# Occupancy + loom resampling cadence, same as flycar_q's COUNT_S:
# the blue measurement needs frame history at this rate.
COUNT_S = 0.10

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
# runs 0 (hungry) to 1 (satiated). Eating fills it at a rate of one
# old decision's worth (1/EATS_TO_FULL) per EAT_STEP_S seconds of
# eating -- EATS_TO_FULL was tuned in the decision era, when one eat
# was one 2 s decision -- and the level drains back to 0 over
# HUNGER_RETURN_S seconds.
EATS_TO_FULL = 6
EAT_STEP_S = 2.0
HUNGER_RETURN_S = 30.0


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
    level 0 = hungry (H3), 0.5 = base, 1 = the extended satiety
    point; the satiety-side line passes through the measured S3 set
    at level ~0.83. Between the points is a straight line, a display
    device like the binary states were."""
    level = min(1.0, max(0.0, level))
    if level <= 0.5:
        a, b, t = STATES["hungry"], STATES["base"], level * 2.0
    else:
        a, b, t = STATES["base"], STATES["satiated"], (level - 0.5) * 2.0
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


class Satiety:
    """Feeding fills it, time drains it. Level 0..1.

    The level itself is the state: the circuit parameters, the LED
    gauge and the log all read it directly, with no latch on top.
    Satiety is the dose-response curve shifting with the level, not
    a refusal switch, so a full robot still eats concentrated food
    -- exactly what the measured satiated curve says it should.
    """

    def __init__(self) -> None:
        self.level = 0.0

    def feed(self, seconds: float) -> None:
        """Eating for `seconds` fills the level by that much time."""
        gain = seconds / (EATS_TO_FULL * EAT_STEP_S)
        self.level = min(1.0, self.level + gain)
        if self.level > 1.0 - 1e-9:  # float steps do not sum to 1 exactly
            self.level = 1.0

    def elapse(self, seconds: float) -> None:
        self.level = max(0.0, self.level - seconds / HUNGER_RETURN_S)


# Drive: fly-car's model lives in plant.py (equations and constants
# ported from flycar.behavior) and pulse.py (flycar.pulse). The one
# addition is the feeding gate sigma on the approach term, which
# follows the current MN9 estimate in main.py. Wheel commands are
# re-sent every LOOP_S; the sketch's 3 s watchdog stops the wheels
# if Python dies.
