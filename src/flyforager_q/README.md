# flyforager_q — 実機アプリ

カメラで餌を見て、抽出回路（687 ニューロン）で食べるかどうかを判断し、
UNO Q の LED マトリクスに口吻として表示する App Lab アプリ。
構成は fly-car の flycar_q に倣う。

## 並行に流れる2つの回路（python/main.py）

判断周期はない。ハエと同じく、2つの回路が並行に流れ、信号だけで
結合する。

- 視覚回路（plant.py、fly-car のモデル）はメインループの刻み
  （LOOP_S = 0.1 秒）で連続に進む。毎刻み、最新フレームと loom で
  膜を実時間ぶん進め、車輪を指令し直す。
- 採餌回路（C++ カーネル）は別スレッドで 1 秒試行を連続に回す
  （1 試行 = 脳時間 1 秒、実機で約 0.2 秒）。直近2試行の平均が
  「現在の MN9 発火率」で、最大でも約 0.4 秒遅れの推定値になる。
- 結合信号は2つだけ：カーネルの入力レートは DNa02 を駆動する
  同じ目の PN 出力の平均 × NOMINAL_MAX。MN9 推定値が 10 Hz 以上で
  ゲート σ が開き、fly-car の接近項が通る（下記）。

LED とログは連続状態を1秒ごとに読み出すだけで、判断ではない。
LED は上段バーが MN9（太さとランプが eat 緑／refuse 赤）、行0が
赤の検出量、行5が青の検出量、下段2行が満腹度ゲージ。固定状態では
hungry = 空、base = 半分、satiated = 全点灯。ベンチモード
（MANUAL_RATE）では動かない。

## 駆動 — fly-car のモデル＋採餌ゲート

駆動は fly-car の数理モデルそのもの（plant.py に flycar.behavior
から移植：PN 飽和、交差読み出し、車輪フィルタ、回転キャップ、
赤の安全停止。pulse.py に flycar.pulse のデッドバンド変換）。
変更は1か所だけで、読み出しの接近項（DNa02）に採餌回路の
ゲート σ が掛かる:

$$
v_L = k \cdot \left(\sigma \cdot r_R^{\mathrm{DNa02}} - r_R^{\mathrm{DNp01}}\right), \qquad
v_R = k \cdot \left(\sigma \cdot r_L^{\mathrm{DNa02}} - r_L^{\mathrm{DNp01}}\right), \qquad
\sigma = \begin{cases} 1 & \widehat{\mathrm{MN9}} \ge 10\ \mathrm{Hz}\ (\mathrm{EAT}) \\ 0 & \mathrm{refuse} \end{cases}
$$

$k$ は関数ではなく定数で、発火率を車輪速度に換算する係数
（コードでは FORWARD_PER_HZ）。満腹で refuse になれば赤への
接近だけが消え、逃避項と安全停止はそのまま残る。目の入力（赤の左右レンジ被覆率と重心 place）は
food.py の red_eyes が flycar.occupancy と同じ定義で測り、
採餌回路への公称レートは同じ目の PN 段出力の平均 × 150 Hz。
生の被覆率だと、端の小さい赤（被覆率 0.06 でも place 利得で
DNa02 は 170 Hz 級）が公称 6 Hz に潰れてゲートが開かないため、
DNa02 を駆動する変換後の信号を共有する。中央 ROI の被覆率は
ログ表示と満腹加算の判定のみ。
満腹度の加算は「口元」（中央 ROI の被覆率が FILL_FULL = 0.25
以上）で EAT のときだけ — 遠くの EAT はゲートを開くが、着く前に
満腹にはしない。両眼 0.75 の安全停止 fill は顔に紙を押し当てた
条件で、手持ちデモでは届かない（両眼は 0.2 前後に留まる）。
スケッチの motors は flycar_q からの移植（setMotorSpeed、右ピン3／
左ピン5、3秒ウォッチドッグ）。車輪指令は LOOP_S ごとに更新する。

青の loom も fly-car と同一：loom.py と occupancy.py は
flycar からの逐語コピー（import の1行だけ変更）、閾値は同じ
color_thresholds.json、細胞表は同じ loom_cells.npz（fly-car の
src/flycar/ からコピーする二進ファイル。SHA256
e02722fcd8d311b3714fe05842f57c8632676058e4525ec381d55515fd71036b）。
Counts は flycar_q と同じ 10 Hz で別スレッドが更新し、メインループは
最新の loom 電流を plant.steps に渡す。DNp01 は σ でゲートされ
ない（満腹でも青からは逃げる）。到着停止は back（逃避）のとき
効かない。赤の経路だけはこのアプリの調整済み（food.py）のまま。

未移植：fly-car の直進ヒンジ補正。速度の実測もまだない
（m/s は公称）。

## 数理モデル

全体は、視覚回路と採餌回路が並行に流れ、2本の信号だけで結合した
系である。判断周期はなく、すべての量は連続時間の関数。

目の変換（fly-car と同一の PN 段、 $i \in \{L, R\}$ 、 $c_i$ は目の
赤被覆率、 $\mathrm{place}$ は赤の重心）：

$$
u_i = \mathrm{PN}(c_i, \mathrm{place})
$$

採餌回路への入力は、DNa02 を駆動するのと同じ変換後の信号：

$$
\rho = \rho_{\max} \cdot \frac{u_L + u_R}{2}, \qquad \rho_{\max} = 150\ \mathrm{Hz}
$$

実効入力レートは $k_p \rho$ で、20 個の糖 GRN への Poisson 入力に
なる。採餌回路は抽出サブサーキット（687 ニューロン、LIF）で、
GABA 作動性出力の重みに $g_{\mathrm{GABA}}$ を掛ける。1 秒試行の
MN9 スパイク数を $N_j$ として、

$$
\widehat{\mathrm{MN9}} = \frac{N_j + N_{j-1}}{2}\ \mathrm{Hz}, \qquad
\sigma = \begin{cases} 1 & \widehat{\mathrm{MN9}} \ge 10\ \mathrm{Hz} \\ 0 & \text{それ以外} \end{cases}
$$

駆動の読み出し（fly-car の交差読み出し＋ゲート $\sigma$ ）：

$$
v_L = k \cdot \left(\sigma \cdot r_R^{\mathrm{DNa02}} - r_R^{\mathrm{DNp01}}\right), \qquad
v_R = k \cdot \left(\sigma \cdot r_L^{\mathrm{DNa02}} - r_L^{\mathrm{DNp01}}\right)
$$

$r^{\mathrm{DNp01}}$ は loom（LC4／LPLC2 → DNp01、fly-car と同一）
から来て、 $\sigma$ ではゲートされない。回転キャップ・車輪フィルタ・
赤の安全停止は fly-car のまま。

満腹度 $s \in [0, 1]$ は率で積分する：

$$
\frac{ds}{dt} = \begin{cases}
+\dfrac{1}{T_{\mathrm{eat}}} & \sigma = 1 \text{ かつ } \mathrm{fill} \ge f_{\mathrm{full}} \\
-\dfrac{1}{T_{\mathrm{hungry}}} & \text{それ以外}
\end{cases}
$$

ここで $T_{\mathrm{eat}}$ は満腹までの食事時間（config の
`EATS_TO_FULL` × `EAT_STEP_S` = 12 秒）、 $T_{\mathrm{hungry}}$ は
空腹に戻る時間（`HUNGER_RETURN_S` = 30 秒）、 $f_{\mathrm{full}}$ は
口元の被覆率の閾値（`FILL_FULL` = 0.25）。数式の中で config 定数名を
そのまま書かないのは、GitHub の数式処理が `\_` を落として
`EATS_TO_FULL` のような名前が二重下付き添字エラーになるため。

$s$ が 1 に達するとラッチし、 $s$ が `FULL_RELEASE` $= 0.6$
まで下がる間は実効満腹度 $s_{\mathrm{eff}} = 1$ を保つ（それ以外は
$s_{\mathrm{eff}} = s$ ）。パラメータは $s_{\mathrm{eff}}$ の区分線形
補間で、測定点を通る：

| $s_{\mathrm{eff}}$ | 0 (hungry) | 0.5 (base) | 1 (satiated) |
| --- | --- | --- | --- |
| $k_p$ | 1.5 | 1.0 | 0.67 |
| $g_{\mathrm{GABA}}$ | 0.7 | 1.0 | 1.3 |

到着停止（提示層）： $\mathrm{fill} \ge 0.60$ （`ARRIVE_FILL`）で
車輪を止めてその場で食べる。ただし逃避中（mode back）はそちらが
優先する。

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
`kernel: built` → カメラの warmup → 1 秒ごとの状態行
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
