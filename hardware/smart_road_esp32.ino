/* Educational tabletop demo only. Never connect directly to public road systems.
  ESP32 DevKit, LDR+10k divider, 3.3V-compatible IR obstacle module.
  Wire: 3V3--LDR--GPIO34--10k--GND ; IR VCC->3V3, GND->GND, OUT->GPIO27.
  This LED/IR module usually pulls OUT LOW when it detects a toy-car obstacle.
*/
#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
// Run `ipconfig` on laptop, find its IPv4, replace 192.168.1.100
const char* SERVER_URL = "http://192.168.1.100:8000/sensor";
const char* DEMO_KEY = "change-this-secret";
const int LIGHT_PIN = 34;
const int IR_PIN = 27;
// Set demo coordinates in the app and here (the sample below is central Cairo).
const float LAT = 30.0444;
const float LON = 31.2357;

void setup() {
  Serial.begin(115200);
  pinMode(IR_PIN, INPUT);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  for (int i=0; i<30 && WiFi.status()!=WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("IP: "); Serial.println(WiFi.localIP());
}

void loop() {
  int lightRaw = analogRead(LIGHT_PIN);
  bool obstacle = (digitalRead(IR_PIN) == LOW);
  Serial.printf("light_raw=%d obstacle=%d\n", lightRaw, obstacle);
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Demo-Key", DEMO_KEY);
    String body = "{\"light_raw\":" + String(lightRaw)
                + ",\"obstacle\":" + String(obstacle ? "true" : "false")
                + ",\"latitude\":" + String(LAT, 5)
                + ",\"longitude\":" + String(LON, 5) + "}";
    int status = http.POST(body);
    Serial.printf("HTTP status = %d\n", status);
    http.end();
  }
  delay(5000);
}
