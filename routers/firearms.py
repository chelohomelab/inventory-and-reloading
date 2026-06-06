from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi import Request
from sqlalchemy.orm import Session, joinedload

import database as models
from dependencies import get_db, save_uploaded_file
from schemas import FirearmPatchPayload, SoldPayload

router = APIRouter()

KNOWN_FRAME_TYPES = {"Rifle", "Pistol", "Shotgun"}


@router.post("/firearms/")
async def create_firearm(
    brand: str = Form(...),
    model: str = Form(...),
    price: float = Form(...),
    caliber: str = Form(...),
    frame_type: str = Form(...),
    twist_rate: str = Form(None),
    scope_optic: str = Form(None),
    image_1: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    img_path = await save_uploaded_file(image_1, "firearm")
    new_gun = models.Firearm(
        brand=brand, model=model, price_paid=price,
        frame_type=frame_type, image_path_1=img_path,
    )
    db.add(new_gun)
    db.flush()
    db.add(models.Barrel(
        firearm_id=new_gun.id, caliber=caliber,
        name="Primary", twist_rate=twist_rate, price_paid=0.0,
    ))
    if scope_optic and scope_optic.strip() and scope_optic.strip().lower() not in ("none",):
        optic_brand = scope_optic.strip()
        existing_scope = db.query(models.Scope).filter(models.Scope.brand == optic_brand).first()
        if existing_scope:
            new_gun.scope_id = existing_scope.id
        else:
            new_scope = models.Scope(brand=optic_brand, model="", units="MOA", price_paid=0.0)
            db.add(new_scope)
            db.flush()
            new_gun.scope_id = new_scope.id
    db.commit()
    db.refresh(new_gun)
    return new_gun


@router.get("/firearms/{firearm_id}")
def get_firearm(firearm_id: int, db: Session = Depends(get_db)):
    gun = (
        db.query(models.Firearm)
        .options(
            joinedload(models.Firearm.barrels),
            joinedload(models.Firearm.scope),
            joinedload(models.Firearm.accessories),
        )
        .filter(models.Firearm.id == firearm_id)
        .first()
    )
    if not gun:
        raise HTTPException(status_code=404, detail="Firearm not found")
    return gun


@router.patch("/firearms/{firearm_id}")
def patch_firearm(firearm_id: int, payload: FirearmPatchPayload, db: Session = Depends(get_db)):
    gun = db.query(models.Firearm).filter(models.Firearm.id == firearm_id).first()
    if not gun:
        raise HTTPException(status_code=404, detail="Firearm not found")
    if payload.brand is not None:
        gun.brand = payload.brand
    if payload.model is not None:
        gun.model = payload.model
    if payload.price_paid is not None:
        gun.price_paid = payload.price_paid
    if payload.caliber is not None:
        primary = db.query(models.Barrel).filter(models.Barrel.firearm_id == firearm_id).first()
        if primary:
            primary.caliber = payload.caliber
    if payload.scope_optic is not None:
        optic = payload.scope_optic.strip()
        if not optic or optic.lower() == "none":
            gun.scope_id = None
        else:
            existing = db.query(models.Scope).filter(models.Scope.brand == optic).first()
            if existing:
                gun.scope_id = existing.id
            else:
                s = models.Scope(brand=optic, model="", units="MOA", price_paid=0.0)
                db.add(s)
                db.flush()
                gun.scope_id = s.id
    db.commit()
    db.refresh(gun)
    return gun


@router.post("/firearms/{firearm_id}/mark-sold/")
def mark_firearm_sold(firearm_id: int, payload: SoldPayload, db: Session = Depends(get_db)):
    gun = db.query(models.Firearm).filter(models.Firearm.id == firearm_id).first()
    if not gun:
        raise HTTPException(status_code=404, detail="Firearm not found")
    gun.is_sold = payload.is_sold
    gun.price_sold = payload.price_sold
    db.commit()
    db.refresh(gun)
    return gun


@router.post("/firearms/{firearm_id}/update-photo/")
async def update_firearm_photo(
    firearm_id: int,
    image_1: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    gun = db.query(models.Firearm).filter(models.Firearm.id == firearm_id).first()
    if not gun:
        raise HTTPException(status_code=404, detail="Firearm not found")
    gun.image_path_1 = await save_uploaded_file(image_1, "firearm")
    db.commit()
    db.refresh(gun)
    return gun


@router.get("/catalog/")
def get_catalog(frame_type: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Firearm).options(joinedload(models.Firearm.barrels))
    if frame_type:
        if frame_type == "Rifle":
            # Catch-all: rifles + any unknown/legacy frame_type values
            query = query.filter(
                (models.Firearm.frame_type == "Rifle") |
                (~models.Firearm.frame_type.in_(KNOWN_FRAME_TYPES))
            )
        else:
            query = query.filter(models.Firearm.frame_type == frame_type)
    result = []
    for gun in query.all():
        barrel = gun.barrels[0] if gun.barrels else None
        result.append({
            "id": gun.id,
            "brand": gun.brand,
            "model": gun.model,
            "frame_type": gun.frame_type,
            "price_paid": gun.price_paid,
            "image_path_1": gun.image_path_1,
            "is_sold": getattr(gun, "is_sold", False),
            "price_sold": getattr(gun, "price_sold", None),
            "caliber": barrel.caliber if barrel else None,
        })
    return result


@router.post("/barrels/")
async def create_barrel(
    firearm_id: int = Form(...),
    caliber: str = Form(...),
    name: str = Form(None),
    price: float = Form(0.0),
    twist: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    img_path = await save_uploaded_file(image, "barrel")
    b = models.Barrel(
        firearm_id=firearm_id, caliber=caliber, name=name,
        price_paid=price, twist_rate=twist, image_path=img_path,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b
