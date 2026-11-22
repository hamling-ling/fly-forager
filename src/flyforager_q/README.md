# flyforager_q — 実機アプリ

カメラで餌を見て、抽出回路（687 ニューロン）で食べるかどうかを判断し、
UNO Q の LED マトリクスに口吻として表示する App Lab アプリ。
構成は fly-car の flycar_q に倣う。

## 判断の流れ（python/main.py）

1. 状態を読む（`state.txt`、なければ config の既定）
2. 最新フレームから餌の色の被覆率 → 公称入力レート（v1 の代理写像）
3. C++ カーネル（python/kernel/）を TRIALS 回分（1 試行 = 脳時間 1 秒、
   実機で約 0.2 秒）実行し、MN9 の平均発火率を得る
4. 10 Hz 以上で EAT。LED マトリクス上段のバーの長さが MN9、太さと
   ランプが eat（緑）／refuse（赤）。下段2行は満腹度ゲージで、
   判断バーの消灯（3秒）後も残るので、デモ中にログを見なくても
   満腹になっていく様子が分かる。固定状態では hungry = 空、
   base = 半分、satiated = 全点灯。
5. 行動層（behavior.py）が判断を車輪パルスに変えて駆動する
   （下記）。ベンチモード（MANUAL_RATE）では動かない。

## 駆動

スケッチの motors は flycar_q からの移植（setMotorSpeed、右ピン3／
左ピン5、3秒ウォッチドッグ）。判断周期（2秒）ごとに1回指令し、
MCU が次の判断まで保持する。行動は4つ:

| 状態 | 条件 | 動き |
|---|---|---|
| search | 餌が見えない（fill < 0.02） | その場で旋回して探す |
| approach | 見えるが遠い | 左右の被覆率の差で操舵しながら前進 |
| eat | 近距離（fill ≥ 0.20）で EAT | 停止して摂食 |
| reject | 近距離で refuse | 弧を描いて後退 |

行動層は演出層の設計で、回路の出力は MN9 のみ。fly-car の直進
ヒンジ補正は v1 では移植していない（パルスは始動閾値より十分
大きく取る）。速度の実測もまだない。

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

`state.txt` に `auto` と書くと自動モードになる。満腹度（0〜1）が
判断に積算され、食べるたびに満腹側へ 1/5 ずつ進み、餌から離れて
いると10分かけて空腹側へ戻る。パラメータは hungry（0）→ base（0.5）
→ satiated（1）の実測3点を直線でつないだものを使う。
蓄積と回復の速さ自体は演出層の設計値で、実測は3点と用量反応曲線。

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
deploy の最中にボードのホスト側で g++ でビルドする
（App Lab のコンテナには g++ が無いので、アプリ自身はビルドできない）。

## ログの取り方

```
scripts/logs_flyforager_q.sh
```

実機アプリのログを流しながら `logs/flyforager_q-YYYYMMDD-HHMMSS.log`
に保存する。Ctrl-C で止めるとファイルが残る。期待する流れは
`kernel: built` → カメラの warmup → 2 秒ごとの判断行
（`state base fill ... MN9 ... refuse/EAT`）。

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
