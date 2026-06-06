from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi import Request
from sqlalchemy.orm import Session

import database as models
from config import templates
from dependencies import get_db

router = APIRouter()

PREF_DEFAULTS = {
    "feat_shotguns":  "true",
    "feat_handguns":  "true",
    "feat_tc":        "true",
    "feat_reloading": "true",
    "feat_ammo_log":  "true",
}


@router.get("/profile/", response_class=HTMLResponse)
async def profile_page(request: Request):
    return templates.TemplateResponse("profile.html", {
        "request": request, "user": request.state.user,
    })


@router.get("/api/preferences/")
def get_preferences(request: Request, db: Session = Depends(get_db)):
    rows = db.query(models.UserPreference).filter(
        models.UserPreference.user_id == request.state.user.id
    ).all()
    prefs = dict(PREF_DEFAULTS)
    prefs.update({r.key: r.value for r in rows})
    return prefs


@router.patch("/api/preferences/")
async def update_preferences(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    user_id = request.state.user.id
    for key, value in data.items():
        if key not in PREF_DEFAULTS:
            continue
        row = db.query(models.UserPreference).filter(
            models.UserPreference.user_id == user_id,
            models.UserPreference.key == key,
        ).first()
        if row:
            row.value = str(value).lower()
        else:
            db.add(models.UserPreference(user_id=user_id, key=key, value=str(value).lower()))
    db.commit()
    return {"ok": True}
