"""
mode_manager.py
Handles operating modes and packet building for ambient lighting.
Strictly follows PROJECT_SPEC.md.
"""


import time
from packet_builder import PacketBuilder

class ModeManager:
    def __init__(self, config):
        self.config = config
        self.packet_builder = PacketBuilder(config)
        self.current_mode = 1
        # Initialize with current time so we do not immediately trigger fallback on startup
        self.last_packet_time = time.time()

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
        if mode == 4:
            low, high = 70, 80
        else:
            low, high = self.config.brightness_ranges.get(mode, (70, 90))
        return int((low + high) / 2)

    def build_packet(self, data):
        self.last_packet_time = time.time()

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

        data['motion_energy'] = motion_energy
        data['motion_speed'] = self._compute_motion_speed(motion_energy)
        data['brightness'] = self._brightness_for_mode(mode)

        return self.packet_builder.build(data)
