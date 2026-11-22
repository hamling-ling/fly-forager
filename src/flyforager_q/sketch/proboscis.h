#pragma once

// 口吻の代わりの LED 表示。showProboscis は MN9 の発火率と eat フラグを
// 受ける。バーは発火率の長さで、eat のとき太くなり、ランプは緑、
// refuse は赤。最後の更新から 3 秒で消す（proboscisLoop が loop から
// 呼ばれる前提。flycar_q の faceLoop が呼ばれていなかった轍は踏まない）。
void proboscisSetup();
void proboscisLoop();
void showProboscis(int mn9, int eat);
