# Change Summary

- Startup fallback no longer forces the app into mode 4 immediately; fallback still triggers after >1.8s of no packets but is non-sticky. (mode_manager.py)
- Audio FFT now uses an auto-gain peak tracker to normalize motion energy for quiet loopback sources. Legacy fixed divisor `energy_raw / 1e5` is noted in code for rollback. (audio/audio_fft.py)
