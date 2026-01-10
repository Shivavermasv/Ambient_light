"""
signal_processing.py
Signal processing utilities for smoothing motion energy and other signals.
Strictly follows PROJECT_SPEC.md.
"""
import numpy as np

class EMA:
    def __init__(self, ms, rate_hz):
        frame_ms = 1000 / rate_hz
        n = ms / frame_ms
        self.alpha = 1 - np.exp(-1 / n)
        self.value = 0.0

    def update(self, x):
        self.value = self.alpha * x + (1 - self.alpha) * self.value
        return self.value

# Example usage for motion energy smoothing (250ms)
motion_ema = EMA(ms=250, rate_hz=25)

def smooth_motion(x):
    return motion_ema.update(x)
