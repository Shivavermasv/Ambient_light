"""
audio_fft.py
Processes system audio and computes FFT-based energy for ambient lighting.
Strictly follows PROJECT_SPEC.md.
"""
import numpy as np
import sounddevice as sd
import scipy.fftpack
import time

class AudioFFT:
    def __init__(self, sample_rate=44100, buffer_size=2048, ema_ms=100, device=None):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.ema_ms = ema_ms
        self.ema_alpha = self._compute_ema_alpha(ema_ms)
        self.last_energy = 0.0
        self.stream = None
        self.device = device
        # Old fixed normalization divisor: 1e5 (kept for reference)
        self._legacy_norm = 1e5
        # Auto-gain tracking peak to adapt to varied loopback levels
        self._peak_energy = 1e-6
        self._init_stream()

    def _compute_ema_alpha(self, ema_ms):
        frame_ms = 1000 * self.buffer_size / self.sample_rate
        n = ema_ms / frame_ms
        return 1 - np.exp(-1 / n)

    def _init_stream(self):
        try:
            print("Available audio input devices:")
            for idx, dev in enumerate(sd.query_devices()):
                if dev['max_input_channels'] > 0:
                    print(f"  [{idx}] {dev['name']} (inputs: {dev['max_input_channels']})")
            target_device = self.device
            print(f"Attempting to open input device {target_device} for system audio loopback...")
            extra = None
            try:
                info = sd.query_devices(target_device)
                host = sd.query_hostapis(info['hostapi'])
                if host.get('type', '').lower() == 'wasapi':
                    extra = sd.WasapiSettings(loopback=True)
                    print("[AUDIO] Using WASAPI loopback")
            except Exception:
                extra = None
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=2,
                dtype='float32',
                blocksize=self.buffer_size,
                device=target_device,
                extra_settings=extra
            )
            self.stream.start()
            print("Audio stream started successfully.")
        except Exception as e:
            print(f"Audio stream init failed: {e}")
            self.stream = None

    def get_audio_energy(self):
        if self.stream is None:
            print("[AUDIO] No audio stream available. Returning zero motion.")
            return 0.0
        try:
            audio, _ = self.stream.read(self.buffer_size)
            # Mix stereo to mono
            mono = np.mean(audio, axis=1)
            # FFT
            fft = np.abs(scipy.fftpack.fft(mono))[:self.buffer_size // 2]
            freqs = np.fft.fftfreq(self.buffer_size, 1 / self.sample_rate)[:self.buffer_size // 2]
            # Bands
            low = np.sum(fft[(freqs >= 20) & (freqs < 150)])
            mid = np.sum(fft[(freqs >= 150) & (freqs < 2000)])
            energy_raw = 0.7 * low + 0.3 * mid
            # Auto-gain: track a decaying peak so quiet sources still animate
            self._peak_energy = max(self._peak_energy * 0.99, energy_raw)
            # Normalize to 0-200; legacy fixed divisor left in comment above
            energy = np.clip((energy_raw / max(self._peak_energy, 1e-6)) * 150, 0, 200)
            # Smooth
            self.last_energy = self.ema_alpha * energy + (1 - self.ema_alpha) * self.last_energy
            return self.last_energy
        except Exception as e:
            print(f"[AUDIO] Audio FFT failed: {e}")
            return 0.0
