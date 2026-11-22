#include <Arduino_RouterBridge.h>

#include "proboscis.h"

void setup() {
    Monitor.begin(115200);
    delay(100);
    proboscisSetup();
    Bridge.begin();
    Bridge.provide("showProboscis", showProboscis);
    Monitor.println("Proboscis ready");
}

void loop() {
    proboscisLoop();
}
