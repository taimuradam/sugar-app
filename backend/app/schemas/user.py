from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Literal

Role = Literal["admin", "viewer", "user"]

class UserCreate(BaseModel):
    username: str
    password: str
    role: Role = "viewer"

    @field_validator("username")
    @classmethod
    def username_trim(cls, v: str):
        v = v.strip()
        if not v:
            raise ValueError("username is required")
        if len(v) > 64:
            raise ValueError("username too long")
        return v

    @field_validator("password")
    @classmethod
    def password_min(cls, v: str):
        v = str(v)
        if len(v) < 6:
            raise ValueError("password must be at least 6 characters")
        return v



    @field_validator("role")
    @classmethod
    def role_normalize(cls, v: str):
        v = (v or "").strip().lower()
        if v == "user":
            return "viewer"
        return v
class UserUpdate(BaseModel):
    password: str | None = None
    role: Role | None = None

    @field_validator("role")
    @classmethod
    def role_normalize(cls, v: str | None):
        if v is None:
            return None
        vv = str(v).strip().lower()
        if vv == "user":
            return "viewer"
        return vv

    @field_validator("password")
    @classmethod
    def password_min(cls, v: str | None):
        if v is None:
            return None
        v = str(v)
        if len(v) < 6:
            raise ValueError("password must be at least 6 characters")
        return v

class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True
