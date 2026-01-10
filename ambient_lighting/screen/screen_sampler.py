"""
screen_sampler.py

Captures the screen, processes the image, and computes the weighted mean color for ambient lighting.
Follows the algorithm and constraints in PROJECT_SPEC.md.
"""

import numpy as np
import mss
import cv2
import time

class ScreenSampler:
    def __init__(self, downscale_size=(64, 36), crop_top=0.07, crop_bottom=0.13, ema_ms=600):
        """
        Initialize the screen sampler.
        Args:
            downscale_size: Target size for downscaling (width, height).
            crop_top: Fraction to crop from the top of the image.
            crop_bottom: Fraction to crop from the bottom of the image.
            ema_ms: EMA smoothing window in milliseconds (800ms).
        """
        self.downscale_size = downscale_size
        self.crop_top = crop_top
        self.crop_bottom = crop_bottom
        self.ema_alpha = self._compute_ema_alpha(ema_ms)
        self.last_color = np.array([0, 0, 0], dtype=np.float32)
        self.last_capture_success = True

    def _compute_ema_alpha(self, ema_ms):
        # Calculate EMA alpha for smoothing
        # Assume ~25Hz update rate (40ms per frame)
        frame_ms = 40
        n = ema_ms / frame_ms
        return 1 - np.exp(-1 / n)

    def capture_screen(self):
        """
        Capture the full screen using mss.
        Returns:
            np.ndarray: Captured image in RGB format, or None if failed.
        """
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                img = np.array(sct.grab(monitor))
                # Convert BGRA to RGB
                img = img[..., :3][..., ::-1]
                self.last_capture_success = True
                return img
        except Exception as e:
            # Handle screen capture failure gracefully
            print(f"Screen capture failed: {e}")
            self.last_capture_success = False
            return None

    def process_image(self, img):
        """
        Downscale, crop, and convert image to HSV.
        Args:
            img: Input RGB image.
        Returns:
            hsv: Cropped and downscaled HSV image.
        """
        # Downscale
        img_small = cv2.resize(img, self.downscale_size, interpolation=cv2.INTER_AREA)
        # Crop top and bottom
        h = img_small.shape[0]
        top = int(h * self.crop_top)
        bottom = int(h * (1 - self.crop_bottom))
        img_cropped = img_small[top:bottom, :, :]
        # Convert to HSV
        hsv = cv2.cvtColor(img_cropped, cv2.COLOR_RGB2HSV)
        hsv = hsv.astype(np.float32) / np.array([180, 255, 255], dtype=np.float32)  # Normalize H, S, V
        return hsv, img_cropped

    def weighted_mean_color(self, hsv, img_cropped):
        """
        Compute weighted mean color from HSV and RGB images.
        Ignores pixels with V > 0.92 or S < 0.08.
        Weight = S * (1 - V)^1.5
        Returns:
            np.ndarray: Weighted mean RGB color (float32, range 0-255)
        """
        S = hsv[..., 1]
        V = hsv[..., 2]
        mask = (V <= 0.92) & (S >= 0.08)
        weights = np.zeros_like(S)
        weights[mask] = S[mask] * np.power(1 - V[mask], 1.5)
        weights_sum = np.sum(weights)
        if weights_sum == 0:
            # Fallback: use last color
            print("Weighted mean: no valid pixels, using last color.")
            return self.last_color.copy()
        # Apply weights to RGB
        rgb = img_cropped.astype(np.float32)
        weighted_rgb = np.tensordot(weights, rgb, axes=([0, 1], [0, 1])) / weights_sum
        return weighted_rgb

    def desaturate(self, rgb, amount=0.12):
        """
        Desaturate the color by the given amount.
        Args:
            rgb: Input RGB color (float32, range 0-255)
            amount: Fraction to desaturate (0-1)
        Returns:
            np.ndarray: Desaturated RGB color
        """
        # Convert to HSV
        hsv = cv2.cvtColor(np.uint8([[rgb]]), cv2.COLOR_RGB2HSV).astype(np.float32)
        hsv[0, 0, 1] *= (1 - amount)
        # Convert back to RGB
        rgb_desat = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)[0, 0]
        return rgb_desat.astype(np.float32)

    def smooth_color(self, rgb):
        """
        Apply EMA smoothing to the color.
        Args:
            rgb: Current RGB color (float32)
        Returns:
            np.ndarray: Smoothed RGB color
        """
        self.last_color = self.ema_alpha * rgb + (1 - self.ema_alpha) * self.last_color
        return self.last_color.copy()

    def get_screen_color(self):
        """
        Main entry point: capture, process, compute weighted mean, desaturate, smooth.
        Returns:
            np.ndarray: Final RGB color (float32, range 0-255)
        """
        img = self.capture_screen()
        if img is None:
            # Screen capture failed, use last color
            print("Screen capture unavailable, reusing last color.")
            return self.last_color.copy()
        hsv, img_cropped = self.process_image(img)
        rgb = self.weighted_mean_color(hsv, img_cropped)
        rgb = self.desaturate(rgb, amount=0.12)
        rgb = self.smooth_color(rgb)
        return rgb

if __name__ == "__main__":
    sampler = ScreenSampler()
    prev_rgb = None
    while True:
        img = sampler.capture_screen()
        if img is not None:
            hsv, img_cropped = sampler.process_image(img)
            raw_rgb = sampler.weighted_mean_color(hsv, img_cropped)
            smoothed_rgb = sampler.smooth_color(raw_rgb)
            print(f"Raw weighted RGB: {raw_rgb}")
            print(f"Smoothed RGB: {smoothed_rgb}")
        else:
            print("Screen capture unavailable, reusing last color.")
        time.sleep(0.04)  # ~25Hz
