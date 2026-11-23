"""Foraging robot: two circuits running in parallel, coupled by signals.

Like the fly, there is no decision cycle. The visual circuit
(plant.py, fly-car's model) runs continuously at the main loop's
cadence: every LOOP_S it takes the newest camera frame and the
latest loom and advances the membranes by the elapsed wall time.
The feeding circuit runs continuously too, in its own thread: the
C++ kernel runs 1 s trials back to back at the current input, and
the mean of the last two trials is the current MN9 rate estimate.
The circuits touch only through signals -- the kernel's input rate
is NOMINAL_MAX x the mean PN output of the same eyes that drive
DNa02, and the MN9 estimate becomes the gate sigma on the approach
(DNa02) term of fly-car's crossed readout, so the robot approaches
red only while the feeding circuit fires MN9 at the 10 Hz
proboscis threshold or more.

state.txt (next to app.yaml) names the state, or "auto": a satiety
level then integrates -- while MN9 is over threshold with food at
the mouth the level fills toward the satiated parameter set, and
it drains back toward hungry over HUNGER_RETURN_S -- and the
kernel runs at the interpolated parameters.

The LED and the log read the continuous state out once a second;
neither is a decision. Bench mode (MANUAL_RATE in config.py) never
opens the camera and never moves.
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
    EAT_THRESHOLD_HZ,
    KERNEL_SEED,
    LOG_S,
    LOOP_S,
    MANUAL_RATE,
    NOMINAL_MAX,
    STATES,
    Satiety,
    params_at,
    read_state,
    sigma_of,
)
from food import arrived, at_mouth, food_fill_lr, red_eyes
from occupancy import Counts
from plant import Plant, pn_outputs
from pulse import wheel_pulses

# Satiety level for the LED gauge in the fixed states: the anchors
# the auto-mode interpolation passes through.
STATE_LEVELS = {"hungry": 0.0, "base": 0.5, "satiated": 1.0}


class KernelFeed:
    """The feeding circuit as a continuously running process.

    A thread runs one 1 s kernel trial after another at the latest
    published (nominal, k_p, g_gaba). mn9() averages the last two
    trial counts: the freshest MN9 estimate, about 0.4 s old on the
    board (one trial is ~0.2 s of wall time there). The seed walks
    so consecutive trials differ, as trials of a real circuit would.
    """

    def __init__(self) -> None:
        self.nominal = 0.0
        self.k_p, self.g_gaba = STATES["base"]
        self.counts: list[int] = []
        self._seed = KERNEL_SEED
        self.stop = threading.Event()

    def publish(self, nominal: float, k_p: float, g_gaba: float) -> None:
        self.nominal = nominal
        self.k_p = k_p
        self.g_gaba = g_gaba

    def run(self) -> None:
        while not self.stop.is_set():
            _mean, counts = kernel.decide(
                self.nominal, self.k_p, self.g_gaba, 1, seed=self._seed
            )
            self._seed += 1
            self.counts = (self.counts + counts)[-2:]

    def mn9(self) -> float:
        if not self.counts:
            return 0.0
        return sum(self.counts) / len(self.counts)


def loop() -> None:
    # Stdout in the container is block-buffered: at one log line per
    # second the buffer still takes minutes to flush, so the log
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
    feed = KernelFeed()
    threading.Thread(target=feed.run, name="kernel", daemon=True).start()
    # fly-car's occupancy + loom, updated at COUNT_S like flycar_q.
    # flycar_q updates in its main loop; here a thread does it and
    # the main loop only reads the latest values.
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
    state = read_state()
    last_slice = time.monotonic()
    last_log = 0.0
    try:
        while True:
            began = time.monotonic()
            dt = began - last_slice
            last_slice = began
            # State flips are read at the log cadence; the satiety
            # parameters follow the level every slice.
            if began - last_log >= LOG_S:
                state = read_state()
            if state == "auto":
                k_p, g_gaba = params_at(satiety.level)
                label = f"auto({satiety.level:.2f})"
            else:
                k_p, g_gaba = STATES[state]
                label = state
            fill = 0.0
            red_l = red_r = place = 0.0
            blue_l = blue_r = 0.0
            loom = (0.0, 0.0)
            nominal = float(MANUAL_RATE) if MANUAL_RATE is not None else 0.0
            frame = eye.latest() if eye is not None else None
            if eye is not None and frame is None:
                drive.send(0, 0)
                time.sleep(LOOP_S)
                continue
            if frame is not None:
                fill, _fl, _fr = food_fill_lr(frame)
                red_l, red_r, place = red_eyes(frame)
                blue_l, blue_r = occ.values[2], occ.values[3]
                loom = occ.loom
                # The kernel reads the PN stage of the same eyes:
                # nominal = NOMINAL_MAX x mean PN output.
                u_l, u_r = pn_outputs(red_l, red_r, place)
                nominal = NOMINAL_MAX * 0.5 * (u_l + u_r)
            feed.publish(nominal, k_p, g_gaba)
            mn9 = feed.mn9()
            eat = mn9 >= EAT_THRESHOLD_HZ
            # Feeding fills only with the food at the mouth (centre
            # coverage at FILL_FULL); a distant EAT opens the gate
            # but does not fill the robot before it arrives.
            if state == "auto":
                if eat and frame is not None and at_mouth(fill):
                    satiety.feed(dt)
                else:
                    satiety.elapse(dt)
            level = (
                satiety.level if state == "auto" else STATE_LEVELS[state]
            )
            move = ""
            if eye is not None:
                # The feeding gate on fly-car's approach term: sigma
                # follows the current MN9 estimate, the membranes
                # advance by the wall time since the previous slice.
                plant.sigma = sigma_of(mn9)
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
                    f"  sigma {plant.sigma:.2f}"
                )
            if began - last_log >= LOG_S:
                last_log = began
                seen = ""
                if eye is not None:
                    seen = (
                        f"fill {fill:.3f}  eye {red_l:.2f}/{red_r:.2f}  "
                        f"place {place:+.2f}  "
                        f"blue {blue_l:.2f}/{blue_r:.2f}  "
                        f"loom {loom[0]:.2f}/{loom[1]:.2f}  "
                        f"td {occ.theta_dot:.2f}  "
                    )
                proboscis.show(mn9, eat, level,
                               red=(red_l + red_r) / 2.0,
                               blue=(blue_l + blue_r) / 2.0)
                print(
                    f"state {label}  k_p {k_p:.2f}  g_gaba {g_gaba:.2f}  "
                    f"{seen}nominal {nominal:.0f} Hz  "
                    f"MN9 {mn9:.1f} Hz {feed.counts}  "
                    f"{'EAT' if eat else 'refuse'}{move}",
                    flush=True,
                )
            rest = LOOP_S - (time.monotonic() - began)
            if rest > 0:
                time.sleep(rest)
    finally:
        feed.stop.set()
        counts_stop.set()
        drive.send(0, 0)
        proboscis.show(0.0, False)
        if eye is not None:
            eye.close()


App.run(user_loop=loop)
