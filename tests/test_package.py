from pathlib import Path

import flyforager


def test_subcircuit_files_present():
    # 接続表の本体（Connectivity_sub.parquet）は Release（タグ subcircuit-v1）で配るため、
    # リポジトリ内の索引 CSV だけを確認する
    sub = Path(flyforager.__file__).parent / "subcircuit"
    assert (sub / "Completeness_sub.csv").exists()
    assert (sub / "neuron_ids.csv").exists()


def test_subcircuit_neuron_count():
    sub = Path(flyforager.__file__).parent / "subcircuit"
    lines = (sub / "neuron_ids.csv").read_text().strip().splitlines()
    assert len(lines) - 1 == 687  # ヘッダを除いた抽出ニューロン数
