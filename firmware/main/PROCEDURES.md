# ESP32 Ambient Lighting Firmware – Procedures and How They Work

## Networking
- **Wi-Fi Station Setup**: `setupWiFi()` (network.cpp) connects to the configured SSID/PASS, disables modem sleep for reliable UDP, and reports IP/BSSID.
- **UDP Listener**: `setupUDP()` binds to `UDP_PORT` (4210). `receivePacket()` enforces packet size (12 bytes), header/footer (0xAA/0x55), XOR checksum (bytes 1–9), then extracts mode, RGB, brightness, motion_energy, motion_speed, motion_direction.

## State Management
- **Structures**: `TargetState` holds desired values; `RenderState` holds smoothed values (color, brightness, motion, phase).
- **Initialization**: `initState()` seeds both states with fallback Mode 4 ambient values.
- **Packet Application**: `updateStateFromPacket()` clamps RGB to MAX_R/G/B and brightness to BRIGHTNESS_CAP; motion values are clamped to caps. With `FORCE_MAX_BRIGHTNESS`, brightness is forced to 255 regardless of packet.
- **Smoothing**: `smoothState(dt)` applies EMA with fast time constants (~20–30 ms) for color/brightness/motion to improve sync. Phase accumulates using motion_speed and motion_direction. A small floor keeps motion responsive.

## Rendering Pipeline
- **LED Setup**: `setupLEDs()` initializes FastLED on `LED_PIN` with `LED_TYPE`/`COLOR_ORDER`, sets max power (`POWER_LIMIT_MA` unless `DISABLE_POWER_LIMIT`), applies `UncorrectedColor` for maximum brightness, enables dithering, and starts at full brightness (255).
- **Frame Render**: `renderFrame()` picks a mode and calls `renderMode1..5`, then FastLED.show().

### Modes
- **Mode 1 (Gentle sine)**: Large-wavelength sine modulation, boosted base (1.12×) and modulation depth; brightness uses `BRIGHTNESS_GAIN` with a higher floor for visibility.
- **Mode 2 (Ripples)**: Center ripples with stronger motion amplitude (0.75×) and higher base (1.15×); brightness boosted with floor. Mode 3 reuses Mode 2.
- **Mode 4 (Ambient fallback)**: Slow breath around current render_color; brightness floored and forced to 255 when `FORCE_MAX_BRIGHTNESS` is on.
- **Mode 5 (Off)**: All LEDs black, brightness 0.

## Main Loop Timing
- **Loop Cadence**: `renderInterval` ~8 ms (~125 Hz). `update_state(dt)` uses real delta time per loop for smoothing. Fallback triggers after ~1.8 s of no packets, forcing Mode 4 with ambient values.

## Safety and Power
- **Power Budget**: Default `POWER_LIMIT_MA` 20,000 (20A). Optional `DISABLE_POWER_LIMIT` to uncap (use only with adequate PSU and power injection). FastLED enforces this per frame.
- **Brightness**: `BRIGHTNESS_CAP` 255; `BRIGHTNESS_GAIN` 1.35×; `FORCE_MAX_BRIGHTNESS` forces brightness to 255 globally. MAX_R/G/B are 255.

## Diagnostics
- **Serial Debug**: Periodic UDP packet print (mode, RGB, brightness, motion) every 500 ms when packets are received. Wi-Fi connection info printed at boot. Fallback logging when packets stop.

## Fallback Behavior
- After 1.8 s without valid packets, the system enters Mode 4 (ambient), sets target state to the fallback color/brightness, keeps listening for UDP, and resumes packet-driven modes upon next valid packet.
