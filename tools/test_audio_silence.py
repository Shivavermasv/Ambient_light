from __future__ import annotations

import os
import sys
import time

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_ROOT = os.path.join(REPO_ROOT, "ambient_lighting")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from audio.audio_fft import AudioFFT


def main() -> None:
    # If Stereo Mix can't open, AudioFFT should switch to soundcard loopback.
    a = AudioFFT(device=14, sample_rate=48000, buffer_size=2048)
    backend = getattr(a, "_backend", None)
    print("backend=", backend)

    duration_s = 20.0
    dt_s = 0.10
    n = int(duration_s / dt_s)

    energies: list[float] = []
    timestamps: list[float] = []

    t0 = time.time()
    for i in range(n):
        f = a.get_audio_features()
        e = float(f.get("energy", 0.0) or 0.0)
        energies.append(e)
        timestamps.append(time.time() - t0)

        # Print a compact line so you can see it fall after stopping music.
        if i % 5 == 0:
            print(f"t={timestamps[-1]:5.1f}s  energy={e:7.2f}  bass={float(f.get('bass',0.0)):8.1f}  mid={float(f.get('mid',0.0)):8.1f}")

        time.sleep(dt_s)

    a.close()

    arr = np.asarray(energies, dtype=np.float32)
    # Evaluate only the last 6 seconds to represent 'silence after stopping'.
    tail_s = 6.0
    tail_n = int(tail_s / dt_s)
    tail = arr[-tail_n:] if len(arr) >= tail_n else arr

    def stats(x: np.ndarray) -> str:
        return f"min={float(np.min(x)):.2f} mean={float(np.mean(x)):.2f} p95={float(np.percentile(x,95)):.2f} max={float(np.max(x)):.2f}"

    zeros = float(np.mean(tail <= 0.5) * 100.0)

    print("\n--- summary ---")
    print("all :", stats(arr))
    print(f"tail ({tail_s:.0f}s):", stats(tail), f"; <=0.5 for {zeros:.1f}% of tail")


if __name__ == "__main__":
    main()
