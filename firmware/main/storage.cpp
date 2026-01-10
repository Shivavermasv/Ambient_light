// storage.cpp
// Persistent storage for last mode
#include "config.h"
#include <Preferences.h>

Preferences prefs;

void saveLastState(uint8_t mode) {
    prefs.begin("ambient", false);
    prefs.putUChar("last_mode", mode);
    prefs.end();
}

uint8_t loadLastState() {
    prefs.begin("ambient", true);
    uint8_t mode = prefs.getUChar("last_mode", 4);
    prefs.end();
    return mode;
}
