from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
from database import Base, engine, get_db
from models import User, Camera, Visitor
from schemas import *
from auth import *

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Система контроля доступа")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    db = next(get_db())
    if not db.query(User).filter(User.login == "admin").first():
        admin = User(login="admin", password_hash=get_password_hash("admin123"), role="admin", full_name="Администратор")
        db.add(admin)
        db.commit()

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    token = create_access_token(data={"sub": user.login}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer"}

@app.post("/cameras/", response_model=CameraOut)
async def create_camera(camera: CameraCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_camera = Camera(**camera.dict())
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return db_camera

@app.get("/cameras/", response_model=List[CameraOut])
async def get_cameras(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Camera).all()

@app.post("/visitors/", response_model=VisitorOut)
async def create_visitor(visitor: VisitorCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    camera = db.query(Camera).filter(Camera.id == visitor.camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Камера не найдена")
    db_visitor = Visitor(full_name=visitor.full_name, camera_id=visitor.camera_id, operator=current_user.login, notes=visitor.notes)
    db.add(db_visitor)
    db.commit()
    db.refresh(db_visitor)
    return db_visitor

@app.get("/visitors/", response_model=List[VisitorOut])
async def get_visitors(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Visitor).order_by(Visitor.entry_time.desc()).limit(100).all()

@app.put("/visitors/{visitor_id}/exit")
async def mark_exit(visitor_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404)
    if visitor.exit_time:
        raise HTTPException(status_code=400, detail="Выход уже отмечен")
    visitor.exit_time = datetime.now()
    db.commit()
    return {"message": "OK"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
