#include <WiFi.h>
#include <WiFiUdp.h>

// ======== CONFIG (LOCKED) ========
#define WIFI_SSID     "TP-Link_5ACC"
#define WIFI_PASSWORD "986678sv"

#define UDP_PORT      4210
#define PACKET_SIZE   12

#define HEADER_BYTE   0xAA
#define FOOTER_BYTE   0x55

#define PACKET_TIMEOUT_MS 1800  // 1.8s fallback trigger

// ======== MODE DEFINITIONS ========
enum Mode : uint8_t {
  MODE_MOVIE  = 1,
  MODE_MUSIC  = 2,
  MODE_HYBRID = 3,
  MODE_AMBIENT = 4,
  MODE_OFF    = 5
};

// ======== STATE ========
struct TargetState {
  uint8_t mode;
  uint8_t r, g, b;
  uint8_t brightness;
  uint8_t motion_energy;
  uint8_t motion_speed;
  uint8_t direction;
};

TargetState targetState;
unsigned long lastPacketTime = 0;

WiFiUDP udp;
uint8_t packetBuffer[PACKET_SIZE];

// ======== UTIL ========
uint8_t computeChecksum(const uint8_t* buf) {
  uint8_t cs = 0;
  for (int i = 1; i <= 9; i++) cs ^= buf[i];
  return cs;
}

void enterMode4Fallback() {
  targetState.mode = MODE_AMBIENT;
  // Values below are placeholders; rendering comes later
  targetState.r = 180;
  targetState.g = 160;
  targetState.b = 140;
  targetState.brightness = 60;
  targetState.motion_energy = 0;
  targetState.motion_speed = 0;
  targetState.direction = 128;

  Serial.println("[FALLBACK] Entered Mode 4 (Ambient Static)");
}

// ======== SETUP ========
void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("\n[BOOT] ESP32-WROOM starting");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("[WIFI] Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println("\n[WIFI] Connected");
  Serial.print("[WIFI] IP: ");
  Serial.println(WiFi.localIP());

  udp.begin(UDP_PORT);
  Serial.printf("[UDP] Listening on port %d\n", UDP_PORT);

  enterMode4Fallback();
  lastPacketTime = millis();
}

// ======== LOOP ========
void loop() {
  // --- UDP RECEIVE ---
  int packetSize = udp.parsePacket();
  if (packetSize == PACKET_SIZE) {
    udp.read(packetBuffer, PACKET_SIZE);

    bool valid =
      packetBuffer[0]  == HEADER_BYTE &&
      packetBuffer[11] == FOOTER_BYTE &&
      computeChecksum(packetBuffer) == packetBuffer[10];

    if (valid) {
      targetState.mode          = packetBuffer[1];
      targetState.r             = packetBuffer[2];
      targetState.g             = packetBuffer[3];
      targetState.b             = packetBuffer[4];
      targetState.brightness    = packetBuffer[5];
      targetState.motion_energy = packetBuffer[6];
      targetState.motion_speed  = packetBuffer[7];
      targetState.direction     = packetBuffer[8];

      lastPacketTime = millis();

      Serial.printf(
        "[PKT] Mode=%d RGB=(%d,%d,%d) Bright=%d MotionE=%d Speed=%d Dir=%d\n",
        targetState.mode,
        targetState.r, targetState.g, targetState.b,
        targetState.brightness,
        targetState.motion_energy,
        targetState.motion_speed,
        targetState.direction
      );
    } else {
      Serial.println("[PKT] Invalid packet dropped");
    }
  }

  // --- TIMEOUT CHECK ---
  if (millis() - lastPacketTime > PACKET_TIMEOUT_MS) {
    if (targetState.mode != MODE_AMBIENT) {
      enterMode4Fallback();
    }
  }

  // Rendering will be added in Phase 2
}
