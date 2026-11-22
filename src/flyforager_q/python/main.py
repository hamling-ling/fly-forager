"""Foraging robot: see food, run the feeding circuit, show the decision.

One decision cycle: read the state (state.txt next to app.yaml, or the
config default), turn the newest camera frame into a nominal input
rate, run the C++ kernel for TRIALS of 1 s of brain time in that state,
and eat when the mean MN9 rate reaches the 10 Hz proboscis threshold.
The decision is shown on the LED matrix through the sketch, and it
also drives the wheels through fly-car's drive model (plant.py):
the eat/refuse outcome becomes the gate sigma on the approach
(DNa02) term of fly-car's crossed readout, so the robot approaches
red only while the feeding circuit says eat. Bench mode never moves.

state.txt may also say "auto": a satiety level then integrates the
decisions -- eating fills it toward the satiated parameter set, time
drains it back toward hungry -- and the kernel runs at the
interpolated parameters.

With MANUAL_RATE set in config.py the camera is never opened and the
fixed rate is judged instead -- the bench mode for trying states.
"""

from __future__ import annotations

import sys
import threading
import time

from arduino.app_utils import App

import drive
import kernel
import proboscis
from config import (
    COUNT_S,
    DECISION_S,
    EAT_THRESHOLD_HZ,
    KERNEL_SEED,
    MANUAL_RATE,
    NOMINAL_MAX,
    STATES,
    TRIALS,
    Satiety,
    params_at,
    read_state,
)
from food import arrived, at_mouth, food_fill_lr, red_eyes
from occupancy import Counts
from plant import Plant, pn_outputs
from pulse import wheel_pulses

# Satiety level for the LED gauge in the fixed states: the anchors
# the auto-mode interpolation passes through.
STATE_LEVELS = {"hungry": 0.0, "base": 0.5, "satiated": 1.0}


def loop() -> None:
    # Stdout in the container is block-buffered: at one log line per
    # decision cycle the buffer takes minutes to flush, so the log
    # seems to stop and then bursts. Line-buffer it.
    sys.stdout.reconfigure(line_buffering=True)
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
    plant = Plant()
    # fly-car's occupancy + loom, updated at COUNT_S like flycar_q.
    # flycar_q updates in its main loop; here a thread does it,
    # because the decision loop is busy for seconds at a time. The
    # decision loop only reads the latest values.
    occ = Counts()
    counts_stop = threading.Event()
    if eye is not None:
        def _count_loop() -> None:
            while not counts_stop.wait(COUNT_S):
                frame = eye.latest()
                if frame is not None:
                    occ.update(frame, now=time.monotonic())

        threading.Thread(
            target=_count_loop, name="counts", daemon=True
        ).start()
    last_cycle = time.monotonic()
    try:
        while True:
            began = time.monotonic()
            state = read_state()
            if state == "auto":
                satiety.elapse(began - last_cycle)
                k_p, g_gaba = params_at(satiety.effective_level)
                label = f"auto({satiety.effective_level:.2f})"
                if satiety.full:
                    label += " full"
            else:
                k_p, g_gaba = STATES[state]
                label = state
            last_cycle = began
            fill = 0.0
            red_l = red_r = place = 0.0
            blue_l = blue_r = 0.0
            loom = (0.0, 0.0)
            if eye is not None:
                frame, _seen = eye.shot()
                if frame is None:
                    drive.send(0, 0)
                    time.sleep(0.2)
                    continue
                fill, _fl, _fr = food_fill_lr(frame)
                red_l, red_r, place = red_eyes(frame)
                blue_l, blue_r = occ.values[2], occ.values[3]
                loom = occ.loom
                # The kernel reads the PN stage of the same eyes:
                # nominal = NOMINAL_MAX x mean PN output.
                u_l, u_r = pn_outputs(red_l, red_r, place)
                nominal = NOMINAL_MAX * 0.5 * (u_l + u_r)
                seen = (
                    f"fill {fill:.3f}  eye {red_l:.2f}/{red_r:.2f}  "
                    f"place {place:+.2f}  "
                    f"blue {blue_l:.2f}/{blue_r:.2f}  "
                    f"loom {loom[0]:.2f}/{loom[1]:.2f}  "
                    f"td {occ.theta_dot:.2f}  "
                )
            else:
                nominal = float(MANUAL_RATE)
                seen = ""
            mean, counts = kernel.decide(
                nominal, k_p, g_gaba, TRIALS, seed=KERNEL_SEED
            )
            eat = mean >= EAT_THRESHOLD_HZ
            # Feeding counts only with the food at the mouth (centre
            # coverage at FILL_FULL); a distant EAT opens the gate
            # but does not fill the robot before it arrives.
            if eat and state == "auto" and at_mouth(fill):
                satiety.eat()
            level = (
                satiety.effective_level if state == "auto" else STATE_LEVELS[state]
            )
            proboscis.show(mean, eat, level)
            move = ""
            if eye is not None:
                # The feeding gate on fly-car's approach term: sigma
                # follows the latest decision, the membranes advance
                # by the wall time since the previous cycle.
                plant.sigma = 1.0 if eat else 0.0
                step = plant.steps(
                    red_l, red_r, blue_l, blue_r, loom=loom, place=place
                )
                right, left = wheel_pulses(step.v_left, step.v_right)
                mode = step.mode
                if arrived(fill) and mode != "back":
                    # At the food: stop approaching, eat in place.
                    right, left, mode = 0, 0, "arrive"
                drive.send(right, left)
                move = (
                    f"  move {mode} R{right} L{left}"
                    f"  dna {plant.dna_l.rate:.0f}/{plant.dna_r.rate:.0f}"
                    f"  sigma {plant.sigma:.0f}"
                )
            print(
                f"state {label}  k_p {k_p:.2f}  g_gaba {g_gaba:.2f}  "
                f"{seen}nominal {nominal:.0f} Hz  "
                f"MN9 {mean:.1f} Hz {counts}  "
                f"{'EAT' if eat else 'refuse'}{move}",
                flush=True,
            )
            rest = DECISION_S - (time.monotonic() - began)
            if rest > 0:
                time.sleep(rest)
    finally:
        counts_stop.set()
        drive.send(0, 0)
        proboscis.show(0.0, False)
        if eye is not None:
            eye.close()


App.run(user_loop=loop)
