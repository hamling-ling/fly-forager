"""Foraging robot: see food, run the feeding circuit, show the decision.

One decision cycle: read the state (state.txt next to app.yaml, or the
config default), turn the newest camera frame into a nominal input
rate, run the C++ kernel for TRIALS of 1 s of brain time in that state,
and eat when the mean MN9 rate reaches the 10 Hz proboscis threshold.
The decision is shown on the LED matrix through the sketch.

state.txt may also say "auto": a satiety level then integrates the
decisions -- eating fills it toward the satiated parameter set, time
drains it back toward hungry -- and the kernel runs at the
interpolated parameters.

With MANUAL_RATE set in config.py the camera is never opened and the
fixed rate is judged instead -- the bench mode for trying states.
"""

from __future__ import annotations

import time

from arduino.app_utils import App

import kernel
import proboscis
from config import (
    DECISION_S,
    EAT_THRESHOLD_HZ,
    KERNEL_SEED,
    MANUAL_RATE,
    STATES,
    TRIALS,
    Satiety,
    params_at,
    read_state,
)
from food import fill_to_rate, food_fill


def loop() -> None:
    if not proboscis.wait_until_bridge():
        raise SystemExit("マイコンに届かない")
    kernel.ensure_built()
    eye = None
    if MANUAL_RATE is None:
        from camera import Eye

        eye = Eye()
        eye.start()
        if not eye.wait_ready():
            print("camera: フレームが来てから判断を始める")
    else:
        print(f"bench mode: nominal rate fixed at {MANUAL_RATE:g} Hz")
    satiety = Satiety()
    last_cycle = time.monotonic()
    try:
        while True:
            began = time.monotonic()
            state = read_state()
            if state == "auto":
                satiety.elapse(began - last_cycle)
                k_p, g_gaba = params_at(satiety.level)
                label = f"auto({satiety.level:.2f})"
            else:
                k_p, g_gaba = STATES[state]
                label = state
            last_cycle = began
            if eye is not None:
                frame, _seen = eye.shot()
                if frame is None:
                    time.sleep(0.2)
                    continue
                fill = food_fill(frame)
                nominal = fill_to_rate(fill)
                seen = f"fill {fill:.3f}  "
            else:
                nominal = float(MANUAL_RATE)
                seen = ""
            mean, counts = kernel.decide(
                nominal, k_p, g_gaba, TRIALS, seed=KERNEL_SEED
            )
            eat = mean >= EAT_THRESHOLD_HZ
            if eat and state == "auto":
                satiety.eat()
            proboscis.show(mean, eat)
            print(
                f"state {label}  {seen}nominal {nominal:.0f} Hz  "
                f"MN9 {mean:.1f} Hz {counts}  "
                f"{'EAT' if eat else 'refuse'}"
            )
            rest = DECISION_S - (time.monotonic() - began)
            if rest > 0:
                time.sleep(rest)
    finally:
        proboscis.show(0.0, False)
        if eye is not None:
            eye.close()


App.run(user_loop=loop)
