from pathlib import Path

import flyforager


def test_subcircuit_files_present():
    sub = Path(flyforager.__file__).parent / "subcircuit"
    assert (sub / "Completeness_sub.csv").exists()
    assert (sub / "Connectivity_sub.parquet").exists()
    assert (sub / "neuron_ids.csv").exists()


def test_subcircuit_neuron_count():
    sub = Path(flyforager.__file__).parent / "subcircuit"
    lines = (sub / "neuron_ids.csv").read_text().strip().splitlines()
    assert len(lines) - 1 == 687  # ヘッダを除いた抽出ニューロン数
