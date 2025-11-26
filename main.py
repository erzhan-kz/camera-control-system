import os
import sqlite3
import requests
from flask import Flask, render_template, request, redirect, session, url_for, flash
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()  # Загружаем .env с токенами EZVIZ

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")

# EZVIZ API параметры
EZVIZ_APP_KEY = os.environ.get("EZVIZ_APP_KEY")
EZVIZ_APP_SECRET = os.environ.get("EZVIZ_APP_SECRET")
EZVIZ_ACCESS_TOKEN = os.environ.get("EZVIZ_ACCESS_TOKEN")
CAMERA_SERIAL = os.environ.get("CAMERA_SERIAL")  # серийный номер камеры

# SQLite DB
DB_PATH = "faces.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS faces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        photo_url TEXT,
        checkin_time TEXT,
        checkout_time TEXT,
        timer INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

init_db()

# --- АУТЕНТИФИКАЦИЯ ---
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
        row = c.fetchone()
        conn.close()
        if row:
            session["username"] = username
            session["role"] = row[0]
            return redirect(url_for("dashboard"))
        else:
            flash("Неверный логин или пароль")
    return render_template("login.html")


# --- ДАШБОРД ---
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM faces")
    faces = c.fetchall()
    conn.close()

    # Подсчёт таймера пребывания
    updated_faces = []
    for f in faces:
        face_id, photo_url, checkin_time, checkout_time, timer = f
        checkin_dt = datetime.fromisoformat(checkin_time)
        if checkout_time:
            checkout_dt = datetime.fromisoformat(checkout_time)
            stay_time = (checkout_dt - checkin_dt).seconds // 60
        else:
            stay_time = (datetime.now() - checkin_dt).seconds // 60
        updated_faces.append((face_id, photo_url, checkin_time, checkout_time, stay_time))
    
    return render_template("dashboard.html", faces=updated_faces, role=session["role"])


# --- АДМИН: управление пользователями ---
@app.route("/users", methods=["GET", "POST"])
def manage_users():
    if session.get("role") != "Администратор":
        return redirect(url_for("dashboard"))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if request.method == "POST":
        if "add" in request.form:
            username = request.form["username"]
            password = request.form["password"]
            role = request.form["role"]
            try:
                c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
                conn.commit()
                flash("Пользователь добавлен")
            except:
                flash("Ошибка добавления пользователя")
        elif "delete" in request.form:
            user_id = request.form["delete"]
            c.execute("DELETE FROM users WHERE id=?", (user_id,))
            conn.commit()
            flash("Пользователь удалён")
    c.execute("SELECT id, username, role FROM users")
    users = c.fetchall()
    conn.close()
    return render_template("users.html", users=users)


# --- ФИКСАЦИЯ ЛИЦА ЧЕРЕЗ EZVIZ ---
def get_camera_snapshot():
    url = f"https://open.ys7.com/api/lapp/device/capture?accessToken={EZVIZ_ACCESS_TOKEN}&deviceSerial={CAMERA_SERIAL}&channelNo=1"
    try:
        resp = requests.get(url)
        data = resp.json()
        if data["code"] == "200":
            return data["data"]["picUrl"]
        else:
            print("Ошибка EZVIZ:", data)
            return None
    except Exception as e:
        print("Ошибка запроса к EZVIZ:", e)
        return None


@app.route("/capture")
def capture_face():
    if "username" not in session:
        return redirect(url_for("login"))
    photo_url = get_camera_snapshot()
    if photo_url:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute("INSERT INTO faces (photo_url, checkin_time) VALUES (?, ?)", (photo_url, now))
        conn.commit()
        conn.close()
        flash("Лицо зафиксировано")
    else:
        flash("Ошибка получения снимка")
    return redirect(url_for("dashboard"))


# --- ВЫХОД ИЗ СЕССИИ ---
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
