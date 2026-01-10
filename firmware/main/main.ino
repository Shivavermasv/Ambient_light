// main.ino
// Entry point for ESP32 Ambient Cove Lighting
#include "config.h"
#include "network.h"
#include "state.h"
#include "renderer.h"
#include "modes.h"
#include "storage.h"

unsigned long lastPacketTime = 0;
unsigned long lastRenderTime = 0;
const unsigned long renderInterval = 10; // ~100Hz

void setup() {
    Serial.begin(SERIAL_BAUD);
    Serial.println("[BOOT] ESP32 Ambient Cove Lighting");
    setupWiFi();
    setupUDP();
    setupLEDs();
    initState();
    Serial.println("[INIT] Entering Mode 4");
}

void loop() {
    handle_udp();
    update_state();
    if (millis() - lastRenderTime >= renderInterval) {
        renderFrame();
        lastRenderTime = millis();
    }
}

void handle_udp() {
    Packet packet;
    if (receivePacket(packet)) {
        updateStateFromPacket(packet);
        lastPacketTime = millis();
        Serial.println("[UDP] Packet received");
    } else if (millis() - lastPacketTime > 1800) {
        // Fallback to Mode 4
        targetState.mode = 4;
        Serial.println("[FALLBACK] No packet, Mode 4");
    }
}

void update_state() {
    float dt = renderInterval / 1000.0f;
    smoothState(dt);
}
