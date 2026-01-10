# ESP32 Ambient Cove Lighting Firmware

This firmware implements the FINAL locked specification for the Cinematic Ambient Cove Lighting Renderer on ESP32-WROOM, strictly following the provided protocol and architecture.

## File Structure
- main.ino: Entry point
- config.h: Hardware and global config
- network.cpp: UDP packet handling
- state.cpp / state.h: State management
- renderer.cpp: LED rendering
- modes.cpp: Effect logic
- storage.cpp: Persistent mode storage

## Features
- 5 operating modes
- Strict packet protocol
- Safety and fallback logic
- Smoothing and cinematic effects
- Serial logging

See `ESP32_FIRMWARE_SPEC.md` for full requirements.
