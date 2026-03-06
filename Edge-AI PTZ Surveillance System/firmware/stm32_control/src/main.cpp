#include <Arduino.h>
#include <Servo.h>

Servo panMotor;  // Вісь X (вліво-вправо)
Servo tiltMotor; // Вісь Y (вгору-вниз)

// D2 (RX) та D8 (TX) зайняті під отримання даних. Мотори туди не підключати!
HardwareSerial ESP_Serial(D2, D8); 

int currentAngleX = 90; // Поточна позиція X
int targetAngleX = 90;  // Цільова позиція X

int currentAngleY = 90; // Поточна позиція Y
int targetAngleY = 90;  // Цільова позиція Y

void setup() {
  pinMode(LED_BUILTIN, OUTPUT); 
  
  // Підключаємо мотори до відповідних пінів
  panMotor.attach(9);  // Встав жовтий/помаранчевий дріт осі X у пін D9
  tiltMotor.attach(3); // Встав жовтий/помаранчевий дріт осі Y у пін D3
  
  // Ставимо в центр при запуску
  panMotor.write(currentAngleX); 
  tiltMotor.write(currentAngleY); 
  
  ESP_Serial.begin(115200); 
  
  // Блимаємо діодом, сигналізуючи, що плата готова
  for(int i=0; i<3; i++) {
    digitalWrite(LED_BUILTIN, HIGH); delay(150);
    digitalWrite(LED_BUILTIN, LOW); delay(150);
  }
}

void loop() {
  // 1. Читаємо нову команду. Формат має бути "X,Y" (наприклад: "120,45\n")
  if (ESP_Serial.available() > 0) {
    String data = ESP_Serial.readStringUntil('\n'); 
    data.trim(); 
    
    if (data.length() > 0) {
      int commaIndex = data.indexOf(','); // Знаходимо кому, яка розділяє координати
      
      // Якщо кома є, розбиваємо рядок на два числа
      if (commaIndex > 0) {
        int newAngleX = data.substring(0, commaIndex).toInt(); 
        int newAngleY = data.substring(commaIndex + 1).toInt();
        
        // Захист моторів: оновлюємо ціль, тільки якщо кути в межах 0-180
        if (newAngleX >= 0 && newAngleX <= 180) targetAngleX = newAngleX;
        if (newAngleY >= 0 && newAngleY <= 180) targetAngleY = newAngleY;
        
        digitalWrite(LED_BUILTIN, HIGH); // Світимо діод, поки їдемо
      }
    }
  }

  // 2. Плавно крокуємо до цілі (одразу двома моторами)
  bool isMoving = false; // Прапорець, щоб знати, чи ми ще в русі

  // Рух по осі X
  if (currentAngleX != targetAngleX) {
    if (currentAngleX < targetAngleX) currentAngleX++;
    else currentAngleX--;
    panMotor.write(currentAngleX);
    isMoving = true;
  }

  // Рух по осі Y
  if (currentAngleY != targetAngleY) {
    if (currentAngleY < targetAngleY) currentAngleY++;
    else currentAngleY--;
    tiltMotor.write(currentAngleY);
    isMoving = true;
  }
  
  // Якщо хоча б один мотор зробив крок - робимо затримку
  if (isMoving) {
    delay(15); // Ті самі 15 мс для плавності
  } else {
    // Коли обидва мотори доїхали до цілі - гасимо діод
    digitalWrite(LED_BUILTIN, LOW); 
  }
}
