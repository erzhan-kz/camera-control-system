# main.py
import os
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from models import Base, get_engine, get_session, User, Visit
from sqlalchemy.orm import Session
import datetime
from passlib.context import CryptContext
from jose import JWTError, jwt
import uuid
from camera_ezviz import download_snapshot
from PIL import Image
import imagehash

# CONFIG
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60*24*7

EZVIZ_DEVICE_SERIAL = os.getenv("EZVIZ_DEVICE_SERIAL")  # e.g. BF8488786
SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "./media/faces")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./camera.db")

os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs("static", exist_ok=True)

# DB init
engine = get_engine(DB_URL)
Base.metadata.create_all(bind=engine)
db = get_session(engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
app = FastAPI()
app.mount("/media", StaticFiles(directory="media"), name="media")
templates = Jinja2Templates(directory="templates")

# Simple auth utils (JWT)
def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: datetime.timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user_by_username(sess: Session, username: str):
    return sess.query(User).filter(User.username==username).first()

# Dependency
def get_db():
    session = get_session(engine)
    try:
        yield session
    finally:
        session.close()

# AUTH endpoints (simple)
@app.post("/api/register")
def register_user(username: str = Form(...), password: str = Form(...), role: str = Form("user"), db: Session = Depends(get_db)):
    if get_user_by_username(db, username):
        raise HTTPException(400, "User exists")
    user = User(username=username, password_hash=get_password_hash(password), role=role)
    db.add(user); db.commit()
    return {"ok": True, "username": username}

@app.post("/api/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}

# helper: save snapshot from EZVIZ
def save_snapshot_and_register(device_serial: str = None, session: Session = None):
    if device_serial is None:
        device_serial = EZVIZ_DEVICE_SERIAL
    if device_serial is None:
        raise RuntimeError("EZVIZ_DEVICE_SERIAL not configured")
    ts = datetime.datetime.utcnow()
    filename = f"{ts.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
    dest = os.path.join(SNAPSHOT_DIR, filename)
    download_snapshot(device_serial, dest)
    # compute hash
    img = Image.open(dest).convert("L").resize((200,200))
    h = str(imagehash.phash(img))
    # create Visit record
    visit = Visit(photo_path=dest, time_in=ts, person_data=None, image_hash=h, exited=False)
    session.add(visit)
    session.commit()
    return visit

# Admin endpoint to trigger snapshot (or background scheduler)
@app.post("/api/take_snapshot")
def take_snapshot(background: bool = Form(False), db: Session = Depends(get_db)):
    if background:
        # run in background
        from threading import Thread
        def job():
            s = get_session(engine)
            try:
                save_snapshot_and_register(session=s)
            finally:
                s.close()
        t = Thread(target=job, daemon=True); t.start()
        return {"status":"scheduled"}
    else:
        visit = save_snapshot_and_register(session=db)
        return {"id": visit.id, "photo": visit.photo_path, "time_in": visit.time_in.isoformat()}

# API to mark exit by id
@app.post("/api/mark_exit/{visit_id}")
def mark_exit(visit_id: int, db: Session = Depends(get_db)):
    v = db.query(Visit).get(visit_id)
    if not v:
        raise HTTPException(404, "Not found")
    if v.exited:
        return {"ok": True, "msg": "Already exited"}
    v.time_out = datetime.datetime.utcnow()
    v.duration_seconds = int((v.time_out - v.time_in).total_seconds())
    v.exited = True
    db.add(v); db.commit()
    return {"ok": True}

# API list visits
@app.get("/api/visits")
def list_visits(db: Session = Depends(get_db)):
    rows = db.query(Visit).order_by(Visit.time_in.desc()).all()
    result = []
    for r in rows:
        result.append({
            "id": r.id,
            "photo": r.photo_path,
            "time_in": r.time_in.isoformat(),
            "time_out": r.time_out.isoformat() if r.time_out else None,
            "duration_seconds": r.duration_seconds,
            "person_data": r.person_data,
            "exited": bool(r.exited)
        })
    return result

# Simple web UI
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    visits = db.query(Visit).order_by(Visit.time_in.desc()).all()
    return templates.TemplateResponse("index.html", {"request": request, "visits": visits})

# static helper to serve photo (if needed)
@app.get("/photo/{filename}")
def photo(filename: str):
    path = os.path.join(SNAPSHOT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
