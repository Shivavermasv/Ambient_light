// main.ino
// Entry point for ESP32 Ambient Cove Lighting
#include "config.h"
#include "network.h"
#include "state.h"
#include "renderer.h"
#include "modes.h"
#include "storage.h"

static unsigned long lastPacketTimeMs = 0;
static unsigned long lastPacketMs = 0;
static float lastPacketDtS = 0.040f;
static bool havePacket = false;

static unsigned long lastRenderMs = 0;
static unsigned long lastStateMs = 0;
static const unsigned long renderIntervalMs = 8; // ~125Hz for faster response

static bool fallbackActive = false;

void setup() {
    Serial.begin(SERIAL_BAUD);
    Serial.println("[BOOT] ESP32 Ambient Cove Lighting");
    setupWiFi();
    setupUDP();
    setupLEDs();
    initState();
    lastStateMs = millis();
    lastRenderMs = lastStateMs;
    lastPacketTimeMs = lastStateMs;
    Serial.println("[INIT] Entering Mode 4");
}

void loop() {
    unsigned long nowMs = millis();
    handle_udp();

    float dtState = (nowMs - lastStateMs) / 1000.0f;
    if (dtState < 0.0f) dtState = 0.0f;
    update_state(dtState);
    lastStateMs = nowMs;

    if (nowMs - lastRenderMs >= renderIntervalMs) {
        float dtRender = (nowMs - lastRenderMs) / 1000.0f;
        if (dtRender < 0.0f) dtRender = 0.0f;
        // Packet-time driven animation
        advanceRenderPhase(dtRender, lastPacketDtS);
        renderFrame();
        lastRenderMs = nowMs;
    }
}

void handle_udp() {
    Packet packet;
    if (receivePacket(packet)) {
        unsigned long nowMs = millis();

        if (havePacket) {
            unsigned long dtMs = nowMs - lastPacketMs;
            if (dtMs < 5UL) dtMs = 5UL;
            if (dtMs > 120UL) dtMs = 120UL;
            lastPacketDtS = dtMs / 1000.0f;
        } else {
            lastPacketDtS = 0.040f;
        }
        lastPacketMs = nowMs;
        havePacket = true;

        updateStateFromPacket(packet, nowMs);
        if (fallbackActive) {
            // Snap immediately on resume for clean sync.
            snapRenderStateToTarget(true);
            fallbackActive = false;
        }
        lastPacketTimeMs = nowMs;
        static unsigned long lastDbg = 0;
        if (nowMs - lastDbg > 500) {
            Serial.printf("[UDP] mode=%u fid=%u rgb=%u,%u,%u bright=%u motionE=%u speed=%u dir=%u pktDt=%.3f\n",
                          packet.mode, packet.frame_id,
                          packet.r, packet.g, packet.b,
                          packet.brightness, packet.motion_energy, packet.motion_speed, packet.motion_direction,
                          lastPacketDtS);
            lastDbg = nowMs;
        }
    } else if (millis() - lastPacketTimeMs > 1800) {
        // Fallback to Mode 4 with safe ambient defaults
        if (!fallbackActive) {
        targetState.mode = FALLBACK_MODE;
        targetState.r = static_cast<uint8_t>(FALLBACK_R);
        targetState.g = static_cast<uint8_t>(FALLBACK_G);
        targetState.b = static_cast<uint8_t>(FALLBACK_B);
        targetState.brightness = static_cast<uint8_t>(FALLBACK_BRIGHTNESS);
#if FORCE_MAX_BRIGHTNESS
        targetState.brightness = 255;
#endif
        targetState.motion_energy = 0;
        targetState.motion_speed = 0;
        targetState.motion_direction = 128;

        snapRenderStateToTarget(true);
        Serial.println("[FALLBACK] No packet, Mode 4 ambient");
        fallbackActive = true;

        havePacket = false;
        lastPacketDtS = 0.040f;
        }
    }
}

void update_state(float dt) {
    smoothState(dt);
}
