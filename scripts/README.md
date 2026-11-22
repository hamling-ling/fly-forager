# scripts

## 実機へのデプロイ

`deploy_flyforager_q.sh` が flyforager_q を UNO Q にデプロイする
（fly-car の deploy と同じ流儀）。使い方は `src/flyforager_q/README.md`。

## 全脳データの入手

全脳モデルで実験を再現するには、次の2つを `data/` に置く（どちらもこのリポジトリには含めない）。

1. Shiu et al. のモデルコードと FlyWire v783 の接続表
   - コード: https://github.com/philshiu/Drosophila_brain_model （MIT）
   - 接続表（Completeness_783.csv / Connectivity_783.parquet）は同リポジトリの案内に従って入手する。FlyWire のデータは CC BY-NC 4.0
2. FlyWire のアノテーション（Schlegel et al. 2024、v3.2.0）— ニューロンの型と伝達物質の予測に使う

抽出済みの部分回路だけなら全脳データの入手は不要で、索引は `src/flyforager/subcircuit/` の CSV、接続表の本体は Release（タグ subcircuit-v1）の Connectivity_sub.parquet で足りる。
