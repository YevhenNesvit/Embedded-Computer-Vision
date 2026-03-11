import cv2
import requests
import uvicorn
import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from ultralytics import YOLO
import asyncio
import time
import threading

app = FastAPI()

# ==========================================
# CONFIGURATION
# ==========================================
# Hardware IPs
DEVKIT_IP = "192.168.0.128"

# Video Source: 0 or 1 for USB/FPV UVC Receiver, or "video.mp4" for testing
VIDEO_SOURCE = 0 

# AI Model settings
MODEL_PATH = 'server/best.engine' # Mention in README that this is an optimized INT8 model
TARGET_CLASS_ID = 3      # ID for "Tank" / "APC"

# Tracking & Motor Control (PID-like parameters)
CENTER_TOLERANCE = 40    # Deadzone in pixels to prevent motor jitter
KP_X = 0.04              # Proportional gain for Pan
KP_Y = 0.04              # Proportional gain for Tilt

# Depth Estimation Constants (Monocular setup)
REAL_WIDTH_METERS = 3.0  # Approx real-world width of the target (e.g., APC/Tank)
FOCAL_LENGTH = 750       # Camera focal length in pixels (requires calibration)

# Global State
current_angle_x = 90
current_angle_y = 90
last_request_time = 0    
latest_jpeg = None

# ==========================================
# WEB INTERFACE
# ==========================================
HTML_CONTENT = """
<!DOCTYPE html>
<html>
    <head>
        <title>Autonomous Turret HUD</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body { text-align: center; font-family: 'Courier New', Courier, monospace; background: #111; color: #0f0; margin: 0; padding: 20px; }
            .container { max-width: 800px; margin: auto; }
            img { width: 100%; border-radius: 5px; border: 2px solid #333; box-shadow: 0 0 20px rgba(0,255,0,0.2); }
            h2 { letter-spacing: 2px; }
            .status { margin-top: 15px; font-size: 18px; font-weight: bold; animation: blink 2s infinite; }
            @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>TACTICAL VISION SYSTEM</h2>
            <img src="/video_feed">
            <p class="status">● TRACKING ONLINE</p>
        </div>
    </body>
</html>
"""

# ==========================================
# HARDWARE COMMUNICATION
# ==========================================
def send_movement_command(x, y):
    """Sends asynchronous HTTP GET requests to the ESP32 to control servos."""
    global last_request_time
    # Rate limiting to 10Hz to prevent network/ESP32 flooding
    if time.time() - last_request_time < 0.1:
        return
    last_request_time = time.time()
    
    def do_request():
        try:
            requests.get(f"http://{DEVKIT_IP}/move?x={x}&y={y}", timeout=0.2)
        except:
            pass # Fail silently if ESP32 drops a packet
            
    threading.Thread(target=do_request, daemon=True).start()

# ==========================================
# CORE AI & COMPUTER VISION THREAD
# ==========================================
def vision_thread():
    """Runs the YOLO tracking and draws the custom HUD in a separate thread."""
    global latest_jpeg, current_angle_x, current_angle_y
    
    print("[INFO] Loading optimized AI model...")
    model = YOLO(MODEL_PATH, task='detect')
    
    print(f"[INFO] Connecting to video source: {VIDEO_SOURCE}...")
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    
    while True:
        success, frame = cap.read()
        if not success:
            if isinstance(VIDEO_SOURCE, str): # Loop if it's a video file
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            else:
                time.sleep(0.1)
            continue
            
        frame_h, frame_w, _ = frame.shape
        center_x, center_y = frame_w // 2, frame_h // 2
        
        # Draw Crosshair
        cv2.drawMarker(frame, (center_x, center_y), (0, 0, 255), cv2.MARKER_CROSS, 20, 1)
        
        # AI Inference + ByteTrack (Kalman Filter)
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
        target_found = False
        box_cx, box_cy = 0, 0
        
        for r in results:
            if r.boxes.id is not None:
                boxes = r.boxes.xyxy.cpu().numpy()
                track_ids = r.boxes.id.int().cpu().numpy()
                classes = r.boxes.cls.int().cpu().numpy()
                
                for box, track_id, cls_id in zip(boxes, track_ids, classes):
                    if cls_id == TARGET_CLASS_ID:
                        x1, y1, x2, y2 = box.astype(int)
                        
                        # Custom Bounding Box
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        # Distance Estimation
                        pixel_width = x2 - x1
                        if pixel_width > 0:
                            distance = (REAL_WIDTH_METERS * FOCAL_LENGTH) / pixel_width
                        else:
                            distance = 0.0
                        
                        box_cx = (x1 + x2) // 2
                        box_cy = (y1 + y2) // 2
                        target_found = True
                        
                        # Custom HUD Text with Background
                        text = f"TGT ID:{track_id} | DIST:{distance:.1f}m"
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        (text_w, text_h), _ = cv2.getTextSize(text, font, 0.6, 2)
                        cv2.rectangle(frame, (x1, y1 - text_h - 10), (x1 + text_w, y1), (0, 0, 0), -1)
                        cv2.putText(frame, text, (x1, y1 - 5), font, 0.6, (0, 255, 255), 2)
                        
                        break # Lock onto the first detected target

        # Auto-Tracking Logic
        if target_found:
            cv2.line(frame, (center_x, center_y), (box_cx, box_cy), (0, 255, 0), 1)
            
            err_x = center_x - box_cx
            err_y = center_y - box_cy
            need_move = False
            
            if abs(err_x) > CENTER_TOLERANCE:
                current_angle_x += int(err_x * KP_X)
                current_angle_x = max(0, min(180, current_angle_x))
                need_move = True
                
            if abs(err_y) > CENTER_TOLERANCE:
                current_angle_y -= int(err_y * KP_Y) 
                current_angle_y = max(0, min(180, current_angle_y))
                need_move = True
                
            if need_move:
                send_movement_command(current_angle_x, current_angle_y)

        # Encode frame for web streaming
        _, buffer = cv2.imencode('.jpg', frame)
        latest_jpeg = buffer.tobytes()

# Start the vision processing thread
threading.Thread(target=vision_thread, daemon=True).start()

# ==========================================
# ASYNC WEB SERVER ROUTES
# ==========================================
async def video_generator():
    """Yields the latest processed frame to the web client."""
    while True:
        if latest_jpeg is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + latest_jpeg + b'\r\n')
        await asyncio.sleep(0.03) # Cap at ~30 FPS

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_CONTENT

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(video_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
