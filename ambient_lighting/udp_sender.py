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

    def send(self, packet):
        # Sanity check: print packet once
        print("UDP Packet:", packet)
        try:
            self.sock.sendto(packet, (self.config.udp_ip, self.config.udp_port))
        except Exception as e:
            print(f"UDP send failed: {e}")
