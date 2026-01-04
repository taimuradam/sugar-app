from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import db, require_admin, current_user
from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.models.user import User
from app.core.security import hash_password
from app.services.audit import log_event

router = APIRouter(prefix="/users", tags=["users"])

@router.get("", response_model=list[UserOut])
def list_users(s: Session = Depends(db), u=Depends(require_admin)):
    return s.execute(select(User).order_by(User.username.asc())).scalars().all()

@router.post("", response_model=UserOut)
def create_user(body: UserCreate, s: Session = Depends(db), u=Depends(require_admin)):
    exists = s.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="user_exists")
    user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    s.add(user)
    s.commit()
    s.refresh(user)
    return user

@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, s: Session = Depends(db), u=Depends(require_admin)):
    user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    if body.role is not None:
        user.role = body.role
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    s.add(user)
    s.commit()
    s.refresh(user)
    return user

@router.delete("/{user_id}")
def delete_user(user_id: int, s: Session = Depends(db), admin=Depends(require_admin), me=Depends(current_user)):
    user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    if user.username == me.get("sub"):
        raise HTTPException(status_code=409, detail="cannot_delete_self")
    details = {"username": user.username, "role": user.role}
    s.delete(user)
    s.commit()
    log_event(
        s,
        username=me.get("sub"),
        action="user.delete",
        entity_type="user",
        entity_id=user_id,
        details=details,
    )
    return {"ok": True}