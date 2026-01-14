// state.cpp
// State management for ESP32 Ambient Cove Lighting
#include "config.h"
#include "state.h"
#include <algorithm>

// Global state definitions
TargetState targetState = {};
RenderState renderState = {};

// Packet sequencing and timing
static bool haveFrame = false;
static uint8_t lastFrameId = 0;
static unsigned long lastFrameMs = 0;

// Direction hysteresis
static uint8_t stableDirection = 128;
static uint8_t dirStableCount = 0;

void initState() {
    targetState.mode = static_cast<uint8_t>(FALLBACK_MODE);
    targetState.r = static_cast<uint8_t>(FALLBACK_R);
    targetState.g = static_cast<uint8_t>(FALLBACK_G);
    targetState.b = static_cast<uint8_t>(FALLBACK_B);
    targetState.brightness = static_cast<uint8_t>(FALLBACK_BRIGHTNESS);
    targetState.motion_energy = 0;
    targetState.motion_speed = 0;
    targetState.motion_direction = 128;

    renderState.render_color.r = float(FALLBACK_R);
    renderState.render_color.g = float(FALLBACK_G);
    renderState.render_color.b = float(FALLBACK_B);
    renderState.render_brightness = float(FALLBACK_BRIGHTNESS);
    renderState.render_motion_energy = 0;
    renderState.render_phase = 0;
}

void updateStateFromPacket(const Packet &packet, unsigned long nowMs) {
    // Direction hysteresis: require stability over several packets.
    // motion_direction==0 is treated as "no hint" and ignored.
    if (packet.motion_direction == 0) {
        // keep stableDirection
    } else if (packet.motion_direction != stableDirection) {
        dirStableCount++;
        if (dirStableCount >= 3) {
            stableDirection = packet.motion_direction;
            dirStableCount = 0;
        }
    } else {
        dirStableCount = 0;
    }

    // Frame sequencing and phase timing
    bool resetPhase = false;
    bool skipPhaseAdvance = false;
    uint8_t prevFrame = lastFrameId;
    if (haveFrame) {
        uint8_t expected = uint8_t(prevFrame + 1);
        if (packet.frame_id != expected) {
            resetPhase = true;
            uint8_t gap = static_cast<uint8_t>(packet.frame_id - prevFrame);
            if (gap > 5) {
                skipPhaseAdvance = true; // large gap: don't advance on stale timing
            }
        }
    }

    unsigned long dt_ms = haveFrame ? (nowMs - lastFrameMs) : 40UL;
    if (dt_ms < 5UL) dt_ms = 5UL;
    if (dt_ms > 120UL) { resetPhase = true; dt_ms = 0UL; }
    if (skipPhaseAdvance) dt_ms = 0UL;

    lastFrameId = packet.frame_id;
    lastFrameMs = nowMs;
    haveFrame = true;

    // Apply target with clamping
    targetState.mode = packet.mode;
    targetState.r = std::min(packet.r, static_cast<uint8_t>(MAX_R));
    targetState.g = std::min(packet.g, static_cast<uint8_t>(MAX_G));
    targetState.b = std::min(packet.b, static_cast<uint8_t>(MAX_B));

#if PACKET_BRIGHTNESS_ZERO_IS_NOHINT
    if (packet.brightness == 0 && packet.mode != 5) {
        // keep previous brightness
    } else {
        targetState.brightness = std::min(packet.brightness, static_cast<uint8_t>(BRIGHTNESS_CAP));
    }
#else
    targetState.brightness = std::min(packet.brightness, static_cast<uint8_t>(BRIGHTNESS_CAP));
#endif

    // Laptop often uses 0..180, but allow full 0..255 in case of future tuning.
    targetState.motion_energy = packet.motion_energy;
    targetState.motion_speed = std::min(packet.motion_speed, static_cast<uint8_t>(MOTION_SPEED_CAP));
    targetState.motion_direction = stableDirection;

#if FORCE_MAX_BRIGHTNESS
    if (targetState.mode == FALLBACK_MODE) {
        targetState.brightness = 255;
    }
#endif

    // Direct copy for color/brightness to remove double smoothing
    renderState.render_color = {float(targetState.r), float(targetState.g), float(targetState.b)};
    renderState.render_brightness = float(targetState.brightness);

    // Minimal motion smoothing (<=10 ms effective)
    float motion_alpha = std::min(1.0f, (dt_ms / 10.0f));
    renderState.render_motion_energy += motion_alpha * (targetState.motion_energy - renderState.render_motion_energy);
    if (renderState.render_motion_energy < 1.0f && targetState.motion_energy > 0) {
        renderState.render_motion_energy = 1.0f;
    }

    // Phase is advanced in the main render loop (packet-time driven).
    if (resetPhase) {
        renderState.render_phase = 0.0f;
    }
}

void snapRenderStateToTarget(bool resetPhase) {
    renderState.render_color = {float(targetState.r), float(targetState.g), float(targetState.b)};
    renderState.render_brightness = float(targetState.brightness);
    renderState.render_motion_energy = float(targetState.motion_energy);
    if (resetPhase) {
        renderState.render_phase = 0.0f;
    }
}

void advanceRenderPhase(float dt_s, float packet_dt_s) {
    if (dt_s <= 0.0f) return;
    // Use packet arrival interval as the timing reference.
    // Over one packet interval, total phase advance ~= motion_speed.
    if (packet_dt_s < 0.01f) packet_dt_s = 0.01f;
    if (packet_dt_s > 0.12f) packet_dt_s = 0.12f;
    // Direction is encoded by the laptop as ~32 (left), ~128 (center), ~224 (right).
    // Treat center as neutral (no drift) for stable sync.
    float dir = 0.0f;
    if (targetState.motion_direction == 0) {
        dir = 0.0f;
    } else if (targetState.motion_direction < 96) {
        dir = -1.0f;
    } else if (targetState.motion_direction > 160) {
        dir = 1.0f;
    }
    // Laptop encodes speed as (speed_float * 100) in byte 7.
    float speed = float(targetState.motion_speed) / 100.0f;
    float step = (speed * dir) * (dt_s / packet_dt_s);
    renderState.render_phase += step;
}

void smoothState(float /*dt*/) {
    // Smoothing removed for color/brightness; motion handled in updateStateFromPacket.
}
