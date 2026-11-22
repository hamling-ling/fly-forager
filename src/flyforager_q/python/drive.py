"""Send wheel pulses to the sketch: setMotorSpeed(right, left).

Pulses are -255..255, positive forward. The sketch holds the last
command until the next one arrives and stops the wheels after 3 s
without one (watchdog). fly-car's hinge calibration is not applied
here in v1; the behaviour layer uses pulses well above the servos'
start threshold. A Bridge failure is reported once per distinct
message, like proboscis.
"""

from __future__ import annotations

import time

from arduino.app_utils import Bridge

_error: str | None = None


def send(right: int, left: int) -> bool:
    global _error
    right = max(-255, min(255, int(right)))
    left = max(-255, min(255, int(left)))
    try:
        Bridge.call("setMotorSpeed", right, left)
    except Exception as exc:
        text = f"setMotorSpeed failed: {exc}"
        if text != _error:
            print(text)
            _error = text
        return False
    if _error is not None:
        _error = None
    return True


def wait_until_bridge(attempts: int = 50, pause_s: float = 0.1) -> bool:
    """Stop the wheels, retrying while the sketch's Bridge comes up."""
    for _ in range(attempts):
        if send(0, 0):
            return True
        time.sleep(pause_s)
    return False
