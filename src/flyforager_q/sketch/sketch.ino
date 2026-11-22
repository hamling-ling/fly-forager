#include <Arduino_RouterBridge.h>

#include "motors.h"
#include "proboscis.h"

void setup() {
    Monitor.begin(115200);
    delay(100);
    motorsSetup();
    proboscisSetup();
    Bridge.begin();
    Bridge.provide("setMotorSpeed", setMotorSpeed);
    Bridge.provide("showProboscis", showProboscis);
    Monitor.println("Forager ready");
}

void loop() {
    proboscisLoop();
    motorsLoop();
}
