import cv2
import requests
import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from ultralytics import YOLO
import asyncio
from fastapi.responses import StreamingResponse
import time
import threading

app = FastAPI()

# --- БАЗОВІ НАЛАШТУВАННЯ ---
CAM_URL = "http://192.168.0.116"
DEVKIT_IP = "192.168.0.128"
model = YOLO('best_int8_openvino_model', task='detect') 

# --- НАЛАШТУВАННЯ АВТОТРЕКІНГУ ---
TARGET_CLASS_ID = 3      # ID класу "танк" у твоїй моделі (зазвичай 0, якщо це єдиний клас)
CENTER_TOLERANCE = 40    # "Мертва зона" в пікселях. Якщо танк близько до центру, мотори не смикаються
KP_X = 0.04              # Коефіцієнт швидкості по осі X (підбирається тестами)
KP_Y = 0.04              # Коефіцієнт швидкості по осі Y

# Поточні кути моторів
current_angle_x = 90
current_angle_y = 90
last_request_time = 0    # Для обмеження спаму запитами на ESP32

HTML_CONTENT = """
<!DOCTYPE html>
<html>
    <head>
        <title>YOLOv8 Auto-Tracking</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body { text-align: center; font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: #eee; margin: 0; padding: 20px; }
            .container { max-width: 800px; margin: auto; }
            img { width: 100%; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); background: #000; }
            .status { margin-top: 15px; color: #00ff00; font-size: 18px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>AI Auto-Tracking (Tanks)</h2>
            <img src="/video_feed">
            <p class="status">● AUTOTRACKING ACTIVE</p>
            <p style="color:#888; font-size:14px;">Connected to ESP32: 192.168.0.113</p>
        </div>
    </body>
</html>
"""

# Функція для відправки команд на ESP32 у фоновому потоці
def send_movement_command(x, y):
    global last_request_time
    # Обмежуємо відправку до 10 разів на секунду, щоб не "завісити" ESP32 та STM32
    if time.time() - last_request_time < 0.1:
        return
    last_request_time = time.time()
    
    def do_request():
        try:
            # Звертаємося до оновленого endpoint-у /move?x=..&y=..
            requests.get(f"http://{DEVKIT_IP}/move?x={x}&y={y}", timeout=0.2)
        except:
            pass # Ігноруємо помилки мережі, щоб не крашити відеопотік
            
    threading.Thread(target=do_request).start()

async def video_generator():
    global current_angle_x, current_angle_y
    
    cap = cv2.VideoCapture(CAM_URL, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
    
    while True:
        success, frame = cap.read()
        if not success:
            await asyncio.sleep(0.1)
            continue
            
        # Отримуємо розміри кадру для вирахування ідеального центру
        frame_h, frame_w, _ = frame.shape
        center_x, center_y = frame_w // 2, frame_h // 2
        
        # Малюємо перехрестя прицілу в центрі кадру
        cv2.drawMarker(frame, (center_x, center_y), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)

        start_time = time.perf_counter()
        
        # YOLO розпізнавання
        results = model(frame, stream=True, verbose=False)
        target_found = False
        box_cx, box_cy = 0, 0
        
        for r in results:
            # Перебираємо всі знайдені об'єкти в кадрі
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id == TARGET_CLASS_ID:
                    # Отримуємо координати рамки танка
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    box_cx = int((x1 + x2) / 2)
                    box_cy = int((y1 + y2) / 2)
                    target_found = True
                    break # Беремо у фокус перший-ліпший танк у кадрі і виходимо з циклу
            
            frame = r.plot() # YOLO сама намалює кольорові рамки з відсотками
            
        inference_ms = (time.perf_counter() - start_time) * 1000
        # print(f"Інференс: {inference_ms:.1f} мс")

        # --- ЛОГІКА АВТОТРЕКІНГУ ---
        if target_found:
            # Малюємо лінію від центру екрана до цілі (візуалізація похибки)
            cv2.line(frame, (center_x, center_y), (box_cx, box_cy), (0, 255, 0), 2)
            
            # Вираховуємо похибку (на скільки пікселів ціль зміщена від центру)
            err_x = center_x - box_cx
            err_y = center_y - box_cy
            
            need_move = False
            
            # Коригування осі X (Поворот)
            if abs(err_x) > CENTER_TOLERANCE:
                # Якщо танк зліва, err_x позитивна -> збільшуємо кут (чи навпаки, залежить від збірки)
                current_angle_x += int(err_x * KP_X)
                current_angle_x = max(0, min(180, current_angle_x)) # Обмежуємо 0-180 градусів
                need_move = True
                
            # Коригування осі Y (Нахил)
            if abs(err_y) > CENTER_TOLERANCE:
                current_angle_y -= int(err_y * KP_Y) # Можливо тут потрібен "+", перевіриш на практиці
                current_angle_y = max(0, min(180, current_angle_y))
                need_move = True
                
            # Відправляємо нові кути на ESP32
            if need_move:
                send_movement_command(current_angle_x, current_angle_y)

        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        await asyncio.sleep(0.01)

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_CONTENT

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(video_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
