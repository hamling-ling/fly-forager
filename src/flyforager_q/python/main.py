"""Foraging robot: see food, run the feeding circuit, show the decision.

One decision cycle: read the state (state.txt next to app.yaml, or the
config default), turn the newest camera frame into a nominal input
rate, run the C++ kernel for TRIALS of 1 s of brain time in that state,
and eat when the mean MN9 rate reaches the 10 Hz proboscis threshold.
The decision is shown on the LED matrix through the sketch, and the
behaviour layer (behavior.py) turns it into wheel pulses: search when
nothing is seen, approach steering by the frame's left/right coverage,
stop to eat at the food, arc away on refusal. Bench mode never moves.

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

import drive
import kernel
import proboscis
from behavior import decide_motion
from config import (
    DECISION_S,
    EAT_THRESHOLD_HZ,
    KERNEL_SEED,
    MANUAL_RATE,
    SEARCH_BURST_S,
    STATES,
    TRIALS,
    Satiety,
    params_at,
    read_state,
)
from food import fill_to_rate, food_fill_lr

# Satiety level for the LED gauge in the fixed states: the anchors
# the auto-mode interpolation passes through.
STATE_LEVELS = {"hungry": 0.0, "base": 0.5, "satiated": 1.0}


def loop() -> None:
    if not proboscis.wait_until_bridge():
        raise SystemExit("マイコンに届かない")
    if not drive.wait_until_bridge():
        raise SystemExit("モーターに届かない")
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
            fill = fill_l = fill_r = 0.0
            if eye is not None:
                frame, _seen = eye.shot()
                if frame is None:
                    time.sleep(0.2)
                    continue
                fill, fill_l, fill_r = food_fill_lr(frame)
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
            level = (
                satiety.level if state == "auto" else STATE_LEVELS[state]
            )
            proboscis.show(mean, eat, level)
            move = ""
            if eye is not None:
                mode, right, left = decide_motion(fill, fill_l, fill_r, eat)
                drive.send(right, left)
                move = f"  move {mode} R{right} L{left}"
                if mode == "search":
                    # Burst, then stop and look: holding the turn for
                    # the whole cycle spins the camera past everything.
                    time.sleep(SEARCH_BURST_S)
                    drive.send(0, 0)
            print(
                f"state {label}  k_p {k_p:.2f}  g_gaba {g_gaba:.2f}  "
                f"{seen}nominal {nominal:.0f} Hz  "
                f"MN9 {mean:.1f} Hz {counts}  "
                f"{'EAT' if eat else 'refuse'}{move}"
            )
            rest = DECISION_S - (time.monotonic() - began)
            if rest > 0:
                time.sleep(rest)
    finally:
        drive.send(0, 0)
        proboscis.show(0.0, False)
        if eye is not None:
            eye.close()


App.run(user_loop=loop)
