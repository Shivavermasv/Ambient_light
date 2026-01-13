"""
udp_sender.py
Sends UDP packets to ESP32 for ambient lighting.
Strictly follows PROJECT_SPEC.md.
"""

import socket


class UDPSender:
    def __init__(self, config):
        self.config = config
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._last_debug_print = 0.0

    def send(self, packet):
        # Optional debug print (rate-limited)
        if getattr(self.config, 'debug_udp_packets', False):
            import time

            now = time.time()
            if now - self._last_debug_print > 1.0:
                print("UDP Packet:", packet)
                self._last_debug_print = now

        try:
            self.sock.sendto(packet, (self.config.udp_ip, self.config.udp_port))
        except Exception as e:
            print(f"UDP send failed: {e}")
