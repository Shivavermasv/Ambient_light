"""
main.py
Entry point for ESP32 Cinematic Ambient Cove Lighting laptop application.
Strictly follows PROJECT_SPEC.md.
"""

import threading
import time
from config import Config
from mode_manager import ModeManager
from udp_sender import UDPSender
from screen.screen_sampler import ScreenSampler
from audio.audio_fft import AudioFFT
from signal_processing import smooth_motion

# Load configuration
config = Config()

# Initialize modules
mode_manager = ModeManager(config)
udp_sender = UDPSender(config)
screen_sampler = ScreenSampler()
audio_fft = AudioFFT()

# Shared state
data = {
    'base_color': [0, 0, 0],
    'motion_energy': 0,
    'motion_speed': 0.15,
    'direction': 0,
    'brightness': 70,
    'mode': 1
}

# Thread for screen sampling
def screen_thread():
    while True:
        color = screen_sampler.get_screen_color()
        data['base_color'] = color
        time.sleep(0.04)  # ~25Hz

# Thread for audio FFT
def audio_thread():
    while True:
        energy = audio_fft.get_audio_energy()
        data['motion_energy'] = energy
        time.sleep(0.04)

# Thread for UDP sending
def udp_thread():
    while True:
        packet = mode_manager.build_packet(data)
        udp_sender.send(packet)
        time.sleep(0.04)

# Start threads
threads = [
    threading.Thread(target=screen_thread, daemon=True),
    threading.Thread(target=audio_thread, daemon=True),
    threading.Thread(target=udp_thread, daemon=True)
]
for t in threads:
    t.start()

# Main loop: handle mode switching, fallback, etc.
try:
    while True:
        mode_manager.update_mode(data)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Exiting...")
