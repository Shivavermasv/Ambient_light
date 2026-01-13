// network.cpp
// Handles UDP packet reception and validation
#include <WiFi.h>
#include <WiFiUdp.h>
#include "config.h"
#include "state.h"

WiFiUDP udp;

void setupWiFi() {
    Serial.println("[WiFi] Connecting...");
    WiFi.mode(WIFI_STA);
    // Disable modem sleep for more reliable UDP receive
    WiFi.setSleep(false);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) {
        delay(200);
        Serial.print(".");
    }
    Serial.println("\n[WiFi] Connected");
    Serial.print("[WiFi] SSID: ");
    Serial.println(WIFI_SSID);
    Serial.print("[WiFi] IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("[WiFi] BSSID: ");
    Serial.println(WiFi.BSSIDstr());
}

void setupUDP() {
    udp.begin(UDP_PORT);
    Serial.printf("[UDP] Listening on port %d\n", UDP_PORT);
}

bool receivePacket(Packet &packet) {
    int packetSize = udp.parsePacket();
    if (packetSize != PACKET_SIZE) return false;
    uint8_t buf[PACKET_SIZE];
    udp.read(buf, PACKET_SIZE);
    // Validate header/footer
    if (buf[0] != 0xAA || buf[11] != 0x55) return false;
    // Validate checksum
    uint8_t checksum = 0;
    for (int i = 1; i <= 9; ++i) checksum ^= buf[i];
    if (buf[10] != checksum) return false;
    // Copy to packet
    packet.mode = buf[1];
    packet.r = buf[2];
    packet.g = buf[3];
    packet.b = buf[4];
    packet.brightness = buf[5];
    packet.motion_energy = buf[6];
    packet.motion_speed = buf[7];
    packet.motion_direction = buf[8];
    packet.frame_id = buf[9];
    return true;
}
