from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import database as models
from dependencies import get_db, save_uploaded_file
from schemas import SoldPayload, TCReceiverPatchPayload, TCBarrelPatchPayload

router = APIRouter()


def _receiver_dict(r: models.TCReceiver) -> dict:
    return {
        "id": r.id,
        "platform": r.platform,
        "serial_number": r.serial_number,
        "notes": r.notes,
        "price_paid": r.price_paid,
        "image_path": r.image_path,
        "image_path_2": r.image_path_2,
        "is_sold": r.is_sold,
        "price_sold": r.price_sold,
    }


def _barrel_dict(b: models.Barrel) -> dict:
    return {
        "id": b.id,
        "tc_platform": b.tc_platform,
        "caliber": b.caliber,
        "twist_rate": b.twist_rate,
        "barrel_length": b.barrel_length,
        "hardware_color": b.hardware_color,
        "is_threaded": b.is_threaded,
        "has_muzzle_brake": b.has_muzzle_brake,
        "price_paid": b.price_paid,
        "image_path": b.image_path,
        "image_path_2": b.image_path_2,
        "scope_id": b.scope_id,
    }


@router.get("/tc-receivers/")
def list_tc_receivers(db: Session = Depends(get_db)):
    return [_receiver_dict(r) for r in db.query(models.TCReceiver).all()]


@router.post("/tc-receivers/")
async def create_tc_receiver(
    platform: str = Form(...),
    serial_number: str = Form(None),
    notes: str = Form(None),
    price: float = Form(0.0),
    image: UploadFile = File(None),
    image_2: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    img_path = await save_uploaded_file(image, "tc_receiver")
    img_path_2 = await save_uploaded_file(image_2, "tc_receiver")
    r = models.TCReceiver(platform=platform, serial_number=serial_number,
                          notes=notes, price_paid=price,
                          image_path=img_path, image_path_2=img_path_2)
    db.add(r)
    db.commit()
    db.refresh(r)
    return _receiver_dict(r)


@router.patch("/tc-receivers/{receiver_id}")
def patch_tc_receiver(receiver_id: int, payload: TCReceiverPatchPayload, db: Session = Depends(get_db)):
    r = db.query(models.TCReceiver).filter(models.TCReceiver.id == receiver_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="TC Receiver not found")
    if payload.platform is not None:
        r.platform = payload.platform
    if payload.serial_number is not None:
        r.serial_number = payload.serial_number
    if payload.notes is not None:
        r.notes = payload.notes
    if payload.price_paid is not None:
        r.price_paid = payload.price_paid
    db.commit()
    db.refresh(r)
    return _receiver_dict(r)


@router.post("/tc-receivers/{receiver_id}/update-photo/")
async def update_tc_receiver_photo(
    receiver_id: int,
    slot: int = Form(1),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    r = db.query(models.TCReceiver).filter(models.TCReceiver.id == receiver_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="TC Receiver not found")
    img_path = await save_uploaded_file(image, "tc_receiver")
    if slot == 2:
        r.image_path_2 = img_path
    else:
        r.image_path = img_path
    db.commit()
    db.refresh(r)
    return _receiver_dict(r)


@router.post("/tc-receivers/{receiver_id}/mark-sold/")
def mark_tc_receiver_sold(receiver_id: int, payload: SoldPayload, db: Session = Depends(get_db)):
    r = db.query(models.TCReceiver).filter(models.TCReceiver.id == receiver_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="TC Receiver not found")
    r.is_sold = payload.is_sold
    r.price_sold = payload.price_sold
    db.commit()
    db.refresh(r)
    return _receiver_dict(r)


@router.get("/tc-barrels/{barrel_id}")
def get_tc_barrel(barrel_id: int, db: Session = Depends(get_db)):
    b = db.query(models.Barrel).filter(
        models.Barrel.id == barrel_id, models.Barrel.tc_platform.isnot(None)
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="TC Barrel not found")
    return _barrel_dict(b)


@router.get("/tc-barrels/")
def list_tc_barrels(db: Session = Depends(get_db)):
    barrels = db.query(models.Barrel).filter(models.Barrel.tc_platform.isnot(None)).all()
    return [_barrel_dict(b) for b in barrels]


@router.post("/tc-barrels/")
async def create_tc_barrel(
    tc_platform: str = Form(...),
    caliber: str = Form(...),
    twist_rate: str = Form(None),
    barrel_length: str = Form(None),
    hardware_color: str = Form(None),
    is_threaded: bool = Form(False),
    has_muzzle_brake: bool = Form(False),
    price: float = Form(0.0),
    image: UploadFile = File(None),
    image_2: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    img_path = await save_uploaded_file(image, "tc_barrel")
    img_path_2 = await save_uploaded_file(image_2, "tc_barrel")
    b = models.Barrel(
        firearm_id=None,
        tc_platform=tc_platform,
        caliber=caliber,
        name=f"{tc_platform} {caliber}",
        twist_rate=twist_rate,
        barrel_length=barrel_length,
        hardware_color=hardware_color,
        is_threaded=is_threaded,
        has_muzzle_brake=has_muzzle_brake,
        price_paid=price,
        image_path=img_path,
        image_path_2=img_path_2,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return _barrel_dict(b)


@router.patch("/tc-barrels/{barrel_id}")
def patch_tc_barrel(barrel_id: int, payload: TCBarrelPatchPayload, db: Session = Depends(get_db)):
    b = db.query(models.Barrel).filter(
        models.Barrel.id == barrel_id, models.Barrel.tc_platform.isnot(None)
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="TC Barrel not found")
    if payload.caliber is not None:
        b.caliber = payload.caliber
    if payload.twist_rate is not None:
        b.twist_rate = payload.twist_rate
    if payload.barrel_length is not None:
        b.barrel_length = payload.barrel_length
    if payload.hardware_color is not None:
        b.hardware_color = payload.hardware_color
    if payload.is_threaded is not None:
        b.is_threaded = payload.is_threaded
    if payload.has_muzzle_brake is not None:
        b.has_muzzle_brake = payload.has_muzzle_brake
    if payload.price_paid is not None:
        b.price_paid = payload.price_paid
    db.commit()
    db.refresh(b)
    return _barrel_dict(b)


@router.post("/tc-barrels/{barrel_id}/update-photo/")
async def update_tc_barrel_photo(
    barrel_id: int,
    slot: int = Form(1),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    b = db.query(models.Barrel).filter(
        models.Barrel.id == barrel_id, models.Barrel.tc_platform.isnot(None)
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="TC Barrel not found")
    img_path = await save_uploaded_file(image, "tc_barrel")
    if slot == 2:
        b.image_path_2 = img_path
    else:
        b.image_path = img_path
    db.commit()
    db.refresh(b)
    return _barrel_dict(b)
