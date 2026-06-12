from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import database as models
from dependencies import get_db, save_uploaded_file
from schemas import WishlistPatchPayload

router = APIRouter()

ITEM_TYPES = {"Rifle", "Handgun", "Shotgun", "TC System", "TC Barrel", "Optic", "Other"}


def _wish_dict(w: models.Wishlist) -> dict:
    return {
        "id": w.id,
        "item_type": w.item_type,
        "brand": w.brand,
        "model": w.model,
        "caliber": w.caliber,
        "priority": w.priority,
        "est_price": w.est_price,
        "notes": w.notes,
        "image_path": w.image_path,
        "url": w.url,
        "created_at": w.created_at,
    }


@router.get("/wishlist/")
def list_wishlist(db: Session = Depends(get_db)):
    return [_wish_dict(w) for w in db.query(models.Wishlist).order_by(models.Wishlist.id.desc()).all()]


@router.post("/wishlist/")
async def add_wishlist(
    item_type: str = Form("Other"),
    brand: str = Form(None),
    model: str = Form(None),
    caliber: str = Form(None),
    priority: str = Form("Medium"),
    est_price: float = Form(None),
    notes: str = Form(None),
    url: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    img_path = await save_uploaded_file(image, "wish")
    w = models.Wishlist(
        item_type=item_type,
        brand=brand,
        model=model,
        caliber=caliber,
        priority=priority,
        est_price=est_price,
        notes=notes,
        image_path=img_path,
        url=url,
        created_at=datetime.utcnow().strftime("%Y-%m-%d"),
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return _wish_dict(w)


@router.patch("/wishlist/{wish_id}")
def patch_wishlist(wish_id: int, payload: WishlistPatchPayload, db: Session = Depends(get_db)):
    w = db.query(models.Wishlist).filter(models.Wishlist.id == wish_id).first()
    if not w:
        raise HTTPException(404, "Not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(w, field, value)
    db.commit()
    db.refresh(w)
    return _wish_dict(w)


@router.post("/wishlist/{wish_id}/update-photo/")
async def update_wishlist_photo(wish_id: int, image: UploadFile = File(...), db: Session = Depends(get_db)):
    w = db.query(models.Wishlist).filter(models.Wishlist.id == wish_id).first()
    if not w:
        raise HTTPException(404, "Not found")
    path = await save_uploaded_file(image, "wish")
    w.image_path = path
    db.commit()
    return _wish_dict(w)


@router.delete("/wishlist/{wish_id}")
def delete_wishlist(wish_id: int, db: Session = Depends(get_db)):
    w = db.query(models.Wishlist).filter(models.Wishlist.id == wish_id).first()
    if not w:
        raise HTTPException(404, "Not found")
    db.delete(w)
    db.commit()
    return {"deleted": wish_id}


@router.post("/wishlist/{wish_id}/convert/")
def convert_wishlist(wish_id: int, db: Session = Depends(get_db)):
    """Convert a wishlist item to actual inventory. Returns {type, id} for frontend redirect."""
    w = db.query(models.Wishlist).filter(models.Wishlist.id == wish_id).first()
    if not w:
        raise HTTPException(404, "Not found")

    result_type = None
    result_id = None

    if w.item_type in ("Rifle", "Handgun", "Shotgun"):
        frame = w.item_type  # maps directly
        f = models.Firearm(
            brand=w.brand or "Unknown",
            model=w.model or "Unknown",
            frame_type=frame,
            price_paid=w.est_price or 0.0,
            image_path_1=w.image_path,
        )
        db.add(f)
        db.commit()
        db.refresh(f)
        result_type = "firearm"
        result_id = f.id

    elif w.item_type == "TC System":
        tc = models.TCReceiver(
            platform="Encore",
            notes=f"{w.brand or ''} {w.model or ''}".strip() or None,
            price_paid=w.est_price or 0.0,
            image_path=w.image_path,
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        result_type = "tc_receiver"
        result_id = tc.id

    elif w.item_type == "TC Barrel":
        b = models.Barrel(
            name=f"{w.brand or ''} {w.model or ''}".strip() or None,
            caliber=w.caliber or "Unknown",
            tc_platform="Encore",
            price_paid=w.est_price or 0.0,
            image_path=w.image_path,
        )
        db.add(b)
        db.commit()
        db.refresh(b)
        result_type = "tc_barrel"
        result_id = b.id

    elif w.item_type == "Optic":
        s = models.Scope(
            brand=w.brand or "Unknown",
            model=w.model or "Unknown",
            price_paid=w.est_price or 0.0,
            image_path=w.image_path,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        result_type = "scope"
        result_id = s.id

    else:
        # "Other" — nothing to convert, just remove
        result_type = "none"
        result_id = None

    db.delete(w)
    db.commit()
    return {"type": result_type, "id": result_id}
