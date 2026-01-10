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
    'motion_energy': 0.0,
    'motion_speed': 0.15,
    'direction': 0,
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
        self.selected_audio_device = 0
        self.init_ui()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(200)

    def init_ui(self):
        import sounddevice as sd
        layout = QtWidgets.QVBoxLayout(self)

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
        audio_box = QtWidgets.QGroupBox("Audio Input Device")
        audio_layout = QtWidgets.QHBoxLayout()
        self.audio_combo = QtWidgets.QComboBox()
        self.audio_devices = [dev for dev in sd.query_devices() if dev['max_input_channels'] > 0]
        for idx, dev in enumerate(self.audio_devices):
            self.audio_combo.addItem(f"[{idx}] {dev['name']}")
        self.audio_combo.currentIndexChanged.connect(self.change_audio_device)
        audio_layout.addWidget(self.audio_combo)
        audio_box.setLayout(audio_layout)
        layout.addWidget(audio_box)

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

        # Motion graph
        self.motion_graph = MotionGraph()
        layout.addWidget(self.motion_graph)

        # Print devices at startup
        print("[AUDIO] Available devices:")
        for idx, dev in enumerate(self.audio_devices):
            print(f"  [{idx}] {dev['name']} (inputs: {dev['max_input_channels']})")

    def handle_update(self):
        idx = self.audio_combo.currentIndex()
        print(f"[GUI] Update pressed. Using audio device idx={idx}")
        with data_lock:
            data['audio_device_idx'] = idx

    def change_mode(self, idx):
        with data_lock:
            data['mode'] = idx + 1

    def change_audio_device(self, idx):
        self.selected_audio_device = idx
        with data_lock:
            data['audio_device_idx'] = idx
        import sounddevice as sd
        print("[AUDIO] Available devices (on change):")
        for i, dev in enumerate(sd.query_devices()):
            if dev['max_input_channels'] > 0:
                print(f"  [{i}] {dev['name']} (inputs: {dev['max_input_channels']})")

    def update_status(self):
        with data_lock:
            rgb = [int(x) for x in data['base_color']]
            mode = data['mode']
            motion = data['motion_energy']
            error_msg = data.get('error_msg', "")
        qcolor = QtGui.QColor(*rgb)
        pix = QtGui.QPixmap(60, 60)
        pix.fill(qcolor)
        self.color_label.setPixmap(pix)
        self.status_label.setText(f"Mode: {mode} | Color: {rgb} | Motion: {motion:.4f}")
        self.motion_graph.update_value(motion)
        self.error_label.setText(error_msg)


def screen_thread():
    cfg = Config()
    print("[SCREEN] Screen thread started")
    try:
        sampler = ScreenSampler(
            downscale_size=cfg.screen_downscale,
            crop_top=cfg.screen_crop_top,
            crop_bottom=cfg.screen_crop_bottom,
            ema_ms=cfg.screen_ema_ms,
        )
    except Exception as e:
        msg = f"ScreenSampler init failed: {e}"
        print(msg)
        with data_lock:
            data['error_msg'] = msg
        return
    last_color = np.array([0, 0, 0], dtype=np.float32)
    # EMA for motion 250ms at ~25Hz
    motion_alpha = 1 - np.exp(-1 / (250 / 40))
    motion_value = 0.0
    while True:
        try:
            color = sampler.get_screen_color()
            delta = np.abs(color - last_color).sum()
            screen_motion = np.clip(delta * 0.8, 0, 180)
            motion_value = motion_alpha * screen_motion + (1 - motion_alpha) * motion_value
            last_color = color
            with data_lock:
                data['base_color'] = color
                data['screen_motion_energy'] = motion_value
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
            energy = audio_fft.get_audio_energy()
            with data_lock:
                data['audio_motion_energy'] = energy
                if last_error and audio_fft.stream is not None:
                    data['error_msg'] = ""
                    last_error = ""
        except Exception as e:
            msg = f"Audio thread error: {e}"
            print(msg)
            with data_lock:
                data['error_msg'] = msg
            last_error = msg
        time.sleep(0.04)


def udp_thread():
    config = Config()
    mode_manager = ModeManager(config)
    udp_sender = UDPSender(config)
    while True:
        with data_lock:
            mode_manager.update_mode(data)
            packet = mode_manager.build_packet(data)
        udp_sender.send(packet)
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
