import cv2
import requests
import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from ultralytics import YOLO
import asyncio
from fastapi.responses import StreamingResponse

app = FastAPI()

# --- НАЛАШТУВАННЯ ---
CAM_URL = "http://192.168.0.114"
DEVKIT_IP = "192.168.0.113"
model = YOLO('yolov8n.pt') 
current_angle = 90

# HTML інтерфейс (зручний для тачскріна телефону)
HTML_CONTENT = """
<!DOCTYPE html>
<html>
    <head>
        <title>FastAPI AI Camera</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body { text-align: center; font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: #eee; margin: 0; padding: 20px; }
            .container { max-width: 800px; margin: auto; }
            img { width: 100%; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); background: #000; }
            .controls { margin-top: 25px; display: flex; justify-content: center; gap: 20px; }
            button { 
                padding: 20px 40px; font-size: 24px; border: none; border-radius: 50px;
                background: #3498db; color: white; cursor: pointer; touch-action: manipulation;
                transition: transform 0.1s, background 0.3s;
            }
            button:active { transform: scale(0.95); background: #2980b9; }
            .status { margin-top: 15px; color: #888; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>YOLOv8 Real-time Control</h2>
            <img src="/video_feed">
            <div class="controls">
                <button onclick="move(-15)">◀</button>
                <button onclick="move(15)">▶</button>
            </div>
            <p class="status">Connected to: 192.168.0.114 | Mode: FastAPI + YOLOv8n</p>
        </div>
        <script>
            function move(delta) {
                fetch(`/move?delta=${delta}`);
            }
        </script>
    </body>
</html>
"""

async def video_generator():
    cap = cv2.VideoCapture(CAM_URL, cv2.CAP_FFMPEG)
    while True:
        success, frame = cap.read()
        if not success:
            print("Помилка: Не вдалося отримати кадр з камери. Перевіряю з'єднання...")
            cap.release()
            await asyncio.sleep(2) # Чекаємо перед повторною спробою
            cap = cv2.VideoCapture(CAM_URL, cv2.CAP_FFMPEG)
            continue
        
        # YOLO розпізнавання
        results = model(frame, stream=True, verbose=False)
        for r in results:
            frame = r.plot() 

        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        await asyncio.sleep(0.01)

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_CONTENT

@app.get("/video_feed")
async def video_feed():
    # StreamingResponse — це ключ до успіху в FastAPI для відео
    return StreamingResponse(video_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/move")
async def move(delta: int):
    global current_angle
    current_angle = max(0, min(180, current_angle + delta))
    
    # Використовуємо threading для requests, щоб не блокувати асинхронний цикл
    def do_request():
        try:
            requests.get(f"http://{DEVKIT_IP}/pan?val={current_angle}", timeout=0.5)
        except:
            print("ESP DevKit connection error")

    import threading
    threading.Thread(target=do_request).start()
    
    return {"status": "ok", "angle": current_angle}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
