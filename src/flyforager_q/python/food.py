"""See the food and turn it into a nominal input rate.

V1 proxy mapping (a demo device, not a measured one): the food colour's
coverage of the frame's centre stands in for concentration. Coverage
FILL_FULL maps to NOMINAL_MAX; no coverage maps to 0. The brain side of
the mapping -- nominal rate to MN9 -- is the measured part.
"""

from __future__ import annotations

from config import FOOD_HSV, FILL_FULL, NOMINAL_MAX, ROI_FRACTION


def fill_to_rate(fill: float) -> float:
    """Nominal rate for a coverage fraction. Pure, so it is testable."""
    if fill <= 0.0:
        return 0.0
    return min(NOMINAL_MAX, NOMINAL_MAX * fill / FILL_FULL)


# The feeding circuit reads the same eyes as the drive model: the
# mean eye-range coverage, with EYE_FULL (the safety-stop fill)
# mapping to NOMINAL_MAX. A sheet in front (~0.10 per eye in fly-car's
# calibration) gives ~20 Hz; half-covered eyes give ~100 Hz.
EYE_FULL = 0.75


def eye_to_rate(mean_eye: float) -> float:
    """Nominal rate for the mean eye-range coverage. Pure/testable."""
    if mean_eye <= 0.0:
        return 0.0
    return min(NOMINAL_MAX, NOMINAL_MAX * mean_eye / EYE_FULL)


def _food_mask(frame, roi_fraction: float = ROI_FRACTION):
    """Binary mask of the food colour in the frame's centre ROI."""
    import cv2
    import numpy as np

    height, width = frame.shape[:2]
    rh, rw = int(height * roi_fraction), int(width * roi_fraction)
    y0, x0 = (height - rh) // 2, (width - rw) // 2
    roi = frame[y0:y0 + rh, x0:x0 + rw]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for h_lo, h_hi, s_lo, s_hi, v_lo, v_hi in FOOD_HSV:
        band = cv2.inRange(
            hsv,
            np.array([h_lo, s_lo, v_lo]),
            np.array([h_hi, s_hi, v_hi]),
        )
        mask = cv2.bitwise_or(mask, band)
    return mask


def food_fill(frame) -> float:
    """Coverage of the food colour in the frame's centre ROI, 0..1."""
    import numpy as np

    mask = _food_mask(frame)
    return float(np.count_nonzero(mask)) / float(mask.size)


def food_fill_lr(
    frame, roi_fraction: float = ROI_FRACTION
) -> tuple[float, float, float]:
    """(total, left, right) coverage: total over the ROI, and the
    coverage within each half of it, for steering toward the food.
    roi_fraction=1.0 looks at the whole frame (the periphery)."""
    import numpy as np

    mask = _food_mask(frame, roi_fraction)
    half = mask.shape[1] // 2
    left = mask[:, :half]
    right = mask[:, half:]
    return (
        float(np.count_nonzero(mask)) / float(mask.size),
        float(np.count_nonzero(left)) / float(left.size),
        float(np.count_nonzero(right)) / float(right.size),
    )


# fly-car's eye ranges over the full frame: the left eye reads the
# image position p in [0, 0.65], the right eye p in [0.35, 1].
EYE_LEFT_HI = 0.65
EYE_RIGHT_LO = 0.35


def red_eyes(frame) -> tuple[float, float, float]:
    """(red_l, red_r, place) for fly-car's drive model.

    red_l / red_r are the food colour's coverage of each eye range
    over the full frame; place is the red centroid, -1 at the left
    edge and +1 at the right (0 when no red). Same definitions as
    flycar.occupancy's range_means / red_place, on this app's red
    thresholds and without its small-region filtering.
    """
    import numpy as np

    mask = _food_mask(frame, 1.0)
    width = mask.shape[1]
    p = (np.arange(width) + 0.5) / float(width)
    left = mask[:, p <= EYE_LEFT_HI]
    right = mask[:, p >= EYE_RIGHT_LO]
    red_l = float(np.count_nonzero(left)) / float(left.size)
    red_r = float(np.count_nonzero(right)) / float(right.size)
    columns = mask.sum(axis=0, dtype=np.float64)
    total = float(columns.sum())
    if total <= 0.0:
        return red_l, red_r, 0.0
    centroid = float(np.dot(columns, p) / total)
    place = max(-1.0, min(1.0, (centroid - 0.5) / 0.5))
    return red_l, red_r, place
