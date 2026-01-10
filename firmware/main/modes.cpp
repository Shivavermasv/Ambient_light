// modes.cpp
// Effect implementations for each mode
#include "config.h"
#include <algorithm>
#include "state.h"
#include <FastLED.h>
extern CRGB leds[NUM_LEDS];

void renderMode1() {
    // Gentle sine modulation, large wavelength
    float phase = renderState.render_phase;
    for (int i = 0; i < NUM_LEDS; ++i) {
        float x = (i - NUM_LEDS/2) / 80.0f;
        float mod = 0.1f * sinf(x + phase);
        leds[i] = CRGB(
            fl::clamp(renderState.render_color.r * (1.0f + mod), 0.0f, float(MAX_R)),
            fl::clamp(renderState.render_color.g * (1.0f + mod), 0.0f, float(MAX_G)),
            fl::clamp(renderState.render_color.b * (1.0f + mod), 0.0f, float(MAX_B))
        );
    }
    FastLED.setBrightness(renderState.render_brightness);
}

void renderMode2() {
    // Center-origin ripples, directional drift
    float phase = renderState.render_phase;
    for (int i = 0; i < NUM_LEDS; ++i) {
        float dist = abs(i - NUM_LEDS/2) / 30.0f;
        float ripple = sinf(dist - phase) * renderState.render_motion_energy / 255.0f;
        leds[i] = CRGB(
            fl::clamp(renderState.render_color.r * (0.7f + ripple), 0.0f, float(MAX_R)),
            fl::clamp(renderState.render_color.g * (0.7f + ripple), 0.0f, float(MAX_G)),
            fl::clamp(renderState.render_color.b * (0.7f + ripple), 0.0f, float(MAX_B))
        );
    }
    FastLED.setBrightness(renderState.render_brightness);
}

void renderMode3() {
    // Hybrid: Mode 2 motion, Mode 1 color
    renderMode2();
}
void renderMode4() {
    static float t = 0;
    t += 0.001f;
    float breath = 0.95f + 0.05f * sinf(t);
    for (int i = 0; i < NUM_LEDS; ++i) {
        leds[i] = CRGB(
            fl::clamp(renderState.render_color.r * breath, 0.0f, float(MAX_R)),
            fl::clamp(renderState.render_color.g * breath, 0.0f, float(MAX_G)),
            fl::clamp(renderState.render_color.b * breath, 0.0f, float(MAX_B))
        );
    }
    FastLED.setBrightness(renderState.render_brightness * 0.3f);
}

void renderMode5() {
    // OFF
    for (int i = 0; i < NUM_LEDS; ++i) leds[i] = CRGB::Black;
    FastLED.setBrightness(0);
}


