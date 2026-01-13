"""
config.py
Configuration for ESP32 Cinematic Ambient Cove Lighting laptop application.
Strictly follows PROJECT_SPEC.md.
"""

class Config:
    def __init__(self):
        # UDP settings
        self.udp_ip = '192.168.0.100'  # ESP32 IP (updated to match device)
        self.udp_port = 4210
        self.udp_rate_hz = 25
        self.debug_udp_packets = False
        # Screen settings
        self.screen_downscale = (64, 36)
        self.screen_crop_top = 0.07
        self.screen_crop_bottom = 0.13
        self.screen_ema_ms = 600
        # Audio settings
        self.audio_sample_rate = 44100
        self.audio_buffer_size = 2048
        self.audio_ema_ms = 100
        # LED settings
        self.led_count = 600
        # 0-255 (uint8). Set to 255 for maximum output; ESP32 FastLED power limiting still applies.
        self.led_brightness_cap = 255
        # Mode brightness ranges
        self.brightness_ranges = {
            1: (255, 255),
            2: (255, 255),
            3: (255, 255),
            4: (255, 255),
        }

        # Tweaks (all optional / toggleable)
        # Motion smoothing per mode (ms). Old single value: 250ms.
        self.motion_smoothing_ms = {1: 200, 2: 190, 3: 200}
        # Soft beat accent toggle and parameters
        # Optional (recommended OFF): can interact poorly with UDP jitter and speed ramp limiting.
        self.enable_soft_beat_accent = False
        self.motion_jump_threshold = 0.30  # 30% jump
        self.motion_bump_ms = 300
        self.motion_bump_speed_cap = 0.15  # added on top of mapped speed
        # Brightness comfort toggles
        self.enable_night_cap = False  # default OFF per policy
        self.night_cap_value = 90
        self.enable_mode4_drift = False  # default OFF
        self.mode4_drift_amplitude = 5
        self.mode4_drift_period_s = 25  # 20–30s target
        # Color steadiness overrides (additional EMA applied after sampler)
        # Disabled: keep only the sampler EMA to avoid redundant smoothing/latency.
        self.enable_color_mode_ema = False
        self.color_ema_ms = {1: 360, 3: 520}  # faster response vs prior 480/600
        self.enable_desat_reduction = False  # keep 12%; set True to try 10%
        self.desat_amount = 0.10  # old was 0.12
        # Dark-scene enhancement (optional, improves color when overall V is low)
        self.enable_dark_boost = True
        self.dark_boost_v_thresh = 0.25
        self.dark_boost_strength = 0.15  # scale for saturation/value boost when under threshold
        # Spatial bias (no protocol change): bias color/direction toward dominant region
        self.enable_spatial_bias = True
        self.spatial_regions = 3  # left, center, right
        self.spatial_bias_blend = 0.35  # blend dominant region color into base
        # Audio robustness
        self.audio_target_level = 160  # normalize toward this
        self.audio_hard_cap = 190      # hard ceiling
        self.audio_noise_gate = 4.0    # ease gate to let motion through
        self.audio_noise_gate_hold_s = 2.0  # slightly shorter hold
        # Direction drift
        self.enable_direction_drift = False  # default OFF
        self.direction_drift_step = 1
        self.direction_drift_interval_s = 1.5
        self.direction_drift_motion_threshold = 8.0  # disable drift when motion is high

        # Audio-musical enhancements (Mode 2 focused)
        self.enable_audio_enhancements = True
        # Bass/mid split (retain legacy 0.7/0.3 for motion; extras use raw bands)
        self.audio_bass_motion_weight = 0.7  # old fixed weight 0.7
        self.audio_mid_motion_weight = 0.3   # old fixed weight 0.3
        # Brightness float around midpoint in Mode 2 (±range). Old behavior: fixed midpoint.
        self.enable_audio_brightness_float = False
        self.audio_brightness_float_range = 10
        self.audio_brightness_float_alpha = 0.2  # smoothing for brightness float
        # Hue bias based on spectral centroid; tiny shift to warm/cool the base color.
        self.enable_audio_hue_bias = True
        self.audio_hue_bias_degrees = 8  # small hue nudge
        self.audio_centroid_low_hz = 200
        self.audio_centroid_high_hz = 4000
        # Audio release to avoid snapping to zero between phrases.
        self.audio_release_ms = 700  # previously 600, smoother tail to avoid flutter
        # Motion gating for audio-driven modes
        self.audio_motion_gate = 4.0  # allow more motion to pass
        self.audio_motion_decay = 0.60  # slower decay to keep some motion
        self.audio_motion_smooth_ms = 250  # slightly quicker smoothing for responsiveness
        self.audio_motion_silence_hold_s = 1.2  # still clamps, but sooner responsiveness after sound
        self.audio_motion_speed_cap = 0.65  # cap speed in modes 2/3 for safety (old hard-coded 0.9)

        # Mode 2: ensure visible forward/back travel (direction alternates while audio is active)
        self.enable_audio_direction_oscillation = True
        self.audio_direction_period_s = 6.0
        self.audio_direction_motion_threshold = 6
        self.audio_direction_left = 32
        self.audio_direction_right = 224

        # Speed ramp limiting (units: speed/sec). Helps prevent sudden jumps that can stress strips.
        self.motion_speed_ramp_per_s = 2.5
        self.audio_motion_speed_ramp_per_s = 0.8

        # Mode 4 static color override (bright amber)
        self.mode4_static_color = [255, 180, 80]
