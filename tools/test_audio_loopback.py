from __future__ import annotations

import os
import sys
import time


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_ROOT = os.path.join(REPO_ROOT, "ambient_lighting")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from audio.audio_fft import AudioFFT


def main() -> None:
    # Request Stereo Mix (device 14). If PortAudio can't open it, AudioFFT should
    # fall back to system loopback via `soundcard`.
    a = AudioFFT(device=14, sample_rate=48000, buffer_size=2048)
    print("backend=", getattr(a, "_backend", None))

    for i in range(20):
        f = a.get_audio_features()
        print(i, f)
        time.sleep(0.1)

    a.close()


if __name__ == "__main__":
    main()
