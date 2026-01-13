# Change Summary

- Startup fallback no longer forces the app into mode 4 immediately; fallback still triggers after >1.8s of no packets but is non-sticky. (mode_manager.py)
- Audio FFT now uses an auto-gain peak tracker to normalize motion energy for quiet loopback sources. Legacy fixed divisor `energy_raw / 1e5` is noted in code for rollback. (audio/audio_fft.py)

Tweaks implemented (all toggleable in config.py; old values noted in comments):
- Mode-aware motion smoothing (ms): mode1 250, mode2 190, mode3 220. (main_desktop.py)
- Additional color EMA overlay: mode1 480ms, mode3 600ms; sampler still at 600ms. (main_desktop.py)
- Soft beat accent: +0.15 motion_speed bump for >30% motion jump over 300ms, capped; can disable. (mode_manager.py)
- Brightness comfort: optional night-cap 90 and optional mode4 slow drift (±5 over ~25s). (mode_manager.py)
- Audio robustness: normalize toward 160 with hard-cap 190; noise gate <2 with 1.5s hold. (audio/audio_fft.py)
- Direction drift (idle only) toggle; disabled by default. (mode_manager.py)

New Mode 2 audio musicality (toggleable):
- Audio features (energy, bass, mid, centroid) exposed with release smoothing; legacy get_audio_energy kept. (audio/audio_fft.py, main_desktop.py)
- Brightness float in Mode 2 (±10 around midpoint, smoothed) driven by motion energy. (mode_manager.py, config.py)
- Hue bias in Mode 2 from spectral centroid (±8° warm/cool nudge), base color preserved elsewhere. (mode_manager.py, config.py)
- Config toggles for audio enhancements, centroid bounds, brightness float strength. (config.py)

Latest fixes for Mode 2/3 stability:
- Audio gate tightened (5.0) with longer hold (2.5s) and release 700ms; stricter motion gate (6.0) and faster decay (0.70) to drive motion to zero on silence. (config.py, mode_manager.py)
- Beat accent now only applies to Mode 1 to avoid extra jitter in audio modes. (mode_manager.py)
- Mode 4 now forces bright amber color [255,180,80] with higher brightness midpoint (90–100). (config.py, mode_manager.py)

Color and mode refinements (latest):
- Screen sampler allows configurable desat and dark-scene boost (enabled, V<0.25) to improve saturation in dark content. (screen/screen_sampler.py, main_desktop.py, config.py)
- Audio handling tuned: gate 4.0, motion gate 4.0, decay 0.60, smooth 250ms, release 700ms, silence hold 1.2s; minimal motion restored when audio present but gated to zero. Motion speed clamps to 0.15 when silent. (config.py, mode_manager.py)
- Faster screen response: color EMA Mode1 360ms, Mode3 520ms; motion smoothing Mode1 200ms, Mode3 200ms. (config.py)
- Spatial bias (no protocol change): sample left/center/right, blend dominant region color (35%) into base color, and set a direction hint for ESP32; firmware unchanged. (screen/screen_sampler.py, main_desktop.py, config.py)
- Mode 2 now uses audio-driven color (spectral centroid → hue, energy → saturation) and no longer depends on screen color; screen thread skips color writes in Mode 2. (mode_manager.py, main_desktop.py)
- Raised brightness ranges: Mode1 85–110, Mode2 115–120, Mode3 95–120 (ESP cap 120). (config.py)

Stability + regression fixes (latest):
- WASAPI loopback detection fixed (uses host API name containing "WASAPI"), and channel selection is now safe for output-loopback devices (in=0/out>0). (ambient_lighting/audio/audio_fft.py)
- Audio stream init now auto-retries if it failed once (prevents Mode 2 getting stuck at zero forever when a device can’t open). (ambient_lighting/audio/audio_fft.py)
- Audio capture switched to callback mode (instead of blocking `.read()`), with init retries for device default sample rate/blocksize and FFT length derived from actual frame size. (ambient_lighting/audio/audio_fft.py)
- Audio thread forces re-init if `AudioFFT.stream` is `None` after init, instead of continuing to read zeros silently. (ambient_lighting/main_desktop.py)
- GUI auto-selects a sensible default audio device: prefers WASAPI output loopback only when supported by the installed `sounddevice`; otherwise prefers stable input devices (DirectSound/MME) to avoid “no audio” Mode 2. (ambient_lighting/main_desktop.py)
- Status line now shows audio energy + selected device index to make Mode 2 debugging easier. (ambient_lighting/main_desktop.py)
- Motion speed now has a ramp limiter (especially in Modes 2/3) to prevent sudden fast jumps; new config knobs: `motion_speed_ramp_per_s`, `audio_motion_speed_ramp_per_s`. (ambient_lighting/mode_manager.py, ambient_lighting/config.py)
