# scripts

## 全脳データの入手

全脳モデルで実験を再現するには、次の2つを `data/` に置く（どちらもこのリポジトリには含めない）。

1. Shiu et al. のモデルコードと FlyWire v783 の接続表
   - コード: https://github.com/philshiu/Drosophila_brain_model （MIT）
   - 接続表（Completeness_783.csv / Connectivity_783.parquet）は同リポジトリの案内に従って入手する。FlyWire のデータは CC BY-NC 4.0
2. FlyWire のアノテーション（Schlegel et al. 2024、v3.2.0）— ニューロンの型と伝達物質の予測に使う

抽出済みの部分回路だけなら入手は不要で、`src/flyforager/subcircuit/` の接続表で足りる。
