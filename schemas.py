from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class CameraBase(BaseModel):
    name: str
    ip: str
    type: str
    location: Optional[str] = None

class CameraCreate(CameraBase):
    pass

class CameraOut(CameraBase):
    id: int
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

class VisitorBase(BaseModel):
    full_name: str
    camera_id: int
    notes: Optional[str] = None

class VisitorCreate(VisitorBase):
    pass

class VisitorOut(VisitorBase):
    id: int
    entry_time: datetime
    exit_time: Optional[datetime] = None
    photo: Optional[str] = None
    operator: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
