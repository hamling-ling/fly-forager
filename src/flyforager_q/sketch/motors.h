#pragma once

// rightPulse / leftPulse は -255〜255。正が前進、0 が停止。
// flycar_q の motors を移植（face 連携だけ外した）。
int setMotorSpeed(int rightPulse, int leftPulse);
void motorsSetup();
void motorsLoop();
