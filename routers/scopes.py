from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

import database as models
from dependencies import get_db, save_uploaded_file
from schemas import ScopeMountPayload

router = APIRouter()


def _scope_dict(s: models.Scope) -> dict:
    mounted_on = mounted_firearm_id = mounted_barrel_id = mount_type = None
    if s.firearms:
        f = s.firearms[0]
        mounted_on = f"{f.brand} {f.model}"
        mounted_firearm_id = f.id
        mount_type = "firearm"
    elif s.barrels:
        b = s.barrels[0]
        mounted_on = f"{b.tc_platform or ''} {b.caliber}".strip()
        mounted_barrel_id = b.id
        mount_type = "barrel"
    return {
        "id": s.id,
        "brand": s.brand,
        "model": s.model,
        "units": s.units,
        "price_paid": s.price_paid,
        "image_path": s.image_path,
        "mounted_on": mounted_on,
        "mounted_firearm_id": mounted_firearm_id,
        "mounted_barrel_id": mounted_barrel_id,
        "mount_type": mount_type,
    }


def _load_scope(scope_id: int, db: Session) -> models.Scope:
    return (
        db.query(models.Scope)
        .options(joinedload(models.Scope.firearms), joinedload(models.Scope.barrels))
        .filter(models.Scope.id == scope_id)
        .first()
    )


@router.get("/scopes/")
def list_scopes(db: Session = Depends(get_db)):
    scopes = (
        db.query(models.Scope)
        .options(joinedload(models.Scope.firearms), joinedload(models.Scope.barrels))
        .all()
    )
    return [_scope_dict(s) for s in scopes]


@router.post("/scopes/")
async def create_scope(
    brand: str = Form(...),
    model: str = Form(...),
    units: str = Form("MOA"),
    price: float = Form(0.0),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    img_path = await save_uploaded_file(image, "scope")
    s = models.Scope(brand=brand, model=model, units=units, price_paid=price, image_path=img_path)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _scope_dict(_load_scope(s.id, db))


@router.get("/available-mounts/")
def get_available_mounts(for_scope_id: int = None, db: Session = Depends(get_db)):
    firearms = (
        db.query(models.Firearm)
        .filter(
            models.Firearm.is_sold == False,
            (models.Firearm.scope_id == None) | (models.Firearm.scope_id == for_scope_id),
        )
        .options(joinedload(models.Firearm.barrels))
        .all()
    )
    tc_barrels = (
        db.query(models.Barrel)
        .filter(
            models.Barrel.tc_platform.isnot(None),
            (models.Barrel.scope_id == None) | (models.Barrel.scope_id == for_scope_id),
        )
        .all()
    )
    return {
        "firearms": [{"id": f.id, "label": f"{f.brand} {f.model}", "type": "firearm"} for f in firearms],
        "tc_barrels": [{"id": b.id, "label": f"{b.tc_platform} {b.caliber}", "type": "barrel"} for b in tc_barrels],
    }


@router.patch("/scopes/{scope_id}/mount")
def mount_scope(scope_id: int, payload: ScopeMountPayload, db: Session = Depends(get_db)):
    scope = db.query(models.Scope).filter(models.Scope.id == scope_id).first()
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")
    # Clear previous mount
    db.query(models.Firearm).filter(models.Firearm.scope_id == scope_id).update({"scope_id": None})
    db.query(models.Barrel).filter(models.Barrel.scope_id == scope_id).update({"scope_id": None})
    # Apply new mount
    if payload.mount_type == "firearm" and payload.mount_id:
        gun = db.query(models.Firearm).filter(models.Firearm.id == payload.mount_id).first()
        if not gun:
            raise HTTPException(status_code=404, detail="Firearm not found")
        gun.scope_id = scope_id
    elif payload.mount_type == "barrel" and payload.mount_id:
        barrel = db.query(models.Barrel).filter(models.Barrel.id == payload.mount_id).first()
        if not barrel:
            raise HTTPException(status_code=404, detail="Barrel not found")
        barrel.scope_id = scope_id
    db.commit()
    return _scope_dict(_load_scope(scope_id, db))
