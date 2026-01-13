# Mode Algorithms & Tunables (Current Implementation)

This document describes **what the laptop app currently does** for each mode, including the **algorithms** and the **values/tunables** in use.

Source of truth (code):
- `ambient_lighting/config.py`
- `ambient_lighting/mode_manager.py`
- `ambient_lighting/screen/screen_sampler.py`
- `ambient_lighting/audio/audio_fft.py`
- `ambient_lighting/main_desktop.py`

Spec reference: `PROJECT_SPEC.md` (some values below are intentionally tuned beyond the original spec ranges).

---

## Shared: UDP packet protocol

Transport: UDP to `Config.udp_ip`:`Config.udp_port` (currently `192.168.0.100:4210`)

Packet format (12 bytes) from `ambient_lighting/packet_builder.py`:

- Byte 0: `0xAA` header
- Byte 1: `mode` (1–5)
- Byte 2–4: `base_color` as RGB (0–255)
- Byte 5: `brightness` request (0–`led_brightness_cap`)
- Byte 6: `motion_energy` (0–180)
- Byte 7: `motion_speed * 100` (0–255)
- Byte 8: `direction` (0–255)
- Byte 9: `frame_id` (0–255 wrap)
- Byte 10: XOR checksum of bytes 1–9
- Byte 11: `0x55` footer

Send rate: ~25 Hz (`udp_rate_hz = 25`, threads sleep ~0.04s)

---

## Shared: Screen color algorithm (used by Modes 1 & 3)

Implemented in `ambient_lighting/screen/screen_sampler.py` + `main_desktop.py` screen thread.

1) Capture full screen via `mss`.
2) Downscale to **64×36** (`screen_downscale`).
3) Crop: top **7%**, bottom **13%** (`screen_crop_top`, `screen_crop_bottom`).
4) Convert to HSV.
5) Mask out pixels if **V > 0.92** or **S < 0.08**.
6) Weight each pixel:

$$w = S \cdot (1 - V)^{1.5}$$

7) Weighted mean of RGB using those weights.
8) Optional dark-scene boost (currently **enabled**):
   - threshold `dark_boost_v_thresh = 0.25`
   - strength `dark_boost_strength = 0.15`
9) Desaturate:
   - default **12%** (unless `enable_desat_reduction=True`, then uses `desat_amount=0.10`)
10) Smooth color with EMA:
   - base sampler EMA: `screen_ema_ms = 600`
  - no additional mode-specific color EMA (removed/disabled to reduce latency)

### Spatial bias (screen) + direction hint
If `enable_spatial_bias=True` (currently **enabled**) and mode is not 2:
- Compute weighted mean color in `spatial_regions = 3` horizontal regions (left/center/right)
- Pick the region with max weight sum
- Blend its color into final base color with `spatial_bias_blend = 0.35`
- Set `direction` hint based on dominant region:
  - left → 32
  - center → 128
  - right → 224

Direction hysteresis:
- Direction changes only after the same dominant region is observed for **3 consecutive frames**.

---

## Shared: Screen motion energy (used by Mode 1)

Computed in `main_desktop.py` screen thread:

- Compute per-frame delta:

$$\Delta = |R - R_{prev}| + |G - G_{prev}| + |B - B_{prev}|$$

- Scale + clamp:

$$motion = clamp(\Delta \cdot 0.8, 0, 180)$$

- Smooth with a mode-specific EMA:
- Smooth with a single EMA (~180ms total) in the screen thread.

---

## Shared: Audio FFT features (used by Modes 2 & 3)

Implemented in `ambient_lighting/audio/audio_fft.py`.

- Sample rate: `audio_sample_rate = 44100`
- Buffer size: `audio_buffer_size = 2048`
- Reads audio via `sounddevice.InputStream` callback when possible.
- On Windows, if the user selects a Stereo Mix device that cannot be opened (commonly WDM-KS), it falls back to system-audio loopback using the `soundcard` library (loopback microphone on default speakers).

FFT per block:
- Low band: **20–150 Hz** (sum of magnitudes)
- Mid band: **150–2000 Hz** (sum of magnitudes)
- Spectral centroid computed from full spectrum

Raw energy (pre-normalization):

$$energy\_raw = 0.7 \cdot low + 0.3 \cdot mid$$

Normalization + gating:
- Tracks a decaying peak: `_peak_energy = max(_peak_energy*0.99, energy_raw)`
- Normalized energy:

$$energy = clamp( energy\_raw / peak \cdot target, 0, hard\_cap )$$

Where:
- `audio_target_level = 160`
- `audio_hard_cap = 190`

Noise gate:
- If `energy <= audio_noise_gate` for longer than `audio_noise_gate_hold_s`, energy is forced to 0.
- `audio_noise_gate = 4.0`
- `audio_noise_gate_hold_s = 2.0`

Smoothing:
- Attack smoothing uses `audio_ema_ms = 100`
- Release smoothing uses `audio_release_ms = 700`

Outputs written into shared state:
- `audio_motion_energy` (the normalized + smoothed energy)
- `audio_bass` (raw low-band sum)
- `audio_mid` (raw mid-band sum)
- `audio_centroid` (Hz)

---

## Shared: Motion speed mapping (all modes)

Implemented in `ambient_lighting/mode_manager.py`:

- Motion speed is computed from motion energy using sqrt mapping:

$$speed = 0.15 + (1.2 - 0.15) \cdot \sqrt{clamp(motion/180, 0, 1)}$$

- If motion energy is 0, speed is forced to **0.15** (floor).
- If motion energy is 0, speed is forced to **0.0** (true stop).
- Extra safety: ramp-limit speed changes:
  - general: `motion_speed_ramp_per_s = 2.5`
  - audio modes: `audio_motion_speed_ramp_per_s = 0.8`

Audio speed cap:
- For modes 2/3: `audio_motion_speed_cap = 0.65`

---

## Mode 1 — Movie Ambient (Screen + Motion)

**Color source:** screen (weighted mean + EMA), with optional spatial bias.

**Motion source:** screen motion energy (delta of RGB).

**Beat accent:** optional and currently disabled by default:
- `enable_soft_beat_accent = False`
- Trigger: if `motion_energy > (1 + motion_jump_threshold) * last_motion_energy`
  - `motion_jump_threshold = 0.30` (30% jump)
- Effect duration: `motion_bump_ms = 300`
- Speed bump: add `motion_bump_speed_cap = 0.15` (clamped)

**Brightness:** midpoint of tuned range:
- Mode 1 range: `brightness_ranges[1] = (85, 110)` → midpoint ~97

---

## Mode 2 — Music / Work (Audio Reactive)

**Color source:** audio-driven HSV mapping in `_audio_color()`.

- Hue from centroid: warm→cool range
  - centroid normalized between `audio_centroid_low_hz = 200` and `audio_centroid_high_hz = 4000`
  - hue from 20° to 220°
- Saturation from energy with floor/ceiling:
  - `sat = clamp(energy/160, 0.08, 0.9)`
- Value from energy (gentle):
  - `val = 0.55 + 0.35 * clamp(energy/140, 0, 1)`
- Silence protection:
  - if `energy < 2.0`, reuse the last audio color.

**Motion source:** `audio_motion_energy` (normalized energy), then extra gating/smoothing:
- Gate: if `motion_energy < audio_motion_gate`, set to 0
  - `audio_motion_gate = 4.0`
- No extra laptop-side smoothing beyond the FFT attack/release smoothing in `AudioFFT`.
- Speed cap: `audio_motion_speed_cap = 0.65`

**Brightness:** tuned range midpoint + optional “brightness float”:
- Base range: `brightness_ranges[2] = (115, 120)`
- `enable_audio_brightness_float = True`
  - float range: `audio_brightness_float_range = 10`
  - smoothing alpha: `audio_brightness_float_alpha = 0.2`

**Optional hue bias:** enabled
- `enable_audio_hue_bias = True`
- `audio_hue_bias_degrees = 8`

---

## Mode 3 — Hybrid (Screen + Audio Motion)

**Color source:** screen (same as Mode 1). Audio does not override base color.

**Motion source:** audio energy (same audio gating/smoothing path as Mode 2).

**Brightness:** tuned range midpoint:
- Mode 3 range: `brightness_ranges[3] = (95, 120)`

---

## Mode 4 — Ambient Static (ESP32 Local fallback)

Laptop side:
- Forces base color to `mode4_static_color = [255, 180, 80]` (bright amber)
- Brightness midpoint from fixed range (inside `ModeManager`): 90–100 → midpoint 95
- Optional drift disabled by default:
  - `enable_mode4_drift = False`
  - if enabled: amplitude 5, period 25s

---

## Mode 5 — OFF

Laptop requests brightness 0; color/motion effectively ignored.

---

## Notes (important)

- Several brightness ranges are **higher than the original spec** (tuned for visibility).
- For audio modes, there is a **noise gate + release** path intended to reduce flicker, but if your audio device reports noise even in silence, it can still create motion/color flutter.
- Brightness output is quantized: updated only every **3 frames** to reduce shimmer.
