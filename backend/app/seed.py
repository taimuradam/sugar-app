import os
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password

def main():
    username = os.environ.get("SEED_ADMIN_USER", "admin")
    password = os.environ.get("SEED_ADMIN_PASS", "admin123")

    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing:
            return
        db.add(User(username=username, password_hash=hash_password(password), role="admin"))
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    main()
