"""
packet_builder.py
Builds UDP packets for ESP32 ambient lighting according to protocol in PROJECT_SPEC.md.
"""
import numpy as np

class PacketBuilder:
    def __init__(self, config):
        self.config = config

    def build(self, data):
        # Build 12-byte packet
        packet = np.zeros(12, dtype=np.uint8)
        packet[0] = 0xAA  # Header
        packet[1] = data.get('mode', 1)
        rgb = np.clip(np.round(data.get('base_color', [0,0,0])), 0, 255).astype(np.uint8)
        packet[2:5] = rgb
        packet[5] = np.clip(int(data.get('brightness', 70)), 0, self.config.led_brightness_cap)
        packet[6] = np.clip(int(data.get('motion_energy', 0)), 0, 180)
        packet[7] = np.clip(int(data.get('motion_speed', 0.15) * 100), 0, 255)
        packet[8] = int(data.get('direction', 0))
        # Byte 9: frame_id (0-255 wrap). Used for loss/reorder detection on ESP32.
        packet[9] = int(data.get('frame_id', 0)) & 0xFF
        # Checksum: XOR bytes 1-9
        packet[10] = np.bitwise_xor.reduce(packet[1:10])
        packet[11] = 0x55  # Footer
        return packet.tobytes()
