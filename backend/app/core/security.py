import os
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "10080"))

def hash_password(p: str) -> str:
    if p is None:
        raise ValueError("password is required")
    p = str(p)
    b = p.encode("utf-8")
    if len(b) > 72:
        p = b[:72].decode("utf-8", errors="ignore")
    return pwd.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    if p is None or hashed is None:
        return False
    p = str(p)
    b = p.encode("utf-8")
    if len(b) > 72:
        p = b[:72].decode("utf-8", errors="ignore")
    return pwd.verify(p, hashed)

def create_access_token(sub: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRES_MIN)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])

def create_token(sub: str, role: str) -> str:
    return create_access_token(sub, role)