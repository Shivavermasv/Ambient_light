"""
mode_manager.py
Handles operating modes and packet building for ambient lighting.
Strictly follows PROJECT_SPEC.md, with optional user-approved tweaks toggleable in config.
"""


import time
import numpy as np
import colorsys
from packet_builder import PacketBuilder

class ModeManager:
    def __init__(self, config):
        self.config = config
        self.packet_builder = PacketBuilder(config)
        self.current_mode = 1
        # Initialize with current time so we do not immediately trigger fallback on startup
        self.last_packet_time = time.time()
        self.last_motion_energy = 0.0
        self.bump_end_time = 0.0
        self.drift_last_time = time.time()
        self.mode4_phase = 0.0
        self.audio_motion_state = 0.0
        self.audio_motion_smooth = 0.0
        self.audio_silence_since = None
        self.last_audio_color = np.array([180, 160, 140], dtype=np.float32)
        self._last_motion_speed = 0.15
        self._frame_id = 0
        self._last_brightness = None

    def update_mode(self, data):
        now = time.time()
        requested_mode = data.get('mode', self.current_mode)
        # Apply fallback only when packets have stopped for 1.8s; do not overwrite requested mode otherwise
        if now - self.last_packet_time > 1.8:
            self.current_mode = 4
            data['mode'] = 4
        else:
            self.current_mode = requested_mode
            data['mode'] = requested_mode

    def _compute_motion_speed(self, motion_energy):
        # Non-linear mapping sqrt, range 0.15 - 1.2
        span = 1.2 - 0.15
        norm = max(min(motion_energy / 180.0, 1.0), 0.0)
        return 0.15 + span * (norm ** 0.5)

    def _brightness_for_mode(self, mode):
        if mode == 5:
            return 0
        # Mode brightness ranges (packet brightness still capped by led_brightness_cap).
        # Mode 4 is included so fallback can be driven from config like other modes.
        low, high = self.config.brightness_ranges.get(mode, (70, 90))
        return int((low + high) / 2)

    def _audio_color(self, data):
        """Map audio features to a stable color; avoid bright pink on low energy."""
        energy = max(data.get('audio_motion_energy', 0.0), 0.0)
        centroid = max(data.get('audio_centroid', 0.0), 0.0)
        low_hz = self.config.audio_centroid_low_hz
        high_hz = self.config.audio_centroid_high_hz
        norm_c = min(max((centroid - low_hz) / max(high_hz - low_hz, 1), 0.0), 1.0)
        # Hue from warm (20°) to cool (220°)
        hue = (20.0 + norm_c * 200.0) / 360.0
        # Saturation scales with energy but with a floor and ceiling
        sat = min(max(energy / 160.0, 0.08), 0.9)
        # Value scales gently with energy to avoid strobe
        val = 0.55 + 0.35 * min(energy / 140.0, 1.0)
        if energy < 2.0:
            # keep previous audio color to prevent sudden pinks on silence
            return self.last_audio_color.copy()
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
        c = np.array([r, g, b]) * 255.0
        self.last_audio_color = c
        return c

    def build_packet(self, data):
        self.last_packet_time = time.time()

        # Packet sequence number (byte 9). Increment once per send.
        data['frame_id'] = int(self._frame_id) & 0xFF
        self._frame_id = (self._frame_id + 1) & 0xFF

        mode = data.get('mode', 1)

        # Determine motion source by mode
        screen_motion = data.get('screen_motion_energy', 0.0)
        audio_motion = data.get('audio_motion_energy', 0.0)
        if mode == 1:
            motion_energy = screen_motion
        elif mode == 2:
            motion_energy = audio_motion
        elif mode == 3:
            motion_energy = audio_motion
        else:
            motion_energy = 0.0

        # Soft beat accent: detect large jumps and add a short bump to speed
        now = time.time()
        jump_thresh = self.config.motion_jump_threshold
        if self.config.enable_soft_beat_accent and mode == 1 and self.last_motion_energy > 0:
            if motion_energy > (1 + jump_thresh) * self.last_motion_energy:
                self.bump_end_time = now + (self.config.motion_bump_ms / 1000.0)
        in_bump = self.config.enable_soft_beat_accent and now < self.bump_end_time

        # Mode-specific motion smoothing already applied upstream; retain value
        self.last_motion_energy = motion_energy

        # Additional gating/smoothing for audio-driven modes to avoid flicker on silence
        if mode in (2, 3):
            # Keep FFT attack/release smoothing from AudioFFT, but avoid an extra laptop-side smoothing layer.
            gate = float(getattr(self.config, 'audio_motion_gate', 4.0))
            if motion_energy < gate:
                motion_energy = 0.0

        # Mode 4 static amber override
        if mode == 4 and hasattr(self.config, 'mode4_static_color'):
            data['base_color'] = self.config.mode4_static_color

        # Audio-driven color for Mode 2
        if mode == 2:
            data['base_color'] = self._audio_color(data)

        # Quantize motion energy once and use the same value for packet + speed mapping.
        motion_energy_q = int(np.clip(np.round(float(motion_energy)), 0, 180))
        data['motion_energy'] = motion_energy_q

        base_speed = self._compute_motion_speed(float(motion_energy_q))
        if motion_energy_q <= 0:
            # If motion is zero, request true zero speed.
            base_speed = 0.0
        if mode in (2, 3):
            base_speed = min(base_speed, float(getattr(self.config, 'audio_motion_speed_cap', 0.65)))
        if in_bump:
            base_speed = min(base_speed + self.config.motion_bump_speed_cap, 1.2)

        # Ramp-limit speed changes to avoid sudden jumps (strip safety + nicer feel).
        now = time.time()
        dt = max(now - getattr(self, '_last_speed_time', now), 1e-3)
        self._last_speed_time = now
        ramp_per_s = float(getattr(self.config, 'motion_speed_ramp_per_s', 2.5))
        if mode in (2, 3):
            ramp_per_s = float(getattr(self.config, 'audio_motion_speed_ramp_per_s', 0.8))
        max_delta = ramp_per_s * dt
        base_speed = float(np.clip(base_speed, 0.0, 1.2))
        if motion_energy_q <= 0:
            # On silence/zero motion, snap speed down to 0 (prevents "motion on silent").
            base_speed = 0.0
            self._last_motion_speed = 0.0
        else:
            base_speed = float(np.clip(base_speed, self._last_motion_speed - max_delta, self._last_motion_speed + max_delta))
            self._last_motion_speed = base_speed

        data['motion_speed'] = base_speed

        # Quantize brightness updates to reduce shimmer: update every 3 frames.
        if data['frame_id'] % 3 == 0 or self._last_brightness is None:
            self._last_brightness = self._brightness_for_mode(mode)
        data['brightness'] = int(self._last_brightness)

        # Night-cap brightness
        if self.config.enable_night_cap:
            data['brightness'] = min(data['brightness'], self.config.night_cap_value)

        # Mode 4 ultra-slow drift
        if self.config.enable_mode4_drift and mode == 4:
            period = max(self.config.mode4_drift_period_s, 1)
            amp = self.config.mode4_drift_amplitude
            t = now
            drift = amp * np.sin(2 * np.pi * t / period)
            data['brightness'] = int(np.clip(data['brightness'] + drift, 0, self.config.led_brightness_cap))

        # Audio-driven enhancements (Mode 2 focused)
        if self.config.enable_audio_enhancements and mode == 2:
            audio_bass = data.get('audio_bass', 0.0)
            audio_mid = data.get('audio_mid', 0.0)
            centroid = data.get('audio_centroid', 0.0)

            # Brightness float around midpoint; settle to low when silent
            if self.config.enable_audio_brightness_float:
                midpoint = data['brightness']
                float_range = self.config.audio_brightness_float_range
                if motion_energy <= 0.0:
                    data['brightness'] = int(np.clip(midpoint - float_range / 2, 0, self.config.led_brightness_cap))
                else:
                    norm_energy = min(max(motion_energy / 200.0, 0.0), 1.0)
                    target = midpoint - float_range / 2 + norm_energy * float_range
                    if not hasattr(self, '_brightness_float_state'):
                        self._brightness_float_state = midpoint
                    alpha = self.config.audio_brightness_float_alpha
                    self._brightness_float_state = alpha * target + (1 - alpha) * self._brightness_float_state
                    data['brightness'] = int(np.clip(self._brightness_float_state, 0, self.config.led_brightness_cap))

            # Hue bias based on spectral centroid
            if self.config.enable_audio_hue_bias:
                rgb = np.clip(data.get('base_color', [0, 0, 0]), 0, 255).astype(np.float32)
                hsv = colorsys.rgb_to_hsv(*(rgb / 255.0))
                low_hz = self.config.audio_centroid_low_hz
                high_hz = self.config.audio_centroid_high_hz
                norm_c = min(max((centroid - low_hz) / max(high_hz - low_hz, 1), 0.0), 1.0)
                hue_shift = (norm_c - 0.5) * 2 * (self.config.audio_hue_bias_degrees / 360.0)
                new_h = (hsv[0] + hue_shift) % 1.0
                new_rgb = np.array(colorsys.hsv_to_rgb(new_h, hsv[1], hsv[2])) * 255.0
                data['base_color'] = new_rgb

        # Direction drift when idle/low motion
        if self.config.enable_direction_drift:
            if motion_energy < self.config.direction_drift_motion_threshold:
                if now - self.drift_last_time >= self.config.direction_drift_interval_s:
                    data['direction'] = (data.get('direction', 0) + self.config.direction_drift_step) % 256
                    self.drift_last_time = now
            else:
                self.drift_last_time = now

        # Mode 2: force a gentle forward/back travel by alternating direction
        # while audio motion is active. This prevents "flicker only" when direction
        # is otherwise neutral (128) for stability.
        if mode == 2 and bool(getattr(self.config, 'enable_audio_direction_oscillation', False)):
            threshold = float(getattr(self.config, 'audio_direction_motion_threshold', 6))
            if motion_energy_q >= threshold:
                period = float(getattr(self.config, 'audio_direction_period_s', 6.0))
                period = max(period, 0.5)
                phase = (now % period) / period
                if phase < 0.5:
                    data['direction'] = int(getattr(self.config, 'audio_direction_left', 32)) & 0xFF
                else:
                    data['direction'] = int(getattr(self.config, 'audio_direction_right', 224)) & 0xFF
            else:
                data['direction'] = 128

        return self.packet_builder.build(data)
