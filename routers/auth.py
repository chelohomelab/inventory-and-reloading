import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request
from sqlalchemy.orm import Session

import database as models
from config import templates
from dependencies import get_db, _hash_pw, _verify_pw

router = APIRouter()


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, db: Session = Depends(get_db)):
    if db.query(models.User).count() > 0:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("setup.html", {"request": request, "error": None})


@router.post("/setup")
async def setup_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(models.User).count() > 0:
        return RedirectResponse("/login", status_code=302)
    if len(password) < 8:
        return templates.TemplateResponse(
            "setup.html",
            {"request": request, "error": "Password must be at least 8 characters"},
            status_code=400,
        )
    db.add(models.User(
        username=username.strip(),
        hashed_password=_hash_pw(password),
        is_admin=True,
        is_active=True,
    ))
    db.commit()
    return RedirectResponse("/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    if db.query(models.User).count() == 0:
        return RedirectResponse("/setup", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(
        models.User.username == username.strip(),
        models.User.is_active == True,
    ).first()
    if not user or not _verify_pw(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=401,
        )
    token = secrets.token_hex(32)
    days = 30 if remember else 1
    expires = datetime.utcnow() + timedelta(days=days)
    db.add(models.UserSession(user_id=user.id, token=token, expires_at=expires.isoformat()))
    db.commit()
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(key="session", value=token, httponly=True, samesite="lax", max_age=days * 86400)
    return response


@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session")
    if token:
        sess = db.query(models.UserSession).filter(models.UserSession.token == token).first()
        if sess:
            db.delete(sess)
            db.commit()
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("session")
    return resp
