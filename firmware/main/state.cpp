// state.cpp
// State management for ESP32 Ambient Cove Lighting
#include "config.h"
#include "state.h"
#include <algorithm>

// Global state definitions
TargetState targetState = {};
RenderState renderState = {};

void initState() {
    targetState = {0, 0, 0, 0, 0, 0, 0, 0};
    renderState = {};
}

void updateStateFromPacket(const Packet &packet) {
    targetState.mode = packet.mode;
    targetState.r = std::min(packet.r, static_cast<uint8_t>(MAX_R));
    targetState.g = std::min(packet.g, static_cast<uint8_t>(MAX_G));
    targetState.b = std::min(packet.b, static_cast<uint8_t>(MAX_B));
    targetState.brightness = std::min(packet.brightness, static_cast<uint8_t>(BRIGHTNESS_CAP));
    targetState.motion_energy = std::min(packet.motion_energy, static_cast<uint8_t>(255));
    targetState.motion_speed = std::min(packet.motion_speed, static_cast<uint8_t>(MOTION_SPEED_CAP));
    targetState.motion_direction = packet.motion_direction;
}

void smoothState(float dt) {
    // EMA smoothing
    float color_alpha = dt / 0.5f; // 500ms
    float bright_alpha = dt / 0.8f; // 800ms
    float motion_alpha = dt / 0.3f; // 300ms
    renderState.render_color.r += color_alpha * (targetState.r - renderState.render_color.r);
    renderState.render_color.g += color_alpha * (targetState.g - renderState.render_color.g);
    renderState.render_color.b += color_alpha * (targetState.b - renderState.render_color.b);
    renderState.render_brightness += bright_alpha * (targetState.brightness - renderState.render_brightness);
    renderState.render_motion_energy += motion_alpha * (targetState.motion_energy - renderState.render_motion_energy);
    // Phase accumulates
    renderState.render_phase += (targetState.motion_speed * (targetState.motion_direction ? 1 : -1)) * dt;
}
