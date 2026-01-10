# PROJECT SPECIFICATION
## ESP32 Cinematic Ambient Cove Lighting (Laptop-Driven)

IMPORTANT:
This document defines the FINAL and LOCKED design of the project.
All implementation must follow this exactly unless explicitly stated as tunable.

Copilot rules:
- Do NOT redesign architecture
- Do NOT simplify algorithms
- Do NOT remove safety or fallback logic
- You MAY refactor code structure for cleanliness
- You MAY suggest micro-optimizations that preserve behavior

---

## 1. Project Overview

Build a cinematic ambient LED cove lighting system where:
- A laptop captures system audio (NOT microphone)
- A laptop captures screen content (NOT HDMI edge mirroring)
- Laptop computes semantic lighting parameters
- ESP32-WROOM renders LEDs
- LEDs are placed in room cove (indirect lighting)

Goal: immersion, not flashy RGB effects.

---

## 2. Hardware Constraints (Fixed)

- Controller: ESP32-WROOM
- LEDs: WS2812B
- Length: 10 meters
- Density: 60 LEDs/m
- Total LEDs: 600
- Power supply: 5 V, 20 A SMPS
- Power injection:
  - Start of strip
  - Start of second 5 m strip
  - Optional end injection

No microphone
No HDMI capture
No cloud
No mobile app

---

## 3. High-Level Architecture (LOCKED)

Laptop = Intelligence + Analysis + Control
ESP32 = Renderer + Safety Guardian + Fallback

Laptop is authoritative.
ESP32 is intentionally dumb and never analyzes audio or screen.

---

## 4. Operating Modes (LOCKED)

Mode 1 — Movie Ambient (Screen + Motion)
- Base color from screen weighted mean
- Motion from screen color delta
- Smooth, cinematic, non-distracting

Mode 2 — Music / Work (Audio Reactive)
- Color from fixed palette or slow drift
- Motion from FFT bass energy
- No strobe, no color jumping

Mode 3 — Hybrid (Screen + Audio)
- Base color from screen
- Motion from audio FFT
- Audio never overrides color

Mode 4 — Ambient Static (ESP32 Local)
- Works when laptop is OFF
- Static color or ultra-slow breathing
- Low power

Mode 5 — OFF
- LEDs off
- ESP32 reachable

---

## 5. Failure & Fallback Rules (CRITICAL)

- UDP packets at ~25 Hz
- If no valid packet for ~1.8 seconds:
  - Fade out
  - Enter Mode 4
- On ESP32 reboot:
  - Start in Mode 4
  - Switch only when packets resume

---

## 6. Communication Protocol (LOCKED)

Transport: UDP
Direction: Laptop -> ESP32
Port: 4210

Packet format (12 bytes):

0: Header = 0xAA
1: Mode (1-5)
2: Base_R
3: Base_G
4: Base_B
5: Brightness (request only)
6: MotionEnergy
7: MotionSpeed
8: Direction
9: Reserved = 0x00
10: Checksum (XOR bytes 1-9)
11: Footer = 0x55

ESP32 validates header, footer, checksum and clamps brightness/motion.

---

## 7. Laptop Technology Stack

Language: Python 3.10+

Libraries:
- mss
- numpy
- sounddevice
- scipy
- socket
- threading
- time

---

## 8. Laptop Application Structure

ambient_lighting/
main.py
config.py
mode_manager.py
packet_builder.py
udp_sender.py
signal_processing.py
utils.py
screen/screen_sampler.py
audio/audio_fft.py
requirements.txt

---

## 9. Screen Processing Algorithm (LOCKED)

Capture full screen
Downscale to 64x36
Crop top 7%, bottom 13%

Weighted mean:
Ignore pixels if V > 0.92 or S < 0.08

weight = S * (1 - V)^1.5

Final color = weighted average
Desaturate 12%
Smooth 600 ms EMA

---

## 10. Screen Motion Energy

delta = |R - R_prev| + |G - G_prev| + |B - B_prev|
motion_energy = clamp(delta * 0.8, 0, 180)
Smooth 250 ms

---

## 11. Audio Processing (FFT LOCKED)

System audio loopback
Sample rate: 44.1 kHz
Buffer: 2048 samples

Bands:
Low: 20-150 Hz
Mid: 150-2000 Hz

audio_energy = 0.7*low + 0.3*mid
Smooth 100 ms
Output range 0-200

---

## 12. Motion Mapping

Non-linear mapping (sqrt)
Speed range: 0.15 to 1.2
Direction fixed or ultra-slow drift

---

## 13. Brightness Requests

Mode 1: 70-90
Mode 2: 90-120
Mode 3: 80-100
Laptop absolute cap: 120
ESP32 enforces final limit

---

## 14. ESP32 Rendering Expectations

FastLED
Target vs render state
Smooth interpolation
Phase-based motion
Center ripples
No sharp transitions

---

## 15. Edge Cases

Audio unavailable -> zero motion
Screen failure -> reuse last color
Laptop crash -> ESP32 fallback
Packet loss -> harmless
Wi-Fi jitter -> harmless

---

## 16. Development Philosophy

Correct > clever
Deterministic > reactive
Smooth > flashy
Safety > brightness
Architecture > hacks

---

END OF SPEC
