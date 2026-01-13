"""
main_desktop.py
PyQt5 Desktop App for ESP32 Cinematic Ambient Cove Lighting
- Live mode control
- Color preview
- Real-time motion energy graph
- Status display
"""
import sys
import threading
import time
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
from config import Config
from mode_manager import ModeManager
from udp_sender import UDPSender
from screen.screen_sampler import ScreenSampler
from audio.audio_fft import AudioFFT

data_lock = threading.Lock()

# Shared state
data = {
    'base_color': [0, 0, 0],
    'screen_motion_energy': 0.0,
    'audio_motion_energy': 0.0,
    'audio_bass': 0.0,
    'audio_mid': 0.0,
    'audio_centroid': 0.0,
    'motion_energy': 0.0,
    'motion_speed': 0.15,
    # Direction hint encoded as ~32 (left), 128 (center/neutral), ~224 (right)
    'direction': 128,
    'brightness': 70,
    'mode': 1,
    'audio_device_idx': 0,
    'error_msg': ""
}


class MotionGraph(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = [0] * 100
        self.setMinimumHeight(60)

    def update_value(self, v):
        self.values.append(v)
        if len(self.values) > 100:
            self.values.pop(0)
        self.update()

    def paintEvent(self, event):
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        qp.fillRect(0, 0, w, h, QtGui.QColor(30, 30, 30))
        if len(self.values) < 2:
            return
        pen = QtGui.QPen(QtGui.QColor(0, 200, 255), 2)
        qp.setPen(pen)
        points = [QtCore.QPointF(i * w / 100, h - min(v, 200) / 200 * h) for i, v in enumerate(self.values)]
        for i in range(1, len(points)):
            qp.drawLine(points[i - 1], points[i])


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ambient Lighting Control Panel")
        self.setFixedSize(520, 460)
        self.init_ui()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(200)

    def init_ui(self):
        import sounddevice as sd
        layout = QtWidgets.QVBoxLayout(self)

        # Warn early if soundcard isn't available (Mode 2 system-audio capture depends on it on Windows).
        try:
            import soundcard  # noqa: F401
            self._soundcard_available = True
        except Exception:
            self._soundcard_available = False

        # Mode selection
        mode_box = QtWidgets.QGroupBox("Select Mode")
        mode_layout = QtWidgets.QHBoxLayout()
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems([
            "1: Movie Ambient",
            "2: Music/Work",
            "3: Hybrid",
            "4: Ambient Static",
            "5: OFF"
        ])
        self.mode_combo.currentIndexChanged.connect(self.change_mode)
        mode_layout.addWidget(self.mode_combo)
        mode_box.setLayout(mode_layout)
        layout.addWidget(mode_box)

        # Audio device selection
        audio_box = QtWidgets.QGroupBox("Audio Device (Input or WASAPI Loopback)")
        audio_layout = QtWidgets.QHBoxLayout()
        self.audio_combo = QtWidgets.QComboBox()
        # IMPORTANT: store real sounddevice device indices (not re-indexed list)
        self.audio_devices = sd.query_devices()
        preferred_combo_index = None

        loopback_supported = False
        try:
            _ = sd.WasapiSettings(loopback=True)
            loopback_supported = True
        except Exception:
            loopback_supported = False

        for dev_idx, dev in enumerate(self.audio_devices):
            in_ch = dev.get('max_input_channels', 0)
            out_ch = dev.get('max_output_channels', 0)
            if in_ch <= 0 and out_ch <= 0:
                continue
            host_name = ""
            try:
                hostapi = dev.get('hostapi', None)
                if hostapi is not None:
                    host_name = sd.query_hostapis(hostapi).get('name', '')
            except Exception:
                host_name = ""
            label = f"[{dev_idx}] {dev['name']} (in:{in_ch} out:{out_ch}{' ' + host_name if host_name else ''})"
            self.audio_combo.addItem(label, userData=dev_idx)

            # Prefer a WASAPI output device for loopback only if supported by sounddevice.
            if preferred_combo_index is None and loopback_supported:
                if out_ch > 0 and 'wasapi' in str(host_name).lower():
                    preferred_combo_index = self.audio_combo.count() - 1

            # Otherwise, prefer stable *input* devices (DirectSound/MME tend to work broadly).
            if preferred_combo_index is None:
                if in_ch > 0 and ('directsound' in str(host_name).lower()):
                    preferred_combo_index = self.audio_combo.count() - 1
            if preferred_combo_index is None:
                if in_ch > 0 and (str(host_name).strip().lower() == 'mme'):
                    preferred_combo_index = self.audio_combo.count() - 1
        self.audio_combo.currentIndexChanged.connect(self.change_audio_device)
        audio_layout.addWidget(self.audio_combo)
        audio_box.setLayout(audio_layout)
        layout.addWidget(audio_box)

        if preferred_combo_index is not None:
            self.audio_combo.setCurrentIndex(preferred_combo_index)
            # Ensure shared state matches UI at startup.
            dev_idx = self.audio_combo.currentData()
            if dev_idx is not None:
                with data_lock:
                    data['audio_device_idx'] = int(dev_idx)

        # Update button
        self.update_button = QtWidgets.QPushButton("Update")
        self.update_button.clicked.connect(self.handle_update)
        layout.addWidget(self.update_button)

        # Color preview
        color_box = QtWidgets.QGroupBox("Current Base Color")
        color_layout = QtWidgets.QHBoxLayout()
        self.color_label = QtWidgets.QLabel()
        self.color_label.setFixedSize(60, 60)
        color_layout.addWidget(self.color_label)
        color_box.setLayout(color_layout)
        layout.addWidget(color_box)

        # Status and error
        self.status_label = QtWidgets.QLabel("Status: ...")
        layout.addWidget(self.status_label)
        self.error_label = QtWidgets.QLabel("")
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label)

        if not self._soundcard_available:
            warn = (
                "Warning: 'soundcard' is not installed. On Windows, Mode 2 system-audio capture "
                "may stay at 0. Install it in your selected interpreter / venv."
            )
            print("[AUDIO] " + warn)
            self.error_label.setText(warn)

        # Motion graph
        self.motion_graph = MotionGraph()
        layout.addWidget(self.motion_graph)

        # Print devices at startup (short)
        try:
            print("[AUDIO] Devices (in/out):")
            for idx, dev in enumerate(sd.query_devices()):
                in_ch = dev.get('max_input_channels', 0)
                out_ch = dev.get('max_output_channels', 0)
                if in_ch > 0 or out_ch > 0:
                    print(f"  [{idx}] {dev['name']} (in:{in_ch} out:{out_ch})")
        except Exception:
            pass

    def handle_update(self):
        dev_idx = self.audio_combo.currentData()
        if dev_idx is None:
            dev_idx = 0
        print(f"[GUI] Update pressed. Using audio device idx={dev_idx}")
        with data_lock:
            data['audio_device_idx'] = int(dev_idx)

    def change_mode(self, idx):
        with data_lock:
            data['mode'] = idx + 1

    def change_audio_device(self, idx):
        dev_idx = self.audio_combo.itemData(idx)
        if dev_idx is None:
            dev_idx = 0
        with data_lock:
            data['audio_device_idx'] = int(dev_idx)
        try:
            import sounddevice as sd
            dev = sd.query_devices()[int(dev_idx)]
            print(f"[GUI] Selected audio device idx={dev_idx}: {dev.get('name','')}")
        except Exception:
            print(f"[GUI] Selected audio device idx={dev_idx}")

    def update_status(self):
        with data_lock:
            rgb = [int(x) for x in data['base_color']]
            mode = data['mode']
            motion = data['motion_energy']
            audio_motion = data.get('audio_motion_energy', 0.0)
            audio_dev = data.get('audio_device_idx', 0)
            audio_backend = data.get('audio_backend', '')
            audio_source = data.get('audio_source', '')
            audio_rms = data.get('audio_rms', 0.0)
            error_msg = data.get('error_msg', "")
        qcolor = QtGui.QColor(*rgb)
        pix = QtGui.QPixmap(60, 60)
        pix.fill(qcolor)
        self.color_label.setPixmap(pix)
        src = audio_backend
        if audio_backend and audio_source:
            src = audio_source
        if src:
            self.status_label.setText(
                f"Mode: {mode} | Color: {rgb} | Motion: {motion:.2f} | Audio: {audio_motion:.2f} | Dev: {audio_dev} | Src: {src} | RMS: {audio_rms:.4f}"
            )
        else:
            self.status_label.setText(
                f"Mode: {mode} | Color: {rgb} | Motion: {motion:.2f} | Audio: {audio_motion:.2f} | Dev: {audio_dev}"
            )
        self.motion_graph.update_value(motion)
        self.error_label.setText(error_msg)


def screen_thread():
    cfg = Config()
    print("[SCREEN] Screen thread started")
    try:
        desat_amount = cfg.desat_amount if cfg.enable_desat_reduction else 0.12
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
    except Exception as e:
        msg = f"ScreenSampler init failed: {e}"
        print(msg)
        with data_lock:
            data['error_msg'] = msg
        return
    last_color = np.array([0, 0, 0], dtype=np.float32)
    # Motion EMA: keep a single ~180ms smoothing stage total.
    motion_alpha = 1 - np.exp(-1 / (180 / 40))
    motion_value = 0.0

    # Direction hysteresis for spatial bias: require stable dominant region for N frames.
    stable_frames_required = 3
    last_dom_idx = None
    dom_streak = 0
    stable_dom_idx = None
    while True:
        try:
            with data_lock:
                current_mode = data.get('mode', 1)

            if cfg.enable_spatial_bias and current_mode != 2:
                color, region_colors, region_weights = sampler.get_screen_data(regions=cfg.spatial_regions)
                # pick dominant region by weight
                if region_weights and max(region_weights) > 0:
                    idx = int(np.argmax(region_weights))

                    if last_dom_idx is None or idx != last_dom_idx:
                        last_dom_idx = idx
                        dom_streak = 1
                    else:
                        dom_streak += 1
                    if dom_streak >= stable_frames_required:
                        stable_dom_idx = idx

                    dom_color = region_colors[idx] if region_colors[idx] is not None else color
                    blend = cfg.spatial_bias_blend
                    color = (1 - blend) * color + blend * dom_color
                    # set direction hint based on region (0:left, 1:center, 2:right)
                    if cfg.spatial_regions >= 3:
                        dir_map = {0: 32, 1: 128, 2: 224}
                        use_idx = stable_dom_idx if stable_dom_idx is not None else idx
                        direction = dir_map.get(use_idx, 128)
                    else:
                        direction = 128
                else:
                    direction = 128
            else:
                color = sampler.get_screen_color()
                direction = 128
            delta = np.abs(color - last_color).sum()
            screen_motion = np.clip(delta * 0.8, 0, 180)
            motion_value = motion_alpha * screen_motion + (1 - motion_alpha) * motion_value
            last_color = color
            with data_lock:
                if current_mode != 2:  # Mode 2 color comes from audio downstream
                    data['base_color'] = color
                data['screen_motion_energy'] = motion_value
                data['direction'] = direction
                data['error_msg'] = ""
        except Exception as e:
            msg = f"Screen thread error: {e}"
            print(msg)
            with data_lock:
                data['error_msg'] = msg
        time.sleep(0.04)


def audio_thread():
    import sounddevice as sd
    cfg = Config()
    last_device_idx = None
    audio_fft = None
    last_error = ""
    while True:
        try:
            with data_lock:
                device_idx = data.get('audio_device_idx', 0)
            if device_idx != last_device_idx or audio_fft is None:
                try:
                    if audio_fft is not None:
                        try:
                            audio_fft.close()
                        except Exception:
                            pass
                    dev = sd.query_devices()[device_idx]
                    print(f"[AUDIO] Using device: {dev['name']}")
                    audio_fft = AudioFFT(sample_rate=cfg.audio_sample_rate, buffer_size=cfg.audio_buffer_size, ema_ms=cfg.audio_ema_ms, device=device_idx)
                    last_device_idx = device_idx
                except Exception as e:
                    msg = f"Audio device error: {e}"
                    print(msg)
                    with data_lock:
                        data['error_msg'] = msg
                    last_error = msg
                    time.sleep(1)
                    continue
            # If stream failed to open (or was lost), force re-init.
            if audio_fft is not None and getattr(audio_fft, 'stream', None) is None:
                if getattr(audio_fft, '_backend', 'sounddevice') == 'soundcard':
                    # soundcard backend doesn't create a sounddevice stream.
                    pass
                else:
                    audio_fft = None
                    time.sleep(0.2)
                    continue
            features = audio_fft.get_audio_features()
            with data_lock:
                data['audio_motion_energy'] = features.get('energy', 0.0)
                data['audio_bass'] = features.get('bass', 0.0)
                data['audio_mid'] = features.get('mid', 0.0)
                data['audio_centroid'] = features.get('centroid', 0.0)

                # Telemetry for debugging intermittent Mode 2 failures.
                data['audio_backend'] = getattr(audio_fft, '_backend', '') or ''
                data['audio_source'] = getattr(audio_fft, 'source_label', '') or ''
                data['audio_rms'] = float(getattr(audio_fft, 'last_rms', 0.0) or 0.0)

                healthy = False
                if getattr(audio_fft, '_backend', 'sounddevice') == 'soundcard':
                    healthy = getattr(audio_fft, '_sc_rec', None) is not None
                else:
                    healthy = audio_fft.stream is not None
                if last_error and healthy:
                    data['error_msg'] = ""
                    last_error = ""
        except Exception as e:
            msg = f"Audio thread error: {e}"
            print(msg)
            with data_lock:
                data['error_msg'] = msg
            last_error = msg
            audio_fft = None  # force re-init on next loop
        time.sleep(0.04)


def udp_thread():
    config = Config()
    mode_manager = ModeManager(config)
    udp_sender = UDPSender(config)
    while True:
        try:
            with data_lock:
                mode_manager.update_mode(data)
                packet = mode_manager.build_packet(data)
            udp_sender.send(packet)
        except Exception as e:
            msg = f"UDP thread error: {e}"
            print(msg)
            with data_lock:
                data['error_msg'] = msg
            time.sleep(0.2)
        time.sleep(0.04)


def main():
    threads = [
        threading.Thread(target=screen_thread, daemon=True),
        threading.Thread(target=audio_thread, daemon=True),
        threading.Thread(target=udp_thread, daemon=True),
    ]
    for t in threads:
        t.start()
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
