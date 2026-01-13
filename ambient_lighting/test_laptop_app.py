"""
test_laptop_app.py
Test cases for ESP32 Cinematic Ambient Cove Lighting laptop application.
Strictly follows PROJECT_SPEC.md edge cases and algorithmic requirements.
"""
import unittest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from screen.screen_sampler import ScreenSampler
from audio.audio_fft import AudioFFT
from packet_builder import PacketBuilder
from config import Config

class TestScreenSampler(unittest.TestCase):
    def setUp(self):
        self.sampler = ScreenSampler()

    def test_screen_failure_reuse_last_color(self):
        # Simulate screen capture failure
        self.sampler.last_color = np.array([123, 45, 67], dtype=np.float32)
        color = self.sampler.get_screen_color()
        self.assertTrue(np.allclose(color, self.sampler.last_color))

    def test_weighted_mean_algorithm(self):
        # Provide synthetic image with known HSV
        img = np.ones((36, 64, 3), dtype=np.uint8) * 128
        hsv, img_cropped = self.sampler.process_image(img)
        rgb = self.sampler.weighted_mean_color(hsv, img_cropped)
        self.assertEqual(rgb.shape, (3,))

class TestAudioFFT(unittest.TestCase):
    def setUp(self):
        self.audio = AudioFFT()

    def test_audio_unavailable_zero_motion(self):
        # Simulate audio stream failure
        self.audio.stream = None
        energy = self.audio.get_audio_energy()
        self.assertEqual(energy, 0.0)

class TestPacketBuilder(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.builder = PacketBuilder(self.config)

    def test_packet_format(self):
        data = {
            'mode': 1,
            'base_color': [10, 20, 30],
            'brightness': 80,
            'motion_energy': 100,
            'motion_speed': 0.5,
            'direction': 1,
            'frame_id': 7,
        }
        packet = self.builder.build(data)
        self.assertEqual(len(packet), 12)
        self.assertEqual(packet[0], 0xAA)
        self.assertEqual(packet[11], 0x55)
        self.assertEqual(packet[9], 7)
        # Checksum
        checksum = 0
        for b in packet[1:10]:
            checksum ^= b
        self.assertEqual(packet[10], checksum)

if __name__ == "__main__":
    unittest.main()
