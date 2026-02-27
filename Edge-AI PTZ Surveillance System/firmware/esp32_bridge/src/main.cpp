#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include "secrets.h"

// --- ТВОЇ НАЛАШТУВАННЯ WI-FI ---
const char* ssid = SECRET_WIFI_SSID;      
const char* password = SECRET_WIFI_PASS;

WebServer server(80);

void setup() {
  // Serial - для виводу інформації в монітор порту на ПК (для дебагу)
  Serial.begin(115200);
  
  // Serial2 - для спілкування з STM32! 
  // На ESP32 пін TX2 - це зазвичай GPIO 17
  Serial2.begin(115200); 
  delay(10);

  WiFi.begin(ssid, password);
  Serial.print("Підключення до Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi підключено!");
  Serial.print("IP ESP32 DevKit: ");
  Serial.println(WiFi.localIP());

  // Чекаємо запит: http://ІП_АДРЕСА/pan?val=Кут
  server.on("/pan", []() {
    if (server.hasArg("val")) {
      String angle = server.arg("val");
      
      // Відправляємо число на STM32 і додаємо символ кінця рядка (\n)
      Serial2.println(angle); 
      
      Serial.println("Відправлено на STM32: " + angle);
      server.send(200, "text/plain", "OK: " + angle);
    } else {
      server.send(400, "text/plain", "Error: No value");
    }
  });

  server.begin();
}

void loop() {
  server.handleClient();
}
