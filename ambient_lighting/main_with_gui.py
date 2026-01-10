"""
main_with_gui.py
Runs the ambient lighting application with a Tkinter GUI for live mode control and status monitoring.
"""
import threading
import time
from config import Config
from mode_manager import ModeManager
from udp_sender import UDPSender
from screen.screen_sampler import ScreenSampler
from audio.audio_fft import AudioFFT
from signal_processing import smooth_motion
from gui import get_gui_shared_data, gui_thread

# Get shared state and update queue from GUI
shared_data, update_queue = get_gui_shared_data()

# Load configuration
config = Config()

# Initialize modules
mode_manager = ModeManager(config)
udp_sender = UDPSender(config)
screen_sampler = ScreenSampler()
audio_fft = AudioFFT()

# Thread for screen sampling
def screen_thread():
    while True:
        color = screen_sampler.get_screen_color()
        shared_data['base_color'] = color
        time.sleep(0.04)  # ~25Hz

# Thread for audio FFT
def audio_thread():
    while True:
        energy = audio_fft.get_audio_energy()
        shared_data['motion_energy'] = energy
        time.sleep(0.04)

# Thread for UDP sending
def udp_thread():
    while True:
        # Mode can be changed by GUI
        packet = mode_manager.build_packet(shared_data)
        udp_sender.send(packet)
        time.sleep(0.04)

# Thread to process GUI update queue (if needed for future expansion)
def gui_update_thread():
    while True:
        try:
            while not update_queue.empty():
                key, value = update_queue.get()
                shared_data[key] = value
        except Exception:
            pass
        time.sleep(0.1)

# Start GUI in main thread, background logic in threads
def main():
    threads = [
        threading.Thread(target=screen_thread, daemon=True),
        threading.Thread(target=audio_thread, daemon=True),
        threading.Thread(target=udp_thread, daemon=True),
        threading.Thread(target=gui_update_thread, daemon=True)
    ]
    for t in threads:
        t.start()
    gui_thread()  # This blocks until GUI is closed

if __name__ == "__main__":
    main()
