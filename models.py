from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    login = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="operator")
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    ip = Column(String)
    type = Column(String)
    status = Column(String, default="Активна")
    location = Column(String)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    visitors = relationship("Visitor", back_populates="camera")

class Visitor(Base):
    __tablename__ = "visitors"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    entry_time = Column(TIMESTAMP(timezone=True), server_default=func.now())
    exit_time = Column(TIMESTAMP(timezone=True), nullable=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"))
    photo = Column(String)
    operator = Column(String)
    notes = Column(String)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    camera = relationship("Camera", back_populates="visitors")
