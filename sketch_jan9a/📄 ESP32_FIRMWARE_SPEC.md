📄 ESP32_FIRMWARE_SPEC.md
# ESP32 FIRMWARE SPECIFICATION
## Cinematic Ambient Cove Lighting Renderer (FINAL)

⚠️ IMPORTANT  
This document defines the FINAL and LOCKED firmware behavior for the ESP32-WROOM.
All code generation MUST strictly follow this document.

Copilot:
- DO NOT redesign architecture
- DO NOT simplify packet protocol
- DO NOT move logic between layers
- DO NOT add features not described here
- You MAY refactor for clarity and safety
- You MAY add comments and type safety
- You MAY optimize performance without changing behavior

---

## 1. Hardware & Environment (FIXED)

- MCU: ESP32-WROOM
- Framework: Arduino core for ESP32
- LED strip:
  - Type: WS2812B
  - Voltage: 5V
  - Length: 10 meters
  - Density: 60 LEDs/m
  - Total LEDs: 600
- Power supply: 5V 20A SMPS
- Power injection:
  - Start of strip
  - Start of second 5m strip
  - (Optional) end of strip
- Data resistor: 330Ω
- Common ground mandatory

❌ No microphone  
❌ No HDMI  
❌ No cloud  
❌ No UI on ESP32  

---

## 2. Role of ESP32 (LOCKED)

ESP32 is:
- A **real-time LED renderer**
- A **safety guardian**
- A **fallback controller**

ESP32 MUST NOT:
- Capture audio
- Capture screen
- Perform FFT
- Decide colors autonomously (except Mode 4)

Laptop is the ONLY intelligence source for Modes 1–3.

---

## 3. Operating Modes (LOCKED)

### Mode 1 — Movie Ambient
- Input: Screen color + screen motion energy
- Behavior:
  - Base color from laptop
  - Gentle spatial motion
  - Slow drift
- No flashing
- No beats

### Mode 2 — Music / Work
- Input: Audio motion energy
- Behavior:
  - Ripples from center
  - Directional flow
- Color from palette or slow drift

### Mode 3 — Hybrid
- Input:
  - Color from screen
  - Motion from audio
- Audio NEVER overrides color

### Mode 4 — Ambient Static (LOCAL)
- ESP32-only
- Works when laptop is OFF
- Static color or ultra-slow breathing
- Low brightness
- Power-stable

### Mode 5 — OFF
- LEDs off
- ESP32 still running

---

## 4. Failure & Fallback Rules (CRITICAL)

- Laptop sends UDP packets at ~25 Hz
- ESP32 expects packets continuously
- If NO valid packet for ~1.8 seconds:
  - Fade out current effect
  - Enter Mode 4 automatically
- On ESP32 reboot:
  - Start in Mode 4
  - Transition only after valid packets arrive

Room must NEVER go dark abruptly.

---

## 5. Communication Protocol (LOCKED)

### Transport
- UDP
- Laptop → ESP32
- Port: 4210
- Stateless

### Packet Format (12 bytes)

| Byte | Meaning |
|----|----|
| 0 | Header = 0xAA |
| 1 | Mode (1–5) |
| 2 | Base_R |
| 3 | Base_G |
| 4 | Base_B |
| 5 | Brightness (request only) |
| 6 | Motion Energy |
| 7 | Motion Speed |
| 8 | Motion Direction |
| 9 | Reserved (0x00) |
| 10 | Checksum (XOR bytes 1–9) |
| 11 | Footer = 0x55 |

ESP32 MUST:
- Validate header & footer
- Validate checksum
- Reject invalid packets
- Keep last valid state

---

## 6. Firmware Architecture (LOCKED)

### File Structure



/firmware
├── main.ino
├── config.h
├── network.cpp
├── state.cpp
├── renderer.cpp
├── modes.cpp
└── storage.cpp


Responsibilities MUST remain separated.

---

## 7. Core Execution Model

- Single-core Arduino loop
- Non-blocking
- No delay()-based timing
- Fixed render timestep (~100 Hz)
- UDP handling async

Main loop MUST follow:



handle_udp()
update_state()
if (render_due):
render_frame()


---

## 8. State Model (CRITICAL)

ESP32 maintains TWO states:

### Target State (from packets)


mode
r, g, b
brightness
motion_energy
motion_speed
direction


### Render State (used for LEDs)


render_color
render_brightness
render_motion_energy
render_phase


Render state MUST smoothly approach target state.

---

## 9. Smoothing Rules (LOCKED)

- Color smoothing: EMA, 300–800 ms
- Brightness smoothing: slower than color
- Motion energy smoothing: 200–300 ms
- Motion phase accumulates continuously

NO sudden jumps.

---

## 10. Rendering Model (LOCKED)

### Motion representation
- Phase accumulator
- Velocity derived from motion_energy + motion_speed
- Direction controls sign of phase increment

### LED index model
- Linear strip, indices 0–599
- Logical center at index 299
- Effects must be symmetric

---

## 11. Effect Definitions (LOCKED)

### Mode 1 — Movie Ambient
- Large spatial wavelength
- Gentle sine modulation
- Motion derived from screen delta
- Very low amplitude

### Mode 2 — Music / Work
- Center-origin ripples
- Audio-driven amplitude
- Directional drift layered on top

### Mode 3 — Hybrid
- Same motion as Mode 2
- Color locked to screen

### Mode 4 — Ambient Static
- Fixed color OR ultra-slow breathing
- ESP32-local timer
- No packet dependency

### Mode 5 — OFF
- All LEDs black

---

## 12. Safety Limits (NON-NEGOTIABLE)

ESP32 MUST enforce:

- Absolute brightness cap
- Motion speed cap
- Color clamp:
  - Prevent full white (255,255,255)
  - Maintain cinematic tone
- Watchdog-safe logic

Laptop requests are advisory ONLY.

---

## 13. Boot Sequence (LOCKED)

1. Boot
2. Init Serial
3. Init Wi-Fi
4. Init UDP
5. Init FastLED (LEDs off)
6. Load last saved state
7. Enter Mode 4
8. Wait for packets

---

## 14. Persistent Storage

- Save last mode
- Restore on boot
- If last mode was laptop-driven → start in Mode 4

---

## 15. Logging Requirements

Serial logs MUST include:
- Boot status
- Wi-Fi status
- UDP listening
- Packet reception
- Fallback activation
- Mode transitions

---

## 16. Edge Cases to Handle

- Packet loss
- Malformed packets
- Wi-Fi jitter
- Laptop crash
- Long uptime (no memory leaks)

---

## 17. Development Philosophy

- Deterministic > clever
- Smooth > flashy
- Safety > brightness
- Architecture > hacks

---

## END OF ESP32 FIRMWARE SPEC