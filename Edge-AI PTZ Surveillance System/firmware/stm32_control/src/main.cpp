#include <Arduino.h>
#include <Servo.h>

Servo panMotor;  
HardwareSerial ESP_Serial(D2, D8); 

int currentAngle = 90; // Де ми зараз
int targetAngle = 90;  // Куди маємо приїхати

void setup() {
  pinMode(LED_BUILTIN, OUTPUT); 
  panMotor.attach(9); 
  panMotor.write(currentAngle); 
  
  ESP_Serial.begin(115200); 
  
  for(int i=0; i<3; i++) {
    digitalWrite(LED_BUILTIN, HIGH); delay(150);
    digitalWrite(LED_BUILTIN, LOW); delay(150);
  }
}

void loop() {
  // 1. Читаємо нову команду, якщо вона прийшла
  if (ESP_Serial.available() > 0) {
    String data = ESP_Serial.readStringUntil('\n'); 
    data.trim(); 
    
    if (data.length() > 0) {
      int newAngle = data.toInt(); 
      if (newAngle >= 0 && newAngle <= 180) {
        targetAngle = newAngle; // Оновлюємо ціль
        digitalWrite(LED_BUILTIN, HIGH); // Світимо діод, поки їдемо
      }
    }
  }

  // 2. Плавно крокуємо до цілі
  if (currentAngle != targetAngle) {
    if (currentAngle < targetAngle) currentAngle++;
    else currentAngle--;
    
    panMotor.write(currentAngle);
    
    // ⏳ Ця затримка визначає плавність. 
    // 15 мс - це стандартно. Зробиш 30 - буде їхати дуже повільно і плавно.
    delay(15); 
  } else {
    // Коли доїхали до цілі - гасимо діод
    digitalWrite(LED_BUILTIN, LOW); 
  }
}
