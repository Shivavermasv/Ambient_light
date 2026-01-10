// config.h
// Hardware and global configuration for ESP32 Ambient Cove Lighting
#pragma once

#define LED_PIN        5
#define LED_TYPE       WS2812B
#define COLOR_ORDER    GRB
#define NUM_LEDS       600
#define BRIGHTNESS_CAP 180
#define MOTION_SPEED_CAP 255
#define UDP_PORT       4210
#define PACKET_SIZE    12
#define WIFI_SSID      "TP-Link_5ACC"
#define WIFI_PASS      "986678sv"
#define SERIAL_BAUD    115200
#define STATE_SAVE_FILE "/mode.dat"

// Safety color clamp
#define MAX_R 220
#define MAX_G 220
#define MAX_B 220
