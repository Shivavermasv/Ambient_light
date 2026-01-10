"""
gui.py
Tkinter GUI for controlling ESP32 Cinematic Ambient Cove Lighting application modes and monitoring status.
"""
import tkinter as tk
from tkinter import ttk
import threading
import time
import queue

# Shared state for GUI and main app
shared_data = {
    'mode': 1,
    'base_color': [0, 0, 0],
    'motion_energy': 0,
    'motion_speed': 0.15,
    'direction': 0,
    'brightness': 70
}

# For communication between GUI and main app
update_queue = queue.Queue()

class AmbientGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ambient Lighting Control Panel")
        self.geometry("400x300")
        self.resizable(False, False)
        self.create_widgets()
        self.after(100, self.update_status)

    def create_widgets(self):
        # Mode selection
        tk.Label(self, text="Select Mode:", font=("Arial", 12)).pack(pady=10)
        self.mode_var = tk.IntVar(value=shared_data['mode'])
        modes = [
            ("1: Movie Ambient", 1),
            ("2: Music/Work", 2),
            ("3: Hybrid", 3),
            ("4: Ambient Static", 4),
            ("5: OFF", 5)
        ]
        for text, val in modes:
            tk.Radiobutton(self, text=text, variable=self.mode_var, value=val, command=self.change_mode).pack(anchor='w')

        # Status display
        self.status_frame = tk.Frame(self)
        self.status_frame.pack(pady=15)
        self.mode_label = tk.Label(self.status_frame, text="Current Mode: 1", font=("Arial", 11))
        self.mode_label.pack()
        self.color_label = tk.Label(self.status_frame, text="Base Color: [0, 0, 0]", font=("Arial", 11))
        self.color_label.pack()
        self.motion_label = tk.Label(self.status_frame, text="Motion Energy: 0", font=("Arial", 11))
        self.motion_label.pack()

    def change_mode(self):
        new_mode = self.mode_var.get()
        shared_data['mode'] = new_mode
        update_queue.put(('mode', new_mode))
        self.mode_label.config(text=f"Current Mode: {new_mode}")

    def update_status(self):
        # Update status labels from shared_data
        self.mode_label.config(text=f"Current Mode: {shared_data['mode']}")
        self.color_label.config(text=f"Base Color: {list(map(int, shared_data['base_color']))}")
        self.motion_label.config(text=f"Motion Energy: {int(shared_data['motion_energy'])}")
        self.after(200, self.update_status)

def gui_thread():
    app = AmbientGUI()
    app.mainloop()

# For main.py integration:
def get_gui_shared_data():
    return shared_data, update_queue

if __name__ == "__main__":
    t = threading.Thread(target=gui_thread, daemon=True)
    t.start()
    # Example: update shared_data in a loop to simulate main app
    while True:
        # Simulate updates (remove in real integration)
        shared_data['base_color'] = [int(time.time()*10)%255, 100, 200]
        shared_data['motion_energy'] = int((time.time()*5)%180)
        time.sleep(0.5)
