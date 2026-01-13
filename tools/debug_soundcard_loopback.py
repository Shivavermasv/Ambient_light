r"""Debug tool: probe Windows loopback audio via soundcard.

Run with the workspace venv:
    .venv\Scripts\python.exe tools\debug_soundcard_loopback.py

It prints per-chunk RMS/max so you can see whether samples are arriving.
"""

import time

import numpy as np


def main():
    import soundcard as sc

    loopbacks = [m for m in sc.all_microphones(include_loopback=True) if "loopback" in str(m).lower()]
    if not loopbacks:
        raise SystemExit("No loopback microphones found via soundcard.")

    print("Loopback microphones:")
    for m in loopbacks:
        print(" -", m)

    mic = loopbacks[0]
    sr = 48000
    chunk = sr // 5  # 0.2s

    print("\nUsing:", mic)
    print("Recording 10 chunks... (play music while this runs)")

    with mic.recorder(samplerate=sr, channels=2) as rec:
        for i in range(10):
            a = np.asarray(rec.record(chunk), dtype=np.float32)
            rms = float(np.sqrt(np.mean(a * a)))
            mx = float(np.max(np.abs(a)))
            print(f"{i:02d} rms={rms:.6f} max={mx:.6f}")
            time.sleep(0.05)


if __name__ == "__main__":
    main()
