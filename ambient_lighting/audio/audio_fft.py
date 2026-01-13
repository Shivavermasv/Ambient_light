"""audio_fft.py

Processes system audio and computes FFT-based energy for ambient lighting.

Key behaviors:
- Robust device opening: if a selected Windows device backend fails (often WDM-KS),
  automatically tries equivalent devices on WASAPI/DirectSound/MME.
- Silence stability: tracks a noise floor and subtracts it before auto-gain, so
  silence does not normalize to a high motion value.
"""

import time
import warnings

import numpy as np
import scipy.fftpack
import sounddevice as sd


class AudioFFT:
    def __init__(self, sample_rate=44100, buffer_size=2048, ema_ms=100, device=None):
        self.sample_rate = float(sample_rate)
        self.buffer_size = int(buffer_size)
        self.ema_ms = float(ema_ms)

        self.last_energy = 0.0
        self.stream = None
        self.device = device

        # If the selected device is Stereo Mix / WDM-KS on Windows, sounddevice can appear to
        # "open" but still deliver no callback data. Track preference so we can fail over.
        self._prefer_soundcard_loopback = False

        # Backend selection:
        # - 'sounddevice': normal InputStream capture
        # - 'soundcard': Windows loopback capture via soundcard (system audio)
        self._backend = 'sounddevice'
        self._sc_rec = None
        self.source_label = ""
        self.last_rms = 0.0

        # soundcard loopback recovery:
        # If Windows playback device changes (headphones/Bluetooth) the previously selected
        # loopback mic can become silent. Detect extended near-zero RMS and periodically
        # re-select/re-open loopback endpoints.
        self._sc_silence_since = None
        self._sc_last_reselect_time = 0.0
        self._sc_min_rms = 1e-4
        self._sc_silence_trigger_s = 3.0
        self._sc_reselect_min_interval_s = 5.0

        # soundcard read sizing:
        # Some Windows loopback endpoints return near-zeros for very small reads.
        # Read a minimum chunk and use it for FFT.
        self._sc_min_chunk_s = 0.10

        # Auto-gain tracking
        self._peak_energy_adj = 1e-6
        self._noise_floor_raw = None

        # Config-driven thresholds
        from config import Config

        cfg = Config()
        self.target_level = float(cfg.audio_target_level)
        self.hard_cap = float(cfg.audio_hard_cap)
        self.noise_gate = float(cfg.audio_noise_gate)
        self.noise_gate_hold = float(cfg.audio_noise_gate_hold_s)
        self._release_ms = float(cfg.audio_release_ms)

        self._last_active_time = time.time()
        self._last_init_attempt_time = 0.0

        self._latest_audio = None
        self._latest_audio_time = 0.0

        # soundcard may emit frequent discontinuity warnings on Windows.
        try:
            warnings.filterwarnings(
                "ignore",
                message="data discontinuity in recording",
                category=Warning,
            )
        except Exception:
            pass

        # Non-fatal init: allow app to run without audio.
        try:
            self._init_stream()
        except Exception:
            self.stream = None

    def _reset_signal_tracking(self):
        now = time.time()
        self.last_energy = 0.0
        self.last_rms = 0.0
        self._peak_energy_adj = 1e-6
        self._noise_floor_raw = None
        self._last_active_time = now
        self._latest_audio = None
        self._latest_audio_time = 0.0

    def close(self):
        try:
            if self._backend == 'soundcard' and self._sc_rec is not None:
                try:
                    # Recorder is a context manager.
                    self._sc_rec.__exit__(None, None, None)
                except Exception:
                    pass
                self._sc_rec = None
            if self.stream is not None:
                try:
                    if getattr(self.stream, "active", False):
                        self.stream.stop()
                except Exception:
                    pass
                try:
                    self.stream.close()
                except Exception:
                    pass
        finally:
            self.stream = None
            if self._sc_rec is None:
                self._backend = 'sounddevice'
            if self._backend == 'sounddevice':
                self.source_label = ""

    def _compute_ema_alpha_for_frame(self, ema_ms, frame_len):
        dt_ms = 1000.0 * float(frame_len) / float(self.sample_rate)
        tau_ms = float(max(ema_ms, 1e-3))
        return float(1.0 - np.exp(-dt_ms / tau_ms))

    def _audio_callback(self, indata, frames, time_info, status):
        try:
            self._latest_audio = np.array(indata, copy=True)
            self._latest_audio_time = time.time()
        except Exception:
            pass

    def _host_name_for_device(self, dev_info):
        try:
            host = sd.query_hostapis(dev_info["hostapi"])
            return str(host.get("name", ""))
        except Exception:
            return ""

    def _pick_default_input_device(self):
        try:
            default_in = sd.default.device[0]
        except Exception:
            default_in = None
        if default_in is not None and default_in != -1:
            return int(default_in)

        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            try:
                if int(dev.get("max_input_channels", 0) or 0) > 0:
                    return idx
            except Exception:
                continue
        raise RuntimeError("No usable audio input device found.")

    def _candidate_devices(self, device_idx):
        """Yield device indices to try, preferring stable Windows host APIs."""
        if device_idx is None:
            yield self._pick_default_input_device()
            return

        try:
            device_idx = int(device_idx)
        except Exception:
            # Could be a name or tuple; just try it.
            yield device_idx
            return

        devices = sd.query_devices()
        if device_idx < 0 or device_idx >= len(devices):
            yield self._pick_default_input_device()
            return

        base = devices[device_idx]
        base_name = str(base.get("name", "")).strip()

        yield device_idx

        preferred_hosts = ("WASAPI", "DirectSound", "MME")

        def _rank(h):
            h = str(h or "")
            for i, ph in enumerate(preferred_hosts):
                if ph.lower() in h.lower():
                    return i
            if "wdm-ks" in h.lower() or "wdm" in h.lower():
                return 99
            return 50

        # Same exact device name (common for Stereo Mix across host APIs)
        same_name = []
        if base_name:
            for idx, dev in enumerate(devices):
                if idx == device_idx:
                    continue
                if str(dev.get("name", "")).strip() != base_name:
                    continue
                if int(dev.get("max_input_channels", 0) or 0) <= 0:
                    continue
                same_name.append((idx, self._host_name_for_device(dev)))
        same_name.sort(key=lambda t: _rank(t[1]))
        for idx, _ in same_name:
            yield idx

        # If the base looks like Stereo Mix, also try fuzzy matches.
        if "stereo mix" in base_name.lower():
            fuzzy = []
            for idx, dev in enumerate(devices):
                if idx == device_idx:
                    continue
                name = str(dev.get("name", ""))
                if "stereo mix" not in name.lower():
                    continue
                if int(dev.get("max_input_channels", 0) or 0) <= 0:
                    continue
                fuzzy.append((idx, self._host_name_for_device(dev)))
            fuzzy.sort(key=lambda t: _rank(t[1]))
            for idx, _ in fuzzy:
                yield idx

        # Finally try the default input device.
        yield self._pick_default_input_device()

    def _init_stream(self):
        self._last_init_attempt_time = time.time()

        last_err = None
        chosen = None

        prefer_soundcard_on_request_failure = False
        requested_idx = None
        try:
            requested_idx = int(self.device) if self.device is not None else None
        except Exception:
            requested_idx = None

        if requested_idx is not None:
            try:
                devices = sd.query_devices()
                if 0 <= requested_idx < len(devices):
                    base = devices[requested_idx]
                    base_name = str(base.get("name", ""))
                    host_name = self._host_name_for_device(base)
                    if "stereo mix" in base_name.lower() or "wdm-ks" in host_name.lower():
                        prefer_soundcard_on_request_failure = True
                        self._prefer_soundcard_loopback = True
            except Exception:
                pass

        # If user selected a known-problematic Windows input (Stereo Mix on WDM-KS),
        # prefer system loopback capture immediately when available.
        if self._prefer_soundcard_loopback:
            if self._try_init_soundcard_loopback():
                self._reset_signal_tracking()
                return

        for cand in self._candidate_devices(self.device):
            try:
                info = sd.query_devices(cand)
                host_name = self._host_name_for_device(info)
                max_in = int(info.get("max_input_channels", 0) or 0)
                max_out = int(info.get("max_output_channels", 0) or 0)

                use_loopback = False
                if "wasapi" in host_name.lower() and max_in <= 0 and max_out > 0:
                    use_loopback = True

                extra = None
                if use_loopback:
                    try:
                        extra = sd.WasapiSettings(loopback=True)
                    except Exception as e:
                        raise RuntimeError(
                            "WASAPI loopback not available in this sounddevice build. "
                            "Select an input device like 'Stereo Mix'."
                        ) from e

                if use_loopback:
                    channels = 2 if max_out >= 2 else 1
                else:
                    channels = 2 if max_in >= 2 else 1 if max_in >= 1 else 0
                if channels <= 0:
                    raise RuntimeError(
                        f"Device has no input channels and loopback unavailable: in={max_in} out={max_out} host='{host_name}'"
                    )

                loopback_note = " (WASAPI loopback)" if use_loopback else ""
                print(
                    f"[AUDIO] Opening device {cand}: '{info.get('name', '')}' host='{host_name}' in={max_in} out={max_out}{loopback_note}"
                )

                self.close()

                desired_sr = float(self.sample_rate)
                default_sr = float(info.get("default_samplerate", desired_sr) or desired_sr)

                def _try_open(sr, bs):
                    self.stream = sd.InputStream(
                        samplerate=sr,
                        channels=channels,
                        dtype="float32",
                        blocksize=bs,
                        device=cand,
                        extra_settings=extra,
                        callback=self._audio_callback,
                    )
                    self.stream.start()

                attempts = [
                    (desired_sr, int(self.buffer_size)),
                    (default_sr, int(self.buffer_size)),
                    (default_sr, 0),
                    (desired_sr, 0),
                ]

                opened = False
                for sr, bs in attempts:
                    try:
                        _try_open(sr, bs)
                        if sr != desired_sr:
                            self.sample_rate = float(sr)
                        print(f"[AUDIO] Audio stream started successfully (sr={sr}, blocksize={bs if bs else 'default'}).")
                        opened = True
                        break
                    except Exception as e:
                        last_err = e
                        self.stream = None

                if opened:
                    chosen = cand
                    try:
                        self.source_label = f"sounddevice:{info.get('name','')} ({host_name})"
                    except Exception:
                        self.source_label = "sounddevice"
                    break
                else:
                    # If the user explicitly requested Stereo Mix (often WDM-KS) and it won't open,
                    # prefer real system-audio loopback over falling back to a microphone.
                    if prefer_soundcard_on_request_failure and requested_idx is not None and cand == requested_idx:
                        if self._try_init_soundcard_loopback():
                            return

            except Exception as e:
                last_err = e
                self.stream = None
                continue

        if chosen is None:
            # If Stereo Mix is only exposed via WDM-KS, PortAudio frequently can't open it.
            # Fall back to system-audio loopback capture via 'soundcard'.
            if self._try_init_soundcard_loopback():
                return
            raise last_err if last_err is not None else RuntimeError("Failed to open audio device.")

        if self.device != chosen:
            print(f"[AUDIO] Fallback: requested device {self.device} -> using device {chosen}.")
        self.device = chosen
        self._backend = 'sounddevice'

    def _try_init_soundcard_loopback(self):
        """Try to initialize loopback capture using 'soundcard' (Windows system audio)."""
        try:
            import soundcard as sc
        except Exception:
            return False

        try:
            speaker = sc.default_speaker()

            # In this soundcard (MediaFoundation) backend, loopback is exposed as a
            # loopback microphone when include_loopback=True.
            try:
                all_mics = list(sc.all_microphones(include_loopback=True))
            except Exception:
                all_mics = []

            loopback_mics = [m for m in all_mics if "loopback" in str(m).lower()]
            if not loopback_mics:
                return False

            # Prefer the loopback endpoint for the default speaker (but probe others too).
            preferred = []
            try:
                mic_for_speaker = sc.get_microphone(speaker.name, include_loopback=True)
                if mic_for_speaker is not None:
                    preferred.append(mic_for_speaker)
            except Exception:
                pass

            candidates = []
            seen = set()
            for m in preferred + loopback_mics:
                key = str(m)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(m)

            print(f"[AUDIO] soundcard loopback candidates: {[str(m) for m in candidates]}")

            # Try common sample rates.
            best = None
            best_rms = -1.0
            best_sr = None
            fallback = None

            for sr in (int(self.sample_rate), 48000, 44100):
                sr = int(sr)
                for mic in candidates:
                    rec = None
                    try:
                        rec = mic.recorder(samplerate=sr, channels=2)
                        rec.__enter__()
                        # Probe a modest chunk to avoid selecting an endpoint that returns zeros for
                        # short reads (observed on Windows loopback).
                        probe_frames = int(max(2048, sr * 0.20))
                        chunk = rec.record(probe_frames)
                        arr = np.asarray(chunk, dtype=np.float32)
                        rms = float(np.sqrt(np.mean(np.square(arr))) + 0.0)

                        if fallback is None:
                            fallback = (rec, mic, sr, rms)

                        if rms > best_rms:
                            if best is not None:
                                try:
                                    best[0].__exit__(None, None, None)
                                except Exception:
                                    pass
                            best = (rec, mic, sr, rms)
                            best_rms = rms
                            best_sr = sr
                        else:
                            try:
                                rec.__exit__(None, None, None)
                            except Exception:
                                pass
                    except Exception:
                        if rec is not None:
                            try:
                                rec.__exit__(None, None, None)
                            except Exception:
                                pass
                        continue

            chosen = best if best is not None else fallback
            if chosen is None:
                return False

            rec, mic, sr, rms = chosen
            self._sc_rec = rec
            self._backend = 'soundcard'
            self.sample_rate = float(sr)
            self.source_label = f"soundcard:{mic}"
            self.last_rms = float(rms)
            self._sc_silence_since = None
            print(f"[AUDIO] Using soundcard loopback mic: {mic} (sr={sr}, probe_rms={rms:.6f}).")
            return True
        except Exception:
            return False
        return False

    def _maybe_reselect_soundcard_loopback(self, now, rms):
        """If loopback has been silent for a while, re-open loopback endpoints."""
        try:
            rms = float(rms)
        except Exception:
            rms = 0.0

        if rms >= self._sc_min_rms:
            self._sc_silence_since = None
            return False

        if self._sc_silence_since is None:
            self._sc_silence_since = now
            return False

        if (now - self._sc_silence_since) < self._sc_silence_trigger_s:
            return False

        if (now - self._sc_last_reselect_time) < self._sc_reselect_min_interval_s:
            return False

        self._sc_last_reselect_time = now
        print("[AUDIO] Loopback RMS near zero for extended time; re-selecting soundcard loopback endpoint...")

        # Full reopen: close existing recorder and pick best loopback mic again.
        try:
            self.close()
        except Exception:
            pass
        self._reset_signal_tracking()
        ok = self._try_init_soundcard_loopback()
        return bool(ok)

    def _compute_centroid(self, freqs, mags):
        denom = float(np.sum(mags) + 1e-9)
        return float(np.sum(freqs * mags) / denom)

    def get_audio_features(self):
        # soundcard backend doesn't use a sounddevice stream; avoid treating that as an error.
        if self._backend == 'soundcard' and self._sc_rec is not None:
            pass
        elif self.stream is None:
            now = time.time()
            if now - self._last_init_attempt_time > 1.0:
                try:
                    self._init_stream()
                except Exception:
                    pass
            if self.stream is None and self._backend != 'soundcard':
                return {"energy": 0.0, "bass": 0.0, "mid": 0.0, "centroid": 0.0}

        try:
            now = time.time()
            if self._backend == 'soundcard':
                if self._sc_rec is None:
                    return {"energy": 0.0, "bass": 0.0, "mid": 0.0, "centroid": 0.0}
                min_frames = int(max(self.buffer_size, self.sample_rate * float(self._sc_min_chunk_s)))
                audio = self._sc_rec.record(min_frames)
                # soundcard returns float64 in [-1,1]; make it consistent.
                audio = np.asarray(audio, dtype=np.float32)
                if audio.ndim == 1:
                    audio = audio.reshape(-1, 1)
                try:
                    self.last_rms = float(np.sqrt(np.mean(np.square(audio))) + 0.0)
                except Exception:
                    self.last_rms = 0.0

                # If system audio route changes, the previously selected loopback can go silent.
                # Periodically reselect endpoints in that case.
                if self._maybe_reselect_soundcard_loopback(now, self.last_rms):
                    return self.get_audio_features()
            else:
                try:
                    if not getattr(self.stream, "active", True):
                        self.stream.start()
                except Exception:
                    self.close()
                    self._init_stream()
                    if self.stream is None and self._backend != 'soundcard':
                        return {"energy": 0.0, "bass": 0.0, "mid": 0.0, "centroid": 0.0}

                audio = self._latest_audio
                if audio is None:
                    # No callback data yet; try switching to loopback if this looks like a Stereo Mix/WDM-KS selection.
                    if self._prefer_soundcard_loopback and self._try_init_soundcard_loopback():
                        self._reset_signal_tracking()
                        return self.get_audio_features()
                    return {"energy": 0.0, "bass": 0.0, "mid": 0.0, "centroid": 0.0}
                if time.time() - (self._latest_audio_time or 0.0) > 0.5:
                    # Stream is "alive" but delivering stale/no data (common with WDM-KS).
                    if self._prefer_soundcard_loopback and self._try_init_soundcard_loopback():
                        self._reset_signal_tracking()
                        return self.get_audio_features()
                    # Otherwise, force a re-init attempt.
                    try:
                        self.close()
                        self._init_stream()
                    except Exception:
                        pass
                    return {"energy": 0.0, "bass": 0.0, "mid": 0.0, "centroid": 0.0}

            mono = np.mean(audio, axis=1)
            n = int(len(mono))
            if n < 64:
                return {"energy": 0.0, "bass": 0.0, "mid": 0.0, "centroid": 0.0}

            fft = np.abs(scipy.fftpack.fft(mono))[: n // 2]
            freqs = np.fft.fftfreq(n, 1 / self.sample_rate)[: n // 2]

            low = float(np.sum(fft[(freqs >= 20) & (freqs < 150)]))
            mid = float(np.sum(fft[(freqs >= 150) & (freqs < 2000)]))
            centroid = self._compute_centroid(freqs, fft)

            energy_raw = 0.7 * low + 0.3 * mid

            # Noise-floor subtraction so silence stays near 0.
            if self._noise_floor_raw is None:
                self._noise_floor_raw = float(energy_raw)
            nf = float(self._noise_floor_raw)
            er = float(energy_raw)
            if er < nf:
                nf = er
            else:
                near_floor = er < (nf * 1.30 + 1e-9)
                alpha = 0.01 if near_floor else 0.0005
                nf = (1.0 - alpha) * nf + alpha * er
            self._noise_floor_raw = nf

            er_adj = max(0.0, er - nf * 1.10)
            self._peak_energy_adj = max(self._peak_energy_adj * 0.995, er_adj)
            if self._peak_energy_adj < 1e-9:
                energy = 0.0
            else:
                energy = (er_adj / max(self._peak_energy_adj, 1e-9)) * self.target_level

            energy = float(np.clip(energy, 0.0, self.hard_cap))

            if energy > self.noise_gate:
                self._last_active_time = now
            elif now - self._last_active_time > self.noise_gate_hold:
                energy = 0.0

            attack_alpha = self._compute_ema_alpha_for_frame(self.ema_ms, n)
            release_alpha = self._compute_ema_alpha_for_frame(self._release_ms, n)
            energy_slow = attack_alpha * energy + (1 - attack_alpha) * self.last_energy
            self.last_energy = energy_slow if energy > self.last_energy else release_alpha * energy + (1 - release_alpha) * self.last_energy

            return {
                "energy": float(self.last_energy),
                "bass": low,
                "mid": mid,
                "centroid": float(centroid),
            }

        except Exception as e:
            print(f"[AUDIO] Audio FFT failed: {e}")
            if "Stream is stopped" in str(e):
                self.close()
                try:
                    self._init_stream()
                except Exception:
                    pass
            return {"energy": 0.0, "bass": 0.0, "mid": 0.0, "centroid": 0.0}

    def get_audio_energy(self):
        return self.get_audio_features().get("energy", 0.0)
