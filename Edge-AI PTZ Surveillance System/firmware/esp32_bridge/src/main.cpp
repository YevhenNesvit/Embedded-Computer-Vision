#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include "secrets.h"

// --- ТВОЇ НАЛАШТУВАННЯ WI-FI ---
const char* ssid = SECRET_WIFI_SSID;      
const char* password = SECRET_WIFI_PASS;

WebServer server(80);

void setup() {
  // Serial - для виводу інформації в монітор порту на ПК
  Serial.begin(115200);
  
  // Serial2 - для спілкування з STM32
  // На ESP32 пін TX2 - це зазвичай GPIO 17. З'єднуємо його з D2 на STM32.
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

  // НОВИЙ ЗАПИТ: http://ІП_АДРЕСА/move?x=КутX&y=КутY
  server.on("/move", []() {
    if (server.hasArg("x") && server.hasArg("y")) {
      String angleX = server.arg("x");
      String angleY = server.arg("y");
      
      // Склеюємо координати через кому
      String command = angleX + "," + angleY;
      
      // Відправляємо рядок "X,Y\n" на STM32
      Serial2.println(command); 
      
      Serial.println("Відправлено на STM32: " + command);
      server.send(200, "text/plain", "OK: " + command);
    } else {
      server.send(400, "text/plain", "Error: Missing x or y");
    }
  });

  server.begin();
}

void loop() {
  server.handleClient();
}