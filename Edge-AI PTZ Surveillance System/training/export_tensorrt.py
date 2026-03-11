from ultralytics import YOLO

MODEL_PATH = "server/best.pt"
print(f"[INFO] Завантаження моделі {MODEL_PATH}...")

# Завантажуємо оригінальну модель
model = YOLO(MODEL_PATH)

print("[INFO] Починаємо експорт у NVIDIA TensorRT...")
print("[УВАГА] Відеокарта зараз буде гудіти. Це може зайняти 5-15 хвилин!")
print("[УВАГА] Створений файл працюватиме ТІЛЬКИ на цій відеокарті (GTX 1050 Ti).")

# format="engine" - формат TensorRT
# device=0 - використовуємо твою відеокарту
# half=True - конвертуємо числа в FP16 (16-біт) для подвоєння FPS!
# workspace=2 - виділяємо 2 ГБ відеопам'яті під процес конвертації
model.export(
    format="engine", 
    device=0, 
    half=True, 
    workspace=2 
)

print("\n[INFO] Експорт завершено! Шукай файл із розширенням .engine у папці.")
