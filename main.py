from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
import shutil

from database import Base, engine, get_db
from models import User, Camera, Visitor
from schemas import *
from auth import *
from camera import capture_face_from_camera, capture_face_from_file, PHOTO_DIR

# Создаем таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Система контроля доступа",
    description="API для управления доступом с распознаванием лиц",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы для фото
app.mount("/photos", StaticFiles(directory=PHOTO_DIR), name="photos")

# ==================== Аутентификация ====================

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.login}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=UserOut)
async def create_user(
    user: UserCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Только админ может создавать пользователей
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    db_user = db.query(User).filter(User.login == user.login).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        login=user.login,
        password_hash=hashed_password,
        role=user.role,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# ==================== Камеры ====================

@app.post("/cameras/", response_model=CameraOut)
async def create_camera(
    camera: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_camera = Camera(**camera.dict())
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return db_camera

@app.get("/cameras/", response_model=List[CameraOut])
async def get_cameras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Camera).all()

@app.get("/cameras/{camera_id}", response_model=CameraOut)
async def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Камера не найдена")
    return camera

@app.put("/cameras/{camera_id}/status")
async def update_camera_status(
    camera_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Камера не найдена")
    
    camera.status = status
    db.commit()
    return {"message": "Статус обновлен"}

# ==================== Посетители ====================

@app.post("/visitors/", response_model=VisitorOut)
async def create_visitor(
    visitor: VisitorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Получаем камеру
    camera = db.query(Camera).filter(Camera.id == visitor.camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Камера не найдена")
    
    # Захватываем фото с камеры
    photo_path = capture_face_from_camera(camera.ip)
    
    db_visitor = Visitor(
        full_name=visitor.full_name,
        camera_id=visitor.camera_id,
        photo=photo_path,
        operator=current_user.login,
        notes=visitor.notes
    )
    db.add(db_visitor)
    db.commit()
    db.refresh(db_visitor)
    return db_visitor

@app.post("/visitors/upload/", response_model=VisitorOut)
async def create_visitor_with_upload(
    full_name: str,
    camera_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Сохраняем загруженный файл временно
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Обрабатываем фото
    photo_path = capture_face_from_file(temp_path)
    
    # Удаляем временный файл
    import os
    os.remove(temp_path)
    
    db_visitor = Visitor(
        full_name=full_name,
        camera_id=camera_id,
        photo=photo_path,
        operator=current_user.login
    )
    db.add(db_visitor)
    db.commit()
    db.refresh(db_visitor)
    return db_visitor

@app.get("/visitors/", response_model=List[VisitorOut])
async def get_visitors(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Visitor)
    
    if active_only:
        query = query.filter(Visitor.exit_time == None)
    
    return query.order_by(Visitor.entry_time.desc()).offset(skip).limit(limit).all()

@app.get("/visitors/{visitor_id}", response_model=VisitorOut)
async def get_visitor(
    visitor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Посетитель не найден")
    return visitor

@app.put("/visitors/{visitor_id}/exit")
async def mark_visitor_exit(
    visitor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Посетитель не найден")
    
    if visitor.exit_time:
        raise HTTPException(status_code=400, detail="Выход уже отмечен")
    
    visitor.exit_time = datetime.now()
    db.commit()
    return {"message": "Выход отмечен"}

# ==================== Статистика ====================

@app.get("/stats/today")
async def get_today_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    today = datetime.now().date()
    
    total = db.query(Visitor).filter(
        func.date(Visitor.entry_time) == today
    ).count()
    
    active = db.query(Visitor).filter(
        func.date(Visitor.entry_time) == today,
        Visitor.exit_time == None
    ).count()
    
    exited = db.query(Visitor).filter(
        func.date(Visitor.entry_time) == today,
        Visitor.exit_time != None
    ).count()
    
    return {
        "total": total,
        "active": active,
        "exited": exited,
        "date": today
    }

@app.get("/stats/by_camera")
async def get_stats_by_camera(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cameras = db.query(Camera).all()
    stats = []
    
    for camera in cameras:
        count = db.query(Visitor).filter(Visitor.camera_id == camera.id).count()
        stats.append({
            "camera_id": camera.id,
            "camera_name": camera.name,
            "visitor_count": count
        })
    
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
