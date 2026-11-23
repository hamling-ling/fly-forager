"""fly-car's drive model, with the feeding circuit gating approach.

Ported from flycar.behavior (Plant, Lif, the PN saturation, the
crossed DNa02/DNp01 wheel readout, the wheel filter, the rotation
cap, the red safety stop), with exactly one change, in wheel_speeds:

    v_L = k (sigma * r_R^DNa02 - r_R^DNp01)
    v_R = k (sigma * r_L^DNa02 - r_L^DNp01)

sigma is the feeding gate: a sigmoid of the feeding circuit's MN9
estimate, centred on the 10 Hz threshold. It multiplies only the
approach (DNa02) term; the escape (DNp01) term and the safety stop
are untouched, so a satiated robot still flees a looming blue and
still stops at a red sheet held against it.

Not ported yet: the blue loom measurement that produces the DNp01
current (flycar.loom / occupancy). The Plant accepts the current as
``loom`` and the app passes (0, 0), so DNp01 is silent for now.
Pose integration is also dropped; the app only needs wheel speeds.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

# Membrane and readout constants, identical to flycar.behavior.
TAU_MS = 5.0
V_THRESHOLD = 1.0
REFRAC_MS = 5.0
DT = 0.001
TAU_RATE_S = 0.050
TRACK = 0.12

RED_FILL = 0.75  # safety stop: both eye ranges at least this full

N_ORN = 1.0
C0 = 0.05
ALPHA = 4.0
BETA = 0.45
KAPPA = 1.5
OMEGA_SAFE = 1.5
FORWARD_PER_HZ = 0.0003
TAU_V = 0.10
CATCH_UP_S = 0.70
HOLD_STEPS = 20


def catch_up_steps(elapsed_s: float) -> int:
    """Membrane steps for the wall time since the previous tick."""
    span = min(max(float(elapsed_s), HOLD_STEPS * DT), CATCH_UP_S)
    return max(1, int(round(span / DT)))


def pn(concentration: float) -> float:
    """PN saturation. A negative concentration is read as empty."""
    c = max(float(concentration), 0.0)
    return N_ORN * c / (N_ORN * c + C0)


def concentration_gain(place: float) -> float:
    """1 at the centre, ``1 + KAPPA`` at an edge."""
    span = min(abs(float(place)), 1.0)
    return 1.0 + KAPPA * span


def prime_concentration(
    red_l: float, red_r: float, place: float = 0.0
) -> tuple[float, float]:
    """Eye fractions after the edge factor. An empty eye stays at 0."""
    gain = concentration_gain(place)
    return (gain * float(red_l), gain * float(red_r))


def pn_outputs(
    red_l: float, red_r: float, place: float = 0.0
) -> tuple[float, float]:
    """PN output per eye: saturation of the place-gained fractions.

    This is the stage the feeding circuit shares: its nominal input
    rate is NOMINAL_MAX times the mean PN output, so the gate reads
    the same transformed signal that drives DNa02 -- including the
    edge amplification, which raw coverage misses (a small red at
    the frame edge drives DNa02 hard at ~0.06 coverage).
    """
    c_l, c_r = prime_concentration(red_l, red_r, place)
    return (pn(c_l), pn(c_r))


def dna_current(
    red_l: float, red_r: float, place: float = 0.0
) -> tuple[float, float]:
    """DNa02 current. Each side keeps its PN and subtracts the other."""
    u_l, u_r = pn_outputs(red_l, red_r, place)
    return (ALPHA * (u_l - BETA * u_r), ALPHA * (u_r - BETA * u_l))


def red_fills_the_frame(red_l: float, red_r: float) -> bool:
    """Safety stop. Both eye ranges covered, whatever the cells do."""
    return min(float(red_l), float(red_r)) >= RED_FILL


def wheel_speeds(
    dna_l: float,
    dna_r: float,
    gf_l: float,
    gf_r: float,
    sigma: float = 1.0,
) -> tuple[float, float, float, float]:
    """Path speed, yaw, left and right wheel speeds (m/s).

    Crossed readout as in fly-car: the left wheel reads the right
    pair. The feeding gate sigma multiplies DNa02 (approach) only.
    """
    v_left = FORWARD_PER_HZ * (sigma * float(dna_r) - float(gf_r))
    v_right = FORWARD_PER_HZ * (sigma * float(dna_l) - float(gf_l))
    speed = 0.5 * (v_left + v_right)
    omega = (v_right - v_left) / TRACK
    return speed, omega, v_left, v_right


def limit_rotation(v_left: float, v_right: float) -> tuple[float, float]:
    """Shrink a smoothed pair whose yaw exceeds ``OMEGA_SAFE``."""
    left = float(v_left)
    right = float(v_right)
    omega = (right - left) / TRACK
    if abs(omega) <= OMEGA_SAFE:
        return left, right
    mean = 0.5 * (left + right)
    sign = 1.0 if omega >= 0.0 else -1.0
    half = sign * OMEGA_SAFE * TRACK / 2.0
    return mean - half, mean + half


def motion_mode(_speed: float, v_left: float, v_right: float) -> str:
    """Label the wheels after the command. The label does not choose it."""
    if abs(v_left) < 1e-6 and abs(v_right) < 1e-6:
        return "stop"
    if v_left * v_right < 0.0:
        return "spin"
    if v_left < 0.0 or v_right < 0.0:
        return "back"
    return "cruise"


class Lif:
    """Current-based LIF, as in flycar.behavior. State carries across frames."""

    def __init__(self) -> None:
        self.v = 0.0
        self.silent_until = 0
        self.i = 0
        self.rate = 0.0

    def step(self, drive: float) -> tuple[float, bool]:
        self.i += 1
        step = (DT * 1000) / TAU_MS
        spiked = False
        if self.i < self.silent_until:
            self.v = 0.0
        else:
            self.v += step * (-self.v + float(drive))
            if self.v >= V_THRESHOLD:
                spiked = True
                self.v = 0.0
                self.silent_until = self.i + int(round(REFRAC_MS / (DT * 1000)))
        impulse = (1.0 / DT) if spiked else 0.0
        self.rate += (DT / TAU_RATE_S) * (-self.rate + impulse)
        return self.v, spiked


@dataclass
class Step:
    mode: str
    speed: float
    omega: float
    v_left: float
    v_right: float


class Plant:
    """Four cells (DNa02 pair, DNp01 pair) and the gated readout.

    ``sigma`` is set by the caller from the latest feeding decision
    and read on every emit; it can change between steps calls.
    """

    def __init__(self) -> None:
        self.gf_l = Lif()
        self.gf_r = Lif()
        self.dna_l = Lif()
        self.dna_r = Lif()
        self.sigma = 1.0
        self.wheel_left = 0.0
        self.wheel_right = 0.0
        self._wall = time.monotonic()

    def steps(
        self,
        red_l: float,
        red_r: float,
        blue_l: float = 0.0,
        blue_r: float = 0.0,
        n: int | None = None,
        loom: tuple[float, float] = (0.0, 0.0),
        place: float = 0.0,
    ) -> Step:
        """Hold one frame and advance the membranes by ``n`` steps.

        ``n`` omitted follows the wall clock since the previous call,
        capped at ``CATCH_UP_S`` like fly-car's app loop. Signature
        mirrors flycar.behavior: ``blue_l`` / ``blue_r`` are carried
        for the log and the lamps and do not drive DNp01 -- the loom
        current does.
        """
        began = time.monotonic()
        if n is None:
            n = catch_up_steps(began - self._wall)
        self._wall = began
        if n < 1:
            raise ValueError("n must be at least 1")
        i_gf = (float(loom[0]), float(loom[1]))
        i_dna = dna_current(red_l, red_r, place)
        step: Step | None = None
        for _ in range(n):
            self.gf_l.step(i_gf[0])
            self.gf_r.step(i_gf[1])
            self.dna_l.step(i_dna[0])
            self.dna_r.step(i_dna[1])
            step = self._emit(red_l, red_r)
        if step is None:
            raise RuntimeError("steps advanced no membrane time")
        return step

    def _emit(self, red_l: float, red_r: float) -> Step:
        if red_fills_the_frame(red_l, red_r):
            self.wheel_left = 0.0
            self.wheel_right = 0.0
            v_left, v_right = 0.0, 0.0
        else:
            _s, _o, target_left, target_right = wheel_speeds(
                self.dna_l.rate,
                self.dna_r.rate,
                self.gf_l.rate,
                self.gf_r.rate,
                self.sigma,
            )
            follow = DT / TAU_V
            self.wheel_left += follow * (-self.wheel_left + target_left)
            self.wheel_right += follow * (-self.wheel_right + target_right)
            v_left, v_right = limit_rotation(self.wheel_left, self.wheel_right)
        speed = 0.5 * (v_left + v_right)
        omega = (v_right - v_left) / TRACK
        return Step(
            mode=motion_mode(speed, v_left, v_right),
            speed=speed,
            omega=omega,
            v_left=v_left,
            v_right=v_right,
        )
