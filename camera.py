import cv2
import face_recognition
from datetime import datetime
import os
from typing import Optional

PHOTO_DIR = "photos"

def ensure_photo_dir():
    if not os.path.exists(PHOTO_DIR):
        os.makedirs(PHOTO_DIR)

def capture_face_from_camera(camera_ip: str) -> Optional[str]:
    """
    Захватывает кадр с камеры и сохраняет фото лица
    Returns: путь к сохраненному файлу или None
    """
    ensure_photo_dir()
    
    # Пробуем различные форматы подключения
    # RTSP для IP камер
    rtsp_url = f"rtsp://{camera_ip}/stream1"
    
    cap = cv2.VideoCapture(rtsp_url)
    
    # Если RTSP не работает, пробуем HTTP
    if not cap.isOpened():
        http_url = f"http://{camera_ip}/video"
        cap = cv2.VideoCapture(http_url)
    
    # Если и это не работает, пробуем прямое подключение
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_ip)
    
    if not cap.isOpened():
        print(f"Не удалось подключиться к камере {camera_ip}")
        return None
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret or frame is None:
        print("Не удалось захватить кадр")
        return None
    
    # Конвертируем в RGB для face_recognition
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Обнаруживаем лица
    face_locations = face_recognition.face_locations(rgb_frame)
    
    if not face_locations:
        print("Лица не обнаружены")
        # Сохраняем кадр даже без лиц
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{PHOTO_DIR}/visitor_{timestamp}.jpg"
        cv2.imwrite(filename, frame)
        return filename
    
    # Если обнаружены лица, обрезаем первое лицо
    top, right, bottom, left = face_locations[0]
    face_image = frame[top:bottom, left:right]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{PHOTO_DIR}/visitor_{timestamp}.jpg"
    cv2.imwrite(filename, face_image)
    
    print(f"Фото сохранено: {filename}")
    return filename

def capture_face_from_file(file_path: str) -> Optional[str]:
    """
    Обрабатывает загруженное фото и извлекает лицо
    """
    ensure_photo_dir()
    
    image = cv2.imread(file_path)
    if image is None:
        return None
    
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_image)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if face_locations:
        top, right, bottom, left = face_locations[0]
        face_image = image[top:bottom, left:right]
        filename = f"{PHOTO_DIR}/visitor_{timestamp}.jpg"
        cv2.imwrite(filename, face_image)
    else:
        # Если лицо не обнаружено, сохраняем оригинал
        filename = f"{PHOTO_DIR}/visitor_{timestamp}.jpg"
        cv2.imwrite(filename, image)
    
    return filename
