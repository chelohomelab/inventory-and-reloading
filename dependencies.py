import os
import uuid
import bcrypt as _bcrypt
import database as models
from fastapi import UploadFile
from sqlalchemy.orm import Session
from typing import Optional
from config import UPLOAD_DIR


def get_db():
    session = models.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _hash_pw(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify_pw(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


async def save_uploaded_file(file: UploadFile, prefix: str) -> Optional[str]:
    if not file or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1]
    filename = f"{prefix}_{uuid.uuid4()}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as buf:
        buf.write(await file.read())
    return f"/static/uploads/{filename}"
