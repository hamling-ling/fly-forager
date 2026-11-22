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


def _food_mask(frame):
    """Binary mask of the food colour in the frame's centre ROI."""
    import cv2
    import numpy as np

    height, width = frame.shape[:2]
    rh, rw = int(height * ROI_FRACTION), int(width * ROI_FRACTION)
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


def food_fill_lr(frame) -> tuple[float, float, float]:
    """(total, left, right) coverage: total over the ROI, and the
    coverage within each half of it, for steering toward the food."""
    import numpy as np

    mask = _food_mask(frame)
    half = mask.shape[1] // 2
    left = mask[:, :half]
    right = mask[:, half:]
    return (
        float(np.count_nonzero(mask)) / float(mask.size),
        float(np.count_nonzero(left)) / float(left.size),
        float(np.count_nonzero(right)) / float(right.size),
    )
