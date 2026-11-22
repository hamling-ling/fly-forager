#include "proboscis.h"

#include <Arduino.h>
#include <Arduino_LED_Matrix.h>

static const int PIXELS = 104;  // 8 rows x 13 cols
static const int COLS = 13;
static const unsigned long BLANK_MS = 3000;

static Arduino_LED_Matrix matrix;
static unsigned long lastMs = 0;
static bool live = false;

static void writeLamp(int pin, int on) {
    digitalWrite(pin, on ? LOW : HIGH);
}

static void lampsOff() {
    writeLamp(LED3_R, 0);
    writeLamp(LED3_G, 0);
    writeLamp(LED3_B, 0);
}

static void drawBlank() {
    uint8_t frame[PIXELS] = {};
    matrix.draw(frame);
}

void proboscisSetup() {
    matrix.begin();
    matrix.setGrayscaleBits(1);
    pinMode(LED3_R, OUTPUT);
    pinMode(LED3_G, OUTPUT);
    pinMode(LED3_B, OUTPUT);
    lampsOff();
    drawBlank();
}

void showProboscis(int mn9, int eat) {
    uint8_t frame[PIXELS] = {};
    if (mn9 > 0) {
        int len = (mn9 * COLS + 50) / 100;  // 100 Hz で全幅
        if (len > COLS) len = COLS;
        int rowLo = eat ? 2 : 3;
        int rowHi = eat ? 5 : 4;
        for (int r = rowLo; r <= rowHi; ++r)
            for (int c = 0; c < len; ++c) frame[r * COLS + c] = 1;
        writeLamp(LED3_G, eat);
        writeLamp(LED3_R, eat ? 0 : 1);
        writeLamp(LED3_B, 0);
    } else {
        lampsOff();
    }
    matrix.draw(frame);
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
    drawBlank();
    lampsOff();
    live = false;
}
