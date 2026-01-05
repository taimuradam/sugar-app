from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import db
from app.schemas.auth import LoginIn, TokenOut
from app.models.user import User
from app.core.security import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, s: Session = Depends(db)):
    u = s.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="bad_credentials")
    role_out = "viewer" if (u.role or "").lower() == "user" else u.role
    token = create_access_token(sub=u.username, role=role_out)
    return {"access_token": token, "role": role_out}
