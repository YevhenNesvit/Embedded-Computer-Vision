from ultralytics import YOLO
import torch

def train_model():
    # 1. Перевірка CUDA (про всяк випадок)
    device = '0' if torch.cuda.is_available() else 'cpu'
    print(f"🚀 Починаємо навчання на: {torch.cuda.get_device_name(0) if device == '0' else 'CPU'}")

    # 2. Завантажуємо базову модель YOLOv8 Nano (найшвидша для 1050 Ti)
    model = YOLO('yolov8n.pt') 

    # 3. Запуск навчання
    model.train(
        data='Edge-AI PTZ Surveillance System/training/dataset/data.yaml',    # шлях до твого розпакованого файлу
        epochs=50,           # для початку 50 епох достатньо, щоб побачити результат
        imgsz=640,           # стандартний розмір картинок
        batch=8,             # почнемо з 8; якщо видасть "Out of Memory", зміни на 4
        device=device,       # твоя GTX 1050 Ti
        workers=4,           # кількість потоків процесора для завантаження фото
        project='drone_detection', # назва папки з результатами
        name='yolov8n_uav'   # назва конкретного забігу
    )

if __name__ == '__main__':
    train_model()
