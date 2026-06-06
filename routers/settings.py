from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

import database as models
from dependencies import get_db
from schemas import SettingsPatch

router = APIRouter()


@router.get("/lookups/")
def get_lookups(db: Session = Depends(get_db)):
    result: dict = {}
    for row in db.query(models.LookupValue).order_by(models.LookupValue.value).all():
        result.setdefault(row.category, []).append(row.value)

    def _add(cat, values):
        existing = set(result.get(cat, []))
        for v in values:
            if v and v.strip() and v.strip() not in existing:
                result.setdefault(cat, []).append(v.strip())
        result[cat] = sorted(set(result.get(cat, [])))

    _add("caliber", [r.caliber for r in db.query(models.Barrel).all()] +
                    [r.caliber for r in db.query(models.BulletInventory).all()] +
                    [r.caliber for r in db.query(models.CasingInventory).all()] +
                    [getattr(r, "caliber", None) for r in db.query(models.Ammo).all()])
    _add("firearm_brand",       [r.brand for r in db.query(models.Firearm).all()])
    _add("firearm_model",       [r.model for r in db.query(models.Firearm).all()])
    _add("powder_brand",        [r.brand for r in db.query(models.PowderInventory).all()])
    _add("powder_name",         [r.name  for r in db.query(models.PowderInventory).all()])
    _add("primer_brand",        [r.brand for r in db.query(models.PrimerInventory).all()])
    _add("bullet_brand",        [r.brand for r in db.query(models.BulletInventory).all()])
    _add("bullet_product_line", [r.product_line for r in db.query(models.BulletInventory).all()])
    _add("casing_brand",        [r.brand for r in db.query(models.CasingInventory).all()])
    _add("ammo_brand",          [r.brand for r in db.query(models.Ammo).all()])
    return result


@router.post("/lookups/{category}")
async def save_lookup(category: str, value: str = Form(...), db: Session = Depends(get_db)):
    v = value.strip()
    if not v:
        raise HTTPException(status_code=400, detail="Empty value")
    exists = db.query(models.LookupValue).filter(
        models.LookupValue.category == category,
        models.LookupValue.value == v,
    ).first()
    if not exists:
        db.add(models.LookupValue(category=category, value=v))
        db.commit()
    return {"ok": True}


@router.get("/settings/")
def get_settings(db: Session = Depends(get_db)):
    return {s.key: s.value for s in db.query(models.Setting).all()}


@router.patch("/settings/")
def update_settings(payload: SettingsPatch, db: Session = Depends(get_db)):
    for key, val in payload.dict(exclude_none=True).items():
        row = db.query(models.Setting).filter(models.Setting.key == key).first()
        if row:
            row.value = val
        else:
            db.add(models.Setting(key=key, value=val))
    db.commit()
    return {s.key: s.value for s in db.query(models.Setting).all()}
