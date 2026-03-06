from ultralytics import YOLO

# Вказуєш шлях до своєї моделі (можна до оригінальної .pt або до OpenVINO)
model = YOLO('best.pt', task='detect')

# Ця команда виведе в термінал словник з усіма класами, які знає модель
print(model.names)