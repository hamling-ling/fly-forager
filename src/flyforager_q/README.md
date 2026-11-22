# flyforager_q — 実機アプリ

カメラで餌を見て、抽出回路（687 ニューロン）で食べるかどうかを判断し、
UNO Q の LED マトリクスに口吻として表示する App Lab アプリ。
構成は fly-car の flycar_q に倣う。

## 判断の流れ（python/main.py）

1. 状態を読む（`state.txt`、なければ config の既定）
2. 最新フレームから餌の色の被覆率 → 公称入力レート（v1 の代理写像）
3. C++ カーネル（python/kernel/）を TRIALS 回分（1 試行 = 脳時間 1 秒、
   実機で約 0.2 秒）実行し、MN9 の平均発火率を得る
4. 10 Hz 以上で EAT。LED マトリクスのバーの長さが MN9、太さとランプが
   eat（緑）／refuse（赤）

## 状態（空腹／満腹）

状態は実験 D の実測パラメータ対（k_p, g_gaba）：

| 状態 | k_p | g_gaba | 効き方（実測） |
|---|---|---|---|
| base | 1.0 | 1.0 | EC50 72 Hz、食べ始め 60 Hz |
| hungry（H3） | 1.5 | 0.7 | EC50 42 Hz、食べ始め 40 Hz |
| satiated（S3） | 0.67 | 1.3 | EC50 113 Hz、食べ始め 100 Hz |

デモ中の切り替えは、アプリの隣（app.yaml と同じ場所）に置く
`state.txt` に `hungry` / `base` / `satiated` のいずれかを書く。
判断ごとに読み直すので、再起動は要らない。

## ベンチモード

カメラなしで判断だけ試す場合は config.py の `MANUAL_RATE` に
公称レート（例： 60.0）を入れる。カメラを開かず、その濃さで
判断し続ける。

## デプロイ

リポジトリのルートから：

```
scripts/deploy_flyforager_q.sh
```

fly-car の deploy と同じ流儀（停止 → コピー → スケッチのハッシュで
キャッシュ判定 → 起動）。カーネルのバイナリはコピーに含めず、
アプリが初回起動時にボード上の g++ でコンパイルする。

## カーネルのデータ

python/kernel/ の .bin は抽出回路の接続表（CSR 形式）。
w_base.bin が重み、gaba.bin が GABA ゲインを掛ける結合のマスク
（糖 GRN の出力は除外、実験 D の手順どおり）。
出所と検証値は research/ と親リポジトリの README を参照。

.bin はリポジトリに入れず、Release（タグ `kernel-v1`）の
`kernel-data.zip` で配る。clone のあとに次を実行すると、
SHA256 とサイズを照合して python/kernel/ に配置される。

```
scripts/download_kernel_data.sh
```
