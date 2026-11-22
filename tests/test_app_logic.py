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
    path.write_text("auto")
    assert config.read_state(path) == "auto"
    path.write_text("bogus")
    assert config.read_state(path) == config.DEFAULT_STATE


def test_params_at_measured_points():
    assert config.params_at(0.0) == config.STATES["hungry"]
    assert config.params_at(0.5) == config.STATES["base"]
    assert config.params_at(1.0) == config.STATES["satiated"]
    # clamped outside 0..1
    assert config.params_at(-1.0) == config.STATES["hungry"]
    assert config.params_at(2.0) == config.STATES["satiated"]
    # k_p falls and g_gaba rises monotonically toward satiety
    ks = [config.params_at(x / 10)[0] for x in range(11)]
    gs = [config.params_at(x / 10)[1] for x in range(11)]
    assert all(a >= b for a, b in zip(ks, ks[1:]))
    assert all(a <= b for a, b in zip(gs, gs[1:]))


def test_plant_gate():
    import plant

    # fly-car's paper calibration: 0.10 in both eyes -> current ~1.47
    i_l, i_r = plant.dna_current(0.10, 0.10)
    assert abs(i_l - 1.4667) < 0.01 and abs(i_r - 1.4667) < 0.01
    # the gate zeroes the approach term and nothing else
    s, o, v_l, v_r = plant.wheel_speeds(100.0, 100.0, 0.0, 0.0, sigma=1.0)
    assert abs(v_l - 0.03) < 1e-9 and abs(v_r - 0.03) < 1e-9
    s, o, v_l, v_r = plant.wheel_speeds(100.0, 100.0, 0.0, 0.0, sigma=0.0)
    assert v_l == 0.0 and v_r == 0.0
    # escape is not gated: DNp01 still reverses at sigma 0
    s, o, v_l, v_r = plant.wheel_speeds(0.0, 0.0, 100.0, 100.0, sigma=0.0)
    assert abs(v_l + 0.03) < 1e-9 and abs(v_r + 0.03) < 1e-9
    # a held red frame drives forward with the gate open, not closed
    p = plant.Plant()
    step = p.steps(0.10, 0.10, n=1500)
    assert step.v_left > 0.0 and step.v_right > 0.0
    p2 = plant.Plant()
    p2.sigma = 0.0
    step = p2.steps(0.10, 0.10, n=1500)
    assert step.v_left == 0.0 and step.v_right == 0.0
    # the safety stop overrides the gate
    p3 = plant.Plant()
    step = p3.steps(0.80, 0.80, n=1500)
    assert step.v_left == 0.0 and step.v_right == 0.0


def test_pn_outputs_shared_input():
    import plant

    assert plant.pn_outputs(0.0, 0.0) == (0.0, 0.0)
    u_l, u_r = plant.pn_outputs(0.75, 0.75)
    assert abs(u_l - 0.9375) < 1e-9 and abs(u_r - 0.9375) < 1e-9
    # the edge case from the 2026-11-22 log: 0.06 coverage at the
    # right edge drives DNa02 hard, and the PN stage must show it
    u_l, u_r = plant.pn_outputs(0.0, 0.06, place=1.0)
    assert u_l == 0.0 and abs(u_r - 0.75) < 1e-9


def test_at_mouth():
    import food

    assert food.at_mouth(0.33)
    assert food.at_mouth(config.FILL_FULL)
    assert not food.at_mouth(0.05)


def test_arrived():
    import food

    assert food.arrived(0.77)
    assert food.arrived(config.ARRIVE_FILL)
    assert not food.arrived(0.33)


def test_pulse_conversion():
    import pulse

    assert pulse.wheel_pulses(0.05, 0.05) == (40, 40)
    assert pulse.motion_pulse(5) == 0  # below the forward start
    assert pulse.motion_pulse(13) == 13
    assert pulse.motion_pulse(-1) == -37  # reverse dead-band shift
    assert pulse.motion_pulse(0) == 0


def test_satiety_dynamics():
    s = config.Satiety()
    assert s.level == 0.0
    for _ in range(config.EATS_TO_FULL):
        s.eat()
    assert s.level == 1.0
    s.eat()
    assert s.level == 1.0  # capped
    s.elapse(config.HUNGER_RETURN_S / 2)
    assert abs(s.level - 0.5) < 1e-9
    s.elapse(config.HUNGER_RETURN_S)
    assert s.level == 0.0  # floored
