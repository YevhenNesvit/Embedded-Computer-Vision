from ultralytics import YOLO

# Шлях до твоєї найкращої моделі
model = YOLO('runs/detect/drone_detection/yolov8n_uav4/weights/best.pt')

# Запускаємо детекцію на папці test, яку ми завантажили з Roboflow
results = model.predict(source='Edge-AI PTZ Surveillance System/training/dataset/test/images', save=True, conf=0.5)

print("Результати збережено в папку runs/detect/predict")
