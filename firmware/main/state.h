// state.h
// State structures for ESP32 Ambient Cove Lighting
#pragma once
#ifndef STATE_H
#define STATE_H
#include <cstdint>

struct Packet {
    uint8_t mode;
    uint8_t r, g, b;
    uint8_t brightness;
    uint8_t motion_energy;
    uint8_t motion_speed;
    uint8_t motion_direction;
};

struct TargetState {
    uint8_t mode;
    uint8_t r, g, b;
    uint8_t brightness;
    uint8_t motion_energy;
    uint8_t motion_speed;
    uint8_t motion_direction;
};

struct RenderColor {
    float r, g, b;
};

struct RenderState {
    RenderColor render_color;
    float render_brightness;
    float render_motion_energy;
    float render_phase;
};

extern TargetState targetState;
extern RenderState renderState;

void initState();
void updateStateFromPacket(const Packet &packet);
void smoothState(float dt);
#endif // STATE_H
