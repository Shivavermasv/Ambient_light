// renderer.cpp
// LED rendering logic for all modes

#include "config.h"
#include "state.h"
#include "modes.h"
#include <FastLED.h>

CRGB leds[NUM_LEDS];

void setupLEDs() {
    FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
    #if DISABLE_POWER_LIMIT
    FastLED.setMaxPowerInVoltsAndMilliamps(LED_VOLTAGE, 100000); // effectively uncapped; ensure PSU/wiring are safe
    #else
    FastLED.setMaxPowerInVoltsAndMilliamps(LED_VOLTAGE, POWER_LIMIT_MA);
    #endif
    FastLED.setCorrection(LED_CORRECTION);
    FastLED.setTemperature(LED_TEMPERATURE);
    FastLED.setDither(1);
    FastLED.setBrightness(255); // start at full scale; per-mode calls will adjust dynamically
    FastLED.clear();
    FastLED.show();
}

void renderFrame() {
    switch (targetState.mode) {
        case 1: renderMode1(); break;
        case 2: renderMode2(); break;
        case 3: renderMode3(); break;
        case 4: renderMode4(); break;
        case 5: renderMode5(); break;
        default: renderMode4(); break;
    }
    FastLED.show();
}
