#pragma once

// 口吻の代わりの LED 表示（8行×13列）。showProboscis は MN9 の発火率、
// eat フラグ、満腹度（0〜100）、赤と青の検出量（0〜100）を受ける。
//   行0: 赤の検出量バー（両目の被覆率の平均）。常時表示。
//   行1-4（eat）／行2-3（refuse）: 判断バー。長さは発火率、ランプは
//     eat で緑、refuse で赤。最後の更新から 3 秒で判断バーだけ消す。
//   行5: 青の検出量バー（両目の青被覆率の平均）。常時表示。
//   行6-7: 満腹度ゲージ。左から満腹度ぶん点灯し、消灯中も残るので、
//     観客はロボットが満腹になっていく様子を見ていられる。
// マトリクス自体は単色なので、赤バー／青バーの区別は行の位置による。
// proboscisLoop が loop から呼ばれる前提（flycar_q の faceLoop が
// 呼ばれていなかった轍は踏まない）。
void proboscisSetup();
void proboscisLoop();
void showProboscis(int mn9, int eat, int satiety, int redPct, int bluePct);
