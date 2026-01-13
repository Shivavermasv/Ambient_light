// config.h
// Hardware and global configuration for ESP32 Ambient Cove Lighting
#pragma once

#define LED_PIN        5
#define LED_TYPE       WS2812B
#define COLOR_ORDER    GRB
#define NUM_LEDS       600
#define BRIGHTNESS_CAP 255
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

// Treat packet brightness=0 as "no hint" (prevents accidental forced blackout).
// 0 = always apply packet brightness (including 0)
// 1 = ignore 0, keep last brightness
#ifndef PACKET_BRIGHTNESS_ZERO_IS_NOHINT
#define PACKET_BRIGHTNESS_ZERO_IS_NOHINT 1
#endif

// FastLED power limiting. Disable only if you have sufficient power injection.
#ifndef ENABLE_POWER_LIMIT
#define ENABLE_POWER_LIMIT 1
#endif
#ifndef POWER_LIMIT_VOLTS
#define POWER_LIMIT_VOLTS 5
#endif
#ifndef POWER_LIMIT_MA
#define POWER_LIMIT_MA 40000
#endif

// Back-compat macros used by renderer.cpp
#ifndef LED_VOLTAGE
#define LED_VOLTAGE POWER_LIMIT_VOLTS
#endif

#ifndef DISABLE_POWER_LIMIT
#if ENABLE_POWER_LIMIT
#define DISABLE_POWER_LIMIT 0
#else
#define DISABLE_POWER_LIMIT 1
#endif
#endif
