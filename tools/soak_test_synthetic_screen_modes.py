"""soak_test_synthetic_screen_modes.py

Long-run synthetic stress test for the laptop-side algorithm.
- Generates deterministic synthetic frames (no real screen capture)
- Simulates audio features (no real audio device)
- Builds packets for modes 1-5 and validates packet invariants

Usage:
  E:/ambient_light_project/.venv/Scripts/python.exe tools/soak_test_synthetic_screen_modes.py --seconds 180 --fps 25
"""

import argparse
import time

import numpy as np

# Ensure local imports work when run from repo root.
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ambient_lighting')))

from config import Config
from mode_manager import ModeManager
from screen.screen_sampler import ScreenSampler


def make_frame_pattern(t: float, w: int = 64, h: int = 36) -> np.ndarray:
    """Cycle through patterns that historically broke the sampler."""
    phase = int(t) % 12

    if phase in (0, 1):
        # Bright saturated primaries (V=1) + should not get stuck
        colors = ([255, 0, 0], [0, 255, 0], [0, 0, 255])
        c = colors[int(t * 2) % len(colors)]
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, :, :] = np.array(c, dtype=np.uint8)
        return img

    if phase == 2:
        # Pure white (should be ignored -> reuse last color)
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, :, :] = 255
        return img

    if phase == 3:
        # Very dark scene
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, :, :] = 2
        return img

    if phase in (4, 5):
        # Split regions: left dark saturated, right bright white
        img = np.zeros((h, w, 3), dtype=np.uint8)
        x0 = w // 3
        x1 = (2 * w) // 3
        img[:, :x0, :] = np.array([0, 128, 0], dtype=np.uint8)
        img[:, x0:x1, :] = np.array([40, 40, 40], dtype=np.uint8)
        img[:, x1:, :] = np.array([255, 255, 255], dtype=np.uint8)
        return img

    if phase in (6, 7, 8):
        # Smooth gradient sweep
        img = np.zeros((h, w, 3), dtype=np.uint8)
        x = np.linspace(0, 1, w, dtype=np.float32)
        r = (255 * (0.5 + 0.5 * np.sin(2 * np.pi * (x + 0.05 * t)))).astype(np.uint8)
        g = (255 * (0.5 + 0.5 * np.sin(2 * np.pi * (x + 0.05 * t + 0.33)))).astype(np.uint8)
        b = (255 * (0.5 + 0.5 * np.sin(2 * np.pi * (x + 0.05 * t + 0.66)))).astype(np.uint8)
        img[:, :, 0] = r[None, :]
        img[:, :, 1] = g[None, :]
        img[:, :, 2] = b[None, :]
        return img

    # Random-but-deterministic noise block
    rng = np.random.default_rng(int(t * 1000) & 0xFFFF)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def run_sampler_on_frame(sampler: ScreenSampler, img: np.ndarray) -> np.ndarray:
    hsv, cropped = sampler.process_image(img)
    rgb = sampler.weighted_mean_color(hsv, cropped)
    rgb = sampler.boost_dark(rgb)
    rgb = sampler.desaturate(rgb, amount=sampler.desat_amount)
    rgb = sampler.smooth_color(rgb)
    return rgb


def validate_packet(packet_bytes: bytes) -> None:
    p = np.frombuffer(packet_bytes, dtype=np.uint8)
    if int(p[0]) != 0xAA or int(p[11]) != 0x55:
        raise AssertionError("Bad header/footer")
    checksum = 0
    for b in p[1:10]:
        checksum ^= int(b)
    if int(p[10]) != checksum:
        raise AssertionError("Bad checksum")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=180.0)
    ap.add_argument('--fps', type=float, default=25.0)
    args = ap.parse_args()

    cfg = Config()
    cfg.enable_night_cap = False
    cfg.led_brightness_cap = 255
    cfg.brightness_ranges = {1: (255, 255), 2: (255, 255), 3: (255, 255), 4: (255, 255)}

    # Keep the sampler aligned with main_desktop defaults.
    desat_amount = cfg.desat_amount if getattr(cfg, 'enable_desat_reduction', False) else 0.12
    sampler = ScreenSampler(
        downscale_size=cfg.screen_downscale,
        crop_top=cfg.screen_crop_top,
        crop_bottom=cfg.screen_crop_bottom,
        ema_ms=cfg.screen_ema_ms,
        desat_amount=desat_amount,
        dark_boost=cfg.enable_dark_boost,
        dark_boost_v_thresh=cfg.dark_boost_v_thresh,
        dark_boost_strength=cfg.dark_boost_strength,
    )

    mm = ModeManager(cfg)

    dt = 1.0 / max(args.fps, 1e-3)
    end = time.time() + args.seconds

    last_color = np.array([0, 0, 0], dtype=np.float32)
    motion_alpha = 1 - np.exp(-1 / (180 / 40))
    motion_value = 0.0

    packets = 0
    last_print = time.time()

    while time.time() < end:
        now = time.time()
        t = args.seconds - (end - now)

        img = make_frame_pattern(t)
        color = run_sampler_on_frame(sampler, img)

        delta = np.abs(color - last_color).sum()
        screen_motion = float(np.clip(delta * 0.8, 0, 180))
        motion_value = float(motion_alpha * screen_motion + (1 - motion_alpha) * motion_value)
        last_color = color

        # Synthetic audio features
        audio_energy = 120.0 * abs(np.sin(2 * np.pi * t / 2.5))
        audio_centroid = 300.0 + 2500.0 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 7.0))

        base = {
            'base_color': color,
            'screen_motion_energy': motion_value,
            'audio_motion_energy': audio_energy,
            'audio_centroid': audio_centroid,
            'direction': 128,
        }

        for mode in (1, 2, 3, 4, 5):
            d = dict(base)
            d['mode'] = mode
            pkt = mm.build_packet(d)
            validate_packet(pkt)
            packets += 1

        if now - last_print > 5.0:
            print(
                f"t={t:6.1f}s color={list(np.round(color).astype(int))} screen_motion={motion_value:6.1f} "
                f"audio={audio_energy:6.1f} packets={packets}"
            )
            last_print = now

        time.sleep(dt)

    print(f"DONE. seconds={args.seconds} fps={args.fps} total_packets={packets}")


if __name__ == '__main__':
    main()
