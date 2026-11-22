"""Knobs for the foraging robot.

States are the Experiment D parameter sets, measured on the full brain
and reproduced by the extracted subcircuit. A state is only a pair
(k_p, g_gaba): peripheral input gain and GABAergic brake tone. The
presets are the measured endpoints; nothing here interpolates between
them yet.
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
STATE_FILE = Path(__file__).resolve().parents[1] / "state.txt"


def read_state(path: Path = STATE_FILE) -> str:
    """State name from the state file, or DEFAULT_STATE."""
    try:
        name = path.read_text().strip().lower()
    except OSError:
        return DEFAULT_STATE
    return name if name in STATES else DEFAULT_STATE
