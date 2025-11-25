# models.py
from sqlalchemy import (Column, Integer, String, DateTime, Boolean, Text)
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import datetime
import json

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")  # "admin" or "user"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Visit(Base):
    __tablename__ = "visits"
    id = Column(Integer, primary_key=True)
    photo_path = Column(String, nullable=False)
    time_in = Column(DateTime, nullable=False)
    time_out = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    person_data = Column(Text, nullable=True)  # JSON
    image_hash = Column(String, nullable=True)
    exited = Column(Boolean, default=False)

# DB helper
def get_engine(db_url="sqlite:///./camera.db"):
    return create_engine(db_url, connect_args={"check_same_thread": False})

def get_session(engine):
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
