"""Show the decision on the Uno Q's LED matrix via the sketch.

showProboscis(mn9, eat, satiety): the matrix draws a bar whose length
follows the MN9 rate (eat thickens it, lamp green; refusal red), and
a gauge along the bottom rows for the satiety level 0..1, which stays
visible between decisions. A Bridge failure is reported once per
distinct message, like flycar_q.
"""

from __future__ import annotations

import time

from arduino.app_utils import Bridge

_error: str | None = None


def show(mn9_hz: float, eat: bool, level: float = 0.0) -> bool:
    global _error
    pct = int(round(min(1.0, max(0.0, level)) * 100))
    try:
        Bridge.call(
            "showProboscis", int(round(mn9_hz)), 1 if eat else 0, pct
        )
    except Exception as exc:
        text = f"showProboscis failed: {exc}"
        if text != _error:
            print(text)
            _error = text
        return False
    if _error is not None:
        _error = None
    return True


def wait_until_bridge(attempts: int = 50, pause_s: float = 0.1) -> bool:
    """Blank the display, retrying while the sketch's Bridge comes up."""
    for _ in range(attempts):
        if show(0.0, False):
            return True
        time.sleep(pause_s)
    return False
