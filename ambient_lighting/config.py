"""
config.py
Configuration for ESP32 Cinematic Ambient Cove Lighting laptop application.
Strictly follows PROJECT_SPEC.md.
"""

class Config:
    def __init__(self):
        # UDP settings
        self.udp_ip = '192.168.0.103'  # ESP32 IP (updated to match device)
        self.udp_port = 4210
        self.udp_rate_hz = 25
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
        self.led_brightness_cap = 120
        # Mode brightness ranges
        self.brightness_ranges = {
            1: (70, 90),
            2: (90, 120),
            3: (80, 100)
        }
