from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

import database as models
from config import templates
from dependencies import get_db, _hash_pw
from schemas import AdminUserPatch

router = APIRouter()


def _require_admin(request: Request):
    if not getattr(request.state, "user", None) or not request.state.user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    users = db.query(models.User).order_by(models.User.id).all()
    return templates.TemplateResponse("admin_users.html", {
        "request": request, "user": request.state.user, "users": users,
    })


@router.patch("/admin/users/{user_id}")
def admin_patch_user(user_id: int, payload: AdminUserPatch, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(404, "Not found")
    if payload.is_admin  is not None: u.is_admin  = payload.is_admin
    if payload.is_active is not None: u.is_active = payload.is_active
    db.commit()
    return {"id": u.id, "username": u.username, "is_admin": u.is_admin, "is_active": u.is_active}


@router.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    if user_id == request.state.user.id:
        raise HTTPException(400, "Cannot delete your own account")
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(404, "Not found")
    db.delete(u)
    db.commit()
    return {"deleted": user_id}


@router.post("/admin/users/")
async def admin_create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(default=None),
    is_admin: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(request)
    if db.query(models.User).filter(models.User.username == username.strip()).first():
        raise HTTPException(400, "Username already exists")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    u = models.User(
        username=username.strip(),
        email=email.strip() if email else None,
        hashed_password=_hash_pw(password),
        is_admin=bool(is_admin),
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "username": u.username, "is_admin": u.is_admin}
