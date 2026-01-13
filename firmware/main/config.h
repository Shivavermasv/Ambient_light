// config.h
// Hardware and global configuration for ESP32 Ambient Cove Lighting
#pragma once

#define LED_PIN        5
#define LED_TYPE       WS2812B
#define COLOR_ORDER    GRB
#define NUM_LEDS       600  // full strip length

// Power budgeting (FastLED will throttle to stay within this)
#define LED_VOLTAGE    5
#define POWER_LIMIT_MA 40000  // dual 20A supplies
#define DISABLE_POWER_LIMIT 0 // set to 1 to uncap (use only if PSU/injection can handle >40A)

#define BRIGHTNESS_CAP 255  // maximum output (0-255); power limiting still active
#define BRIGHTNESS_GAIN 1.35f // global gain applied in modes to boost perceived brightness

// When enabled, the firmware applies packet brightness exactly (no gain, no minimum floors).
// This is the closest possible "perfect sync" with the laptop-side brightness values.
#define STRICT_PACKET_BRIGHTNESS 1

// Force maximum output (ignores packet brightness). Power limiting still applies.
#define FORCE_MAX_BRIGHTNESS 0
#define MOTION_SPEED_CAP 255
#define UDP_PORT       4210
#define PACKET_SIZE    12
#define WIFI_SSID      "TP-Link_5ACC"
#define WIFI_PASS      "986678sv"
#define SERIAL_BAUD    115200
#define STATE_SAVE_FILE "/mode.dat"

// Safety color clamp
#define MAX_R 255
#define MAX_G 255
#define MAX_B 255

// Fallback (Mode 4) defaults when no packets arrive
#define FALLBACK_MODE        4
#define FALLBACK_R           200
#define FALLBACK_G           120
#define FALLBACK_B           40
#define FALLBACK_BRIGHTNESS  255  // MUST be 0-255 (uint8)
