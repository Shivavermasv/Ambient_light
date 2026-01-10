"""
audio_fft_sanity.py
Manual sanity check for AudioFFT: prints bass_energy, mid_energy, final motion_energy.
Strictly follows PROJECT_SPEC.md.
"""
import numpy as np
import sounddevice as sd
import scipy.fftpack
import time

class AudioFFT:
    def __init__(self, sample_rate=44100, buffer_size=2048, ema_ms=100):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.ema_ms = ema_ms
        self.ema_alpha = self._compute_ema_alpha(ema_ms)
        self.last_energy = 0.0
        self.stream = None
        self._init_stream()

    def _compute_ema_alpha(self, ema_ms):
        frame_ms = 1000 * self.buffer_size / self.sample_rate
        n = ema_ms / frame_ms
        return 1 - np.exp(-1 / n)

    def _init_stream(self):
        try:
            self.stream = sd.InputStream(samplerate=self.sample_rate, channels=2, dtype='float32', blocksize=self.buffer_size, device=None)
            self.stream.start()
        except Exception as e:
            print(f"Audio stream init failed: {e}")
            self.stream = None

    def get_bass_mid_energy(self):
        if self.stream is None:
            return 0.0, 0.0, 0.0
        try:
            audio, _ = self.stream.read(self.buffer_size)
            mono = np.mean(audio, axis=1)
            fft = np.abs(scipy.fftpack.fft(mono))[:self.buffer_size // 2]
            freqs = np.fft.fftfreq(self.buffer_size, 1 / self.sample_rate)[:self.buffer_size // 2]
            bass_energy = np.sum(fft[(freqs >= 20) & (freqs < 150)])
            mid_energy = np.sum(fft[(freqs >= 150) & (freqs < 2000)])
            final_energy = 0.7 * bass_energy + 0.3 * mid_energy
            final_energy = np.clip(final_energy / 1e5, 0, 200)
            self.last_energy = self.ema_alpha * final_energy + (1 - self.ema_alpha) * self.last_energy
            return bass_energy, mid_energy, self.last_energy
        except Exception as e:
            print(f"Audio FFT failed: {e}")
            return 0.0, 0.0, 0.0

if __name__ == "__main__":
    fft = AudioFFT()
    while True:
        bass, mid, final = fft.get_bass_mid_energy()
        print(f"Bass energy: {bass}")
        print(f"Mid energy: {mid}")
        print(f"Final motion energy: {final}")
        time.sleep(0.04)
