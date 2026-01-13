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
        float mod = 0.18f * sinf(x + phase);
        leds[i] = CRGB(
            fl::clamp(renderState.render_color.r * (1.12f + mod), 0.0f, float(MAX_R)),
            fl::clamp(renderState.render_color.g * (1.12f + mod), 0.0f, float(MAX_G)),
            fl::clamp(renderState.render_color.b * (1.12f + mod), 0.0f, float(MAX_B))
        );
    }
    float b = renderState.render_brightness;
#if !STRICT_PACKET_BRIGHTNESS
    b = b * BRIGHTNESS_GAIN;
    if (b < 96.0f) b = 96.0f; // higher floor for visibility
#endif
    FastLED.setBrightness((uint8_t)std::min(255.0f, std::max(0.0f, b)));
}

void renderMode2() {
    // Center-origin ripples, directional drift
    float phase = renderState.render_phase;
    for (int i = 0; i < NUM_LEDS; ++i) {
        float dist = abs(i - NUM_LEDS/2) / 30.0f;
        float motion = renderState.render_motion_energy;
        float ripple_amp = 0.75f * (motion / 180.0f); // motion_energy is 0..180 from laptop
        float ripple = ripple_amp * sinf(dist - phase);
        leds[i] = CRGB(
            fl::clamp(renderState.render_color.r * (1.15f + ripple), 0.0f, float(MAX_R)),
            fl::clamp(renderState.render_color.g * (1.15f + ripple), 0.0f, float(MAX_G)),
            fl::clamp(renderState.render_color.b * (1.15f + ripple), 0.0f, float(MAX_B))
        );
    }
    float b = renderState.render_brightness;
#if !STRICT_PACKET_BRIGHTNESS
    b = b * BRIGHTNESS_GAIN * 1.10f;
    if (b < 110.0f) b = 110.0f;
#endif
    FastLED.setBrightness((uint8_t)std::min(255.0f, std::max(0.0f, b)));
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
    float b = renderState.render_brightness;
#if !STRICT_PACKET_BRIGHTNESS
    if (b < 110.0f) b = 110.0f;
#endif
#if FORCE_MAX_BRIGHTNESS
    b = 255.0f;
#endif
    FastLED.setBrightness((uint8_t)std::min(255.0f, std::max(0.0f, b)));
}

void renderMode5() {
    // OFF
    for (int i = 0; i < NUM_LEDS; ++i) leds[i] = CRGB::Black;
    FastLED.setBrightness(0);
}


