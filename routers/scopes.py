from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

import database as models
from dependencies import get_db, save_uploaded_file
from schemas import ScopeMountPayload, ScopePatchPayload

router = APIRouter()


def _scope_dict(s: models.Scope) -> dict:
    def _mount_label(f):
        cal = f.barrels[0].caliber if f.barrels else None
        base = f"{f.brand} {f.model}"
        return f"{base} ({cal})" if cal else base

    mounts = (
        [{"type": "firearm", "id": f.id, "label": _mount_label(f)} for f in s.firearms] +
        [{"type": "barrel",  "id": b.id, "label": f"{b.tc_platform or ''} {b.caliber}".strip()} for b in s.barrels]
    )
    first = mounts[0] if mounts else None
    return {
        "id": s.id,
        "brand": s.brand,
        "model": s.model,
        "magnification": s.magnification,
        "units": s.units,
        "price_paid": s.price_paid,
        "image_path": s.image_path,
        "image_path_2": s.image_path_2,
        "quantity": getattr(s, "quantity", 1) or 1,
        "mounts": mounts,
        # backward-compat fields kept for existing mount editor
        "mounted_on": first["label"] if first else None,
        "mounted_firearm_id": first["id"] if first and first["type"] == "firearm" else None,
        "mounted_barrel_id":  first["id"] if first and first["type"] == "barrel"  else None,
        "mount_type": first["type"] if first else None,
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
        .filter(models.Scope.is_deleted == False)
        .all()
    )
    return [_scope_dict(s) for s in scopes]


@router.post("/scopes/{scope_id}/trash")
def trash_scope(scope_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Scope).filter(models.Scope.id == scope_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scope not found")
    s.is_deleted = True
    db.commit()
    return {"id": s.id, "is_deleted": True}


@router.post("/scopes/{scope_id}/restore")
def restore_scope(scope_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Scope).filter(models.Scope.id == scope_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scope not found")
    s.is_deleted = False
    db.commit()
    return {"id": s.id, "is_deleted": False}


@router.post("/scopes/")
async def create_scope(
    brand: str = Form(...),
    model: str = Form(...),
    magnification: str = Form(None),
    units: str = Form("MOA"),
    quantity: int = Form(1),
    price: float = Form(0.0),
    image: UploadFile = File(None),
    image_2: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    img_path = await save_uploaded_file(image, "scope")
    img_path_2 = await save_uploaded_file(image_2, "scope")
    s = models.Scope(brand=brand, model=model, magnification=magnification or None,
                     units=units, quantity=max(1, quantity), price_paid=price,
                     image_path=img_path, image_path_2=img_path_2)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _scope_dict(_load_scope(s.id, db))


@router.patch("/scopes/{scope_id}")
def patch_scope(scope_id: int, payload: ScopePatchPayload, db: Session = Depends(get_db)):
    s = db.query(models.Scope).filter(models.Scope.id == scope_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scope not found")
    if payload.brand is not None:
        s.brand = payload.brand
    if payload.model is not None:
        s.model = payload.model
    if payload.magnification is not None:
        s.magnification = payload.magnification or None
    if payload.units is not None:
        s.units = payload.units
    if payload.price_paid is not None:
        s.price_paid = payload.price_paid
    if payload.quantity is not None:
        s.quantity = max(1, payload.quantity)
    db.commit()
    return _scope_dict(_load_scope(scope_id, db))


@router.post("/scopes/{scope_id}/update-photo/")
async def update_scope_photo(
    scope_id: int,
    slot: int = Form(1),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    s = db.query(models.Scope).filter(models.Scope.id == scope_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scope not found")
    img_path = await save_uploaded_file(image, "scope")
    if slot == 2:
        s.image_path_2 = img_path
    else:
        s.image_path = img_path
    db.commit()
    return _scope_dict(_load_scope(scope_id, db))


@router.post("/scopes/{scope_id}/swap-photos/")
def swap_scope_photos(scope_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Scope).filter(models.Scope.id == scope_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scope not found")
    s.image_path, s.image_path_2 = s.image_path_2, s.image_path
    db.commit()
    return _scope_dict(_load_scope(scope_id, db))


@router.get("/available-mounts/")
def get_available_mounts(for_scope_id: int = None, db: Session = Depends(get_db)):
    firearms = (
        db.query(models.Firearm)
        .filter(
            models.Firearm.is_deleted == False,
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
            models.Barrel.is_deleted == False,
            (models.Barrel.scope_id == None) | (models.Barrel.scope_id == for_scope_id),
        )
        .all()
    )
    def _firearm_label(f):
        caliber = f.barrels[0].caliber if f.barrels else None
        base = f"{f.brand} {f.model}"
        return f"{base} ({caliber})" if caliber else base

    return {
        "firearms": [{"id": f.id, "label": _firearm_label(f), "type": "firearm"} for f in firearms],
        "tc_barrels": [{"id": b.id, "label": f"{b.tc_platform} {b.caliber}", "type": "barrel"} for b in tc_barrels],
    }


@router.patch("/scopes/{scope_id}/add-mount")
def add_scope_mount(scope_id: int, payload: ScopeMountPayload, db: Session = Depends(get_db)):
    scope = _load_scope(scope_id, db)
    if not scope:
        raise HTTPException(status_code=404, detail="Scope not found")
    qty = getattr(scope, "quantity", 1) or 1
    if len(scope.firearms) + len(scope.barrels) >= qty:
        raise HTTPException(status_code=400, detail="All scope slots are already occupied")
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


@router.patch("/scopes/{scope_id}/remove-mount")
def remove_scope_mount(scope_id: int, payload: ScopeMountPayload, db: Session = Depends(get_db)):
    if payload.mount_type == "firearm" and payload.mount_id:
        db.query(models.Firearm).filter(
            models.Firearm.id == payload.mount_id,
            models.Firearm.scope_id == scope_id,
        ).update({"scope_id": None})
    elif payload.mount_type == "barrel" and payload.mount_id:
        db.query(models.Barrel).filter(
            models.Barrel.id == payload.mount_id,
            models.Barrel.scope_id == scope_id,
        ).update({"scope_id": None})
    db.commit()
    return _scope_dict(_load_scope(scope_id, db))


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
