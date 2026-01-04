from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.security import decode_token

bearer = HTTPBearer()

def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        return decode_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid_token")

def require_admin(u=Depends(current_user)):
    if u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin_only")
    return u
