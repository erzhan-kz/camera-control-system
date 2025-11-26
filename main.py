# main.py
import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from database import init_db, get_db_session
from auth import login_required
from camera import CameraController
from models import User, Camera
from schemas import user_schema, camera_schema
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'supersecretkey')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///camera.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация базы данных
db_session = init_db(app)

# Инициализация контроллера камер
camera_controller = CameraController()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cameras', methods=['GET'])
@login_required
def list_cameras():
    session = get_db_session()
    cameras = session.query(Camera).all()
    return jsonify([camera_schema.dump(cam) for cam in cameras])

@app.route('/cameras/<int:camera_id>/start', methods=['POST'])
@login_required
def start_camera(camera_id):
    success = camera_controller.start_camera(camera_id)
    return jsonify({'status': 'started' if success else 'failed'})

@app.route('/cameras/<int:camera_id>/stop', methods=['POST'])
@login_required
def stop_camera(camera_id):
    success = camera_controller.stop_camera(camera_id)
    return jsonify({'status': 'stopped' if success else 'failed'})

@app.route('/users', methods=['GET'])
@login_required
def list_users():
    session = get_db_session()
    users = session.query(User).all()
    return jsonify([user_schema.dump(user) for user in users])

@app.route('/healthz', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    # Render использует PORT, если он задан в переменных окружения
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
