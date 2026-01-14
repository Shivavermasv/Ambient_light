"""test_screen_cases.py

Synthetic, deterministic tests for the screen algorithm and per-mode packet behavior.
These tests avoid real screen/audio devices and validate key invariants from PROJECT_SPEC.md.
"""

import unittest
from unittest import mock

import numpy as np

from config import Config
from mode_manager import ModeManager
from packet_builder import PacketBuilder
from screen.screen_sampler import ScreenSampler


def _make_solid_frame(rgb, w=64, h=36):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 0] = int(rgb[0])
    img[:, :, 1] = int(rgb[1])
    img[:, :, 2] = int(rgb[2])
    return img


def _make_split_frame(left_rgb, center_rgb, right_rgb, w=64, h=36):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    x0 = w // 3
    x1 = (2 * w) // 3
    img[:, :x0, :] = np.array(left_rgb, dtype=np.uint8)
    img[:, x0:x1, :] = np.array(center_rgb, dtype=np.uint8)
    img[:, x1:, :] = np.array(right_rgb, dtype=np.uint8)
    return img


def _run_sampler_on_frame(sampler: ScreenSampler, img: np.ndarray) -> np.ndarray:
    hsv, img_cropped = sampler.process_image(img)
    rgb = sampler.weighted_mean_color(hsv, img_cropped)
    rgb = sampler.boost_dark(rgb)
    rgb = sampler.desaturate(rgb, amount=sampler.desat_amount)
    rgb = sampler.smooth_color(rgb)
    return rgb


def _parse_packet(packet_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(packet_bytes, dtype=np.uint8)
    return arr


def _assert_packet_valid(testcase: unittest.TestCase, packet_bytes: bytes):
    p = _parse_packet(packet_bytes)
    testcase.assertEqual(int(p[0]), 0xAA)
    testcase.assertEqual(int(p[11]), 0x55)
    checksum = 0
    for b in p[1:10]:
        checksum ^= int(b)
    testcase.assertEqual(int(p[10]), checksum)
    testcase.assertTrue(np.all((p >= 0) & (p <= 255)))


class TestScreenAlgorithmSynthetic(unittest.TestCase):
    def setUp(self):
        # Keep crop disabled for deterministic synthetic frames.
        # ema_ms=1 => alpha ~ 1 (effectively no smoothing), so assertions are stable.
        self.sampler = ScreenSampler(
            downscale_size=(64, 36),
            crop_top=0.0,
            crop_bottom=0.0,
            ema_ms=1,
            desat_amount=0.0,
            dark_boost=False,
        )

    def test_bright_saturated_primary_colors_do_not_get_stuck(self):
        # Pure bright colors are excluded by V<=0.92, but the fallback should handle them.
        for rgb in ([255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0]):
            img = _make_solid_frame(rgb)
            out = _run_sampler_on_frame(self.sampler, img)
            self.assertTrue(np.allclose(out, np.array(rgb, dtype=np.float32), atol=2.0))

    def test_low_saturation_white_reuses_last_color(self):
        self.sampler.last_color = np.array([10, 20, 30], dtype=np.float32)
        img = _make_solid_frame([255, 255, 255])
        out = _run_sampler_on_frame(self.sampler, img)
        self.assertTrue(np.allclose(out, np.array([10, 20, 30], dtype=np.float32), atol=1e-3))

    def test_region_weights_favor_dark_saturated_region(self):
        # Use a mid-bright saturated green (V ~ 0.5) on the left to ensure non-zero weights.
        img = _make_split_frame([0, 128, 0], [0, 0, 0], [255, 255, 255])
        hsv, cropped = self.sampler.process_image(img)
        region_colors, region_weights = self.sampler.weighted_mean_color_regions(hsv, cropped, regions=3)
        self.assertEqual(len(region_weights), 3)
        self.assertGreater(region_weights[0], region_weights[1])
        self.assertGreater(region_weights[0], region_weights[2])
        self.assertIsNotNone(region_colors[0])
        self.assertTrue(np.allclose(region_colors[0], np.array([0, 128, 0], dtype=np.float32), atol=10.0))

    def test_random_frames_never_nan_and_in_range(self):
        rng = np.random.default_rng(123)
        for _ in range(200):
            img = rng.integers(0, 256, size=(36, 64, 3), dtype=np.uint8)
            out = _run_sampler_on_frame(self.sampler, img)
            self.assertTrue(np.all(np.isfinite(out)))
            self.assertTrue(np.all(out >= 0.0))
            self.assertTrue(np.all(out <= 255.0))


class TestModePacketsSynthetic(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        # Keep tests deterministic and independent of user config edits.
        self.cfg.led_brightness_cap = 255
        self.cfg.brightness_ranges = {1: (255, 255), 2: (255, 255), 3: (255, 255), 4: (255, 255)}
        self.cfg.enable_night_cap = False
        self.cfg.enable_audio_enhancements = False
        self.cfg.enable_direction_drift = False

        # Enable the Mode 2 direction oscillation for test coverage.
        self.cfg.enable_audio_direction_oscillation = True
        self.cfg.audio_direction_period_s = 6.0
        self.cfg.audio_direction_motion_threshold = 6
        self.cfg.audio_direction_left = 32
        self.cfg.audio_direction_right = 224

        self.mm = ModeManager(self.cfg)
        self.pb = PacketBuilder(self.cfg)

    def test_mode1_packet_uses_screen_motion_and_screen_color(self):
        base_color = np.array([40, 60, 80], dtype=np.float32)
        data = {
            'mode': 1,
            'base_color': base_color,
            'screen_motion_energy': 123.4,
            'audio_motion_energy': 0.0,
            'direction': 128,
        }
        pkt = self.mm.build_packet(dict(data))
        _assert_packet_valid(self, pkt)
        p = _parse_packet(pkt)
        self.assertEqual(int(p[1]), 1)
        self.assertTrue(np.allclose(p[2:5], np.round(base_color).astype(np.uint8)))
        self.assertEqual(int(p[5]), 255)
        self.assertEqual(int(p[6]), 123)

    def test_mode2_packet_overrides_color_from_audio(self):
        # Provide a base_color that should be ignored in Mode 2.
        data = {
            'mode': 2,
            'base_color': [10, 20, 30],
            'audio_motion_energy': 80.0,
            'audio_centroid': 1000.0,
            'direction': 128,
        }
        with mock.patch('time.time', return_value=1000.0):
            pkt = self.mm.build_packet(dict(data))
        _assert_packet_valid(self, pkt)
        p = _parse_packet(pkt)
        self.assertEqual(int(p[1]), 2)
        self.assertNotEqual(list(p[2:5]), [10, 20, 30])
        self.assertGreater(int(p[6]), 0)

    def test_mode2_direction_oscillates_when_audio_active(self):
        data = {
            'mode': 2,
            'audio_motion_energy': 40.0,
            'audio_centroid': 1200.0,
            'direction': 128,
        }
        with mock.patch('time.time', return_value=1.0):
            pkt_left = self.mm.build_packet(dict(data))
        with mock.patch('time.time', return_value=4.5):
            pkt_right = self.mm.build_packet(dict(data))
        p1 = _parse_packet(pkt_left)
        p2 = _parse_packet(pkt_right)
        self.assertIn(int(p1[8]), (self.cfg.audio_direction_left, self.cfg.audio_direction_right, 128))
        self.assertIn(int(p2[8]), (self.cfg.audio_direction_left, self.cfg.audio_direction_right, 128))
        self.assertNotEqual(int(p1[8]), int(p2[8]))

    def test_mode3_packet_keeps_screen_color_uses_audio_motion(self):
        data = {
            'mode': 3,
            'base_color': [200, 10, 30],
            'audio_motion_energy': 77.0,
            'direction': 128,
        }
        with mock.patch('time.time', return_value=100.0):
            pkt = self.mm.build_packet(dict(data))
        _assert_packet_valid(self, pkt)
        p = _parse_packet(pkt)
        self.assertEqual(int(p[1]), 3)
        self.assertEqual(list(p[2:5]), [200, 10, 30])
        self.assertEqual(int(p[6]), 77)

    def test_mode5_off_is_black_and_zero_brightness(self):
        data = {'mode': 5, 'base_color': [255, 255, 255], 'screen_motion_energy': 180}
        with mock.patch('time.time', return_value=0.0):
            pkt = self.mm.build_packet(dict(data))
        _assert_packet_valid(self, pkt)
        p = _parse_packet(pkt)
        self.assertEqual(int(p[1]), 5)
        self.assertEqual(int(p[5]), 0)


if __name__ == '__main__':
    unittest.main()
