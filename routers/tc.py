from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import database as models
from dependencies import get_db, save_uploaded_file
from schemas import SoldPayload

router = APIRouter()


def _receiver_dict(r: models.TCReceiver) -> dict:
    return {
        "id": r.id,
        "platform": r.platform,
        "serial_number": r.serial_number,
        "price_paid": r.price_paid,
        "image_path": r.image_path,
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
        "scope_id": b.scope_id,
    }


@router.get("/tc-receivers/")
def list_tc_receivers(db: Session = Depends(get_db)):
    return [_receiver_dict(r) for r in db.query(models.TCReceiver).all()]


@router.post("/tc-receivers/")
async def create_tc_receiver(
    platform: str = Form(...),
    serial_number: str = Form(None),
    price: float = Form(0.0),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    img_path = await save_uploaded_file(image, "tc_receiver")
    r = models.TCReceiver(platform=platform, serial_number=serial_number,
                          price_paid=price, image_path=img_path)
    db.add(r)
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
    db: Session = Depends(get_db),
):
    img_path = await save_uploaded_file(image, "tc_barrel")
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
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return _barrel_dict(b)
