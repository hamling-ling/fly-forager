"""Board-independent logic of flyforager_q: states, food mapping,
kernel output parsing, and the state file. Run from the repo root."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "src" / "flyforager_q" / "python"))

import config
import food
import kernel


def test_state_presets_are_the_measured_sets():
    assert config.STATES["base"] == (1.0, 1.0)
    assert config.STATES["hungry"] == (1.5, 0.7)      # H3
    assert config.STATES["satiated"] == (0.67, 1.3)   # S3
    assert config.DEFAULT_STATE in config.STATES
    assert config.EAT_THRESHOLD_HZ == 10.0


def test_fill_to_rate():
    assert food.fill_to_rate(0.0) == 0.0
    assert food.fill_to_rate(-1.0) == 0.0
    assert food.fill_to_rate(config.FILL_FULL) == config.NOMINAL_MAX
    assert food.fill_to_rate(1.0) == config.NOMINAL_MAX  # clamped
    half = food.fill_to_rate(config.FILL_FULL / 2)
    assert half == config.NOMINAL_MAX / 2


def test_parse_result():
    text = (
        "trial 0: MN9 74, total 12923, wall 0.2143 s\n"
        "mean wall 0.2081 s over 1 trials (nominal 150 Hz, "
        "k_p 1.00, g_gaba 1.00, n=687)\n"
        "result mn9_mean 74.00 mn9_counts 74\n"
    )
    mean, counts = kernel.parse_result(text)
    assert mean == 74.0
    assert counts == [74]


def test_parse_result_multi():
    mean, counts = kernel.parse_result(
        "result mn9_mean 28.20 mn9_counts 27,30,32\n")
    assert mean == 28.2
    assert counts == [27, 30, 32]


def test_read_state(tmp_path):
    path = tmp_path / "state.txt"
    assert config.read_state(path) == config.DEFAULT_STATE  # missing
    path.write_text("hungry\n")
    assert config.read_state(path) == "hungry"
    path.write_text("SATIATED")
    assert config.read_state(path) == "satiated"
    path.write_text("bogus")
    assert config.read_state(path) == config.DEFAULT_STATE
