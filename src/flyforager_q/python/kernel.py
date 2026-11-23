"""Call the C++ decision kernel from Python.

The kernel (kernel/sim.cpp + the .bin circuit tables) is compiled on
the board the first time it is needed, or when sim.cpp is newer than
the binary. Compilation takes a few seconds with the board's g++.

One call runs TRIALS of 1 s of brain time and returns the MN9 spike
counts. The kernel is deterministic for a fixed seed base.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

KERNEL_DIR = Path(__file__).resolve().parent / "kernel"
BINARY = KERNEL_DIR / "sim"
SOURCE = KERNEL_DIR / "sim.cpp"

_RESULT = re.compile(r"result mn9_mean ([0-9.]+) mn9_counts ([0-9,]+)")


def parse_result(text: str) -> tuple[float, list[int]]:
    """(mean, counts) from the kernel's stdout. Pure, so it is testable."""
    match = _RESULT.search(text)
    if match is None:
        raise ValueError("kernel output has no result line")
    mean = float(match.group(1))
    counts = [int(x) for x in match.group(2).split(",")]
    return mean, counts


def ensure_built() -> None:
    """Check the kernel binary is present and current.

    The binary is built on the board's host by the deploy script: the
    App Lab container has no g++ (that is how v1 first died). This is
    only a guard with a clear message, plus a fallback build for
    environments that do have a compiler.
    """
    if BINARY.exists() and BINARY.stat().st_mtime >= SOURCE.stat().st_mtime:
        return
    try:
        print("kernel: compiling sim.cpp")
        done = subprocess.run(
            ["g++", "-O2", "-static", "-o", str(BINARY), str(SOURCE)],
            capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "kernel binary is missing and this container has no g++. "
            "Deploy with scripts/deploy_flyforager_q.sh, which builds "
            "the kernel on the board's host."
        ) from None
    if done.returncode != 0:
        raise RuntimeError(f"kernel build failed: {done.stderr.strip()}")
    print("kernel: built")


def decide(
    nominal_rate: float,
    k_p: float,
    g_gaba: float,
    trials: int,
    seed: int = 1000,
) -> tuple[float, list[int]]:
    """Run the kernel once. Returns (mean MN9 Hz, per-trial counts)."""
    done = subprocess.run(
        [
            str(BINARY),
            f"{nominal_rate:g}", str(trials), f"{k_p:g}", f"{g_gaba:g}",
            str(seed),
        ],
        cwd=KERNEL_DIR, capture_output=True, text=True, timeout=60,
    )
    if done.returncode != 0:
        raise RuntimeError(f"kernel failed: {done.stderr.strip()}")
    return parse_result(done.stdout)
