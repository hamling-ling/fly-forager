#include "proboscis.h"

#include <Arduino.h>
#include <Arduino_LED_Matrix.h>

static const int PIXELS = 104;  // 8 rows x 13 cols
static const int COLS = 13;
static const unsigned long BLANK_MS = 3000;

static Arduino_LED_Matrix matrix;
static unsigned long lastMs = 0;
static bool live = false;
static int satietyPct = 0;
static int detRedPct = 0;
static int detBluePct = 0;

static int barLen(int pct) {
    int len = (pct * COLS + 50) / 100;
    if (len > COLS) len = COLS;
    if (len < 0) len = 0;
    return len;
}

static void writeLamp(int pin, int on) {
    digitalWrite(pin, on ? LOW : HIGH);
}

static void lampsOff() {
    writeLamp(LED3_R, 0);
    writeLamp(LED3_G, 0);
    writeLamp(LED3_B, 0);
}

// Detection rows (0 = red, 5 = blue) and gauge rows (6-7) always;
// the decision bar only when decision=true.
static void drawFrame(int mn9, int eat, bool decision) {
    uint8_t frame[PIXELS] = {};
    int rlen = barLen(detRedPct);
    for (int c = 0; c < rlen; ++c) frame[0 * COLS + c] = 1;
    int blen = barLen(detBluePct);
    for (int c = 0; c < blen; ++c) frame[5 * COLS + c] = 1;
    int glen = barLen(satietyPct);
    for (int c = 0; c < glen; ++c) {
        frame[6 * COLS + c] = 1;
        frame[7 * COLS + c] = 1;
    }
    if (decision && mn9 > 0) {
        int len = (mn9 * COLS + 50) / 100;  // 100 Hz で全幅
        if (len > COLS) len = COLS;
        int rowLo = eat ? 1 : 2;
        int rowHi = eat ? 4 : 3;
        for (int r = rowLo; r <= rowHi; ++r)
            for (int c = 0; c < len; ++c) frame[r * COLS + c] = 1;
    }
    matrix.draw(frame);
}

void proboscisSetup() {
    matrix.begin();
    matrix.setGrayscaleBits(1);
    pinMode(LED3_R, OUTPUT);
    pinMode(LED3_G, OUTPUT);
    pinMode(LED3_B, OUTPUT);
    lampsOff();
    drawFrame(0, 0, false);
}

void showProboscis(int mn9, int eat, int satiety, int redPct, int bluePct) {
    if (satiety < 0) satiety = 0;
    if (satiety > 100) satiety = 100;
    satietyPct = satiety;
    if (redPct < 0) redPct = 0;
    if (redPct > 100) redPct = 100;
    detRedPct = redPct;
    if (bluePct < 0) bluePct = 0;
    if (bluePct > 100) bluePct = 100;
    detBluePct = bluePct;
    drawFrame(mn9, eat, true);
    if (mn9 > 0) {
        writeLamp(LED3_G, eat);
        writeLamp(LED3_R, eat ? 0 : 1);
        writeLamp(LED3_B, 0);
    } else {
        lampsOff();
    }
    lastMs = millis();
    live = true;
}

void proboscisLoop() {
    if (!live) {
        return;
    }
    if (millis() - lastMs < BLANK_MS) {
        return;
    }
    // Blank the decision bar only; the satiety gauge stays up.
    drawFrame(0, 0, false);
    lampsOff();
    live = false;
}
