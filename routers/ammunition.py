from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import database as models
from dependencies import get_db, save_uploaded_file
from schemas import AmmoPatchPayload

router = APIRouter()


def _ammo_dict(a: models.Ammo) -> dict:
    return {
        "id": a.id,
        "is_handload": a.is_handload,
        "brand": a.brand,
        "caliber": getattr(a, "caliber", None),
        "line_or_powder": a.line_or_powder,
        "bullet_weight": a.bullet_weight,
        "bullet_type": a.bullet_type,
        "bullet_bc": getattr(a, "bullet_bc", None),
        "charge_weight": a.charge_weight,
        "coal": a.coal,
        "image_path": a.image_path,
    }


@router.post("/ammo/")
async def add_ammo(
    brand: str = Form(None),
    recipe_name: str = Form(None),
    bullet_type: str = Form(None),
    bullet_id: str = Form(None),
    bullet_weight: float = Form(...),
    is_handload: bool = Form(False),
    ammo_model: str = Form(None),
    powder_id: str = Form(None),
    powder_charge: float = Form(None),
    coal: float = Form(None),
    caliber: str = Form(None),
    bullet_bc: float = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    img_path = await save_uploaded_file(image, "ammo")
    a = models.Ammo(
        brand=recipe_name or brand or "Unknown",
        caliber=caliber,
        bullet_type=bullet_id or bullet_type or "Unknown",
        bullet_weight=bullet_weight,
        bullet_bc=bullet_bc,
        is_handload=is_handload,
        line_or_powder=ammo_model or powder_id,
        charge_weight=powder_charge,
        coal=coal,
        image_path=img_path,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _ammo_dict(a)


@router.get("/ammo/")
def list_ammo(db: Session = Depends(get_db)):
    return [_ammo_dict(a) for a in db.query(models.Ammo).all()]


@router.get("/ammo/{ammo_id}")
def get_ammo(ammo_id: int, db: Session = Depends(get_db)):
    a = db.query(models.Ammo).filter(models.Ammo.id == ammo_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Ammo not found")
    usage = db.query(models.ShotString).filter(models.ShotString.ammo_id == ammo_id).count()
    result = _ammo_dict(a)
    result["usage_count"] = usage
    return result


@router.patch("/ammo/{ammo_id}")
def patch_ammo(ammo_id: int, payload: AmmoPatchPayload, db: Session = Depends(get_db)):
    a = db.query(models.Ammo).filter(models.Ammo.id == ammo_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Ammo not found")
    for field, value in payload.dict(exclude_none=True).items():
        setattr(a, field, value)
    db.commit()
    db.refresh(a)
    return _ammo_dict(a)


@router.delete("/ammo/{ammo_id}")
def delete_ammo(ammo_id: int, db: Session = Depends(get_db)):
    a = db.query(models.Ammo).filter(models.Ammo.id == ammo_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Ammo not found")
    usage = db.query(models.ShotString).filter(models.ShotString.ammo_id == ammo_id).count()
    if usage > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {usage} range session(s) reference this load. Delete those sessions first.",
        )
    db.delete(a)
    db.commit()
    return {"deleted": ammo_id}
