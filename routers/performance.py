from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

import database as models
import math_engine
from dependencies import get_db, save_uploaded_file

router = APIRouter()


@router.post("/performance-log/")
async def log_group(
    barrel_id: int = Form(...),
    ammo_id: int = Form(...),
    date: str = Form(...),
    velocities_csv: str = Form(None),
    group_size: float = Form(None),
    target_image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    barrel = db.query(models.Barrel).filter(models.Barrel.id == barrel_id).first()
    ammo   = db.query(models.Ammo).filter(models.Ammo.id == ammo_id).first()
    if not barrel or not ammo:
        raise HTTPException(status_code=404, detail="Barrel or Ammo profile selection invalid")

    img_path = await save_uploaded_file(target_image, "target")
    metrics  = math_engine.calculate_shot_metrics(velocities_csv)

    log = models.ShotString(
        barrel_id=barrel_id,
        ammo_id=ammo_id,
        date_shot=date,
        velocities=velocities_csv,
        avg_velocity=metrics["avg"],
        extreme_spread=metrics["es"],
        standard_deviation=metrics["sd"],
        group_size_inches=group_size,
        target_image_path=img_path,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.delete("/performance-log/{log_id}")
def delete_performance_log(log_id: int, db: Session = Depends(get_db)):
    log = db.query(models.ShotString).filter(models.ShotString.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")
    db.delete(log)
    db.commit()
    return {"deleted": log_id}


@router.get("/performance-log/ammo/{ammo_id}")
def get_logs_for_ammo(ammo_id: int, db: Session = Depends(get_db)):
    logs = (
        db.query(models.ShotString)
        .options(joinedload(models.ShotString.barrel).joinedload(models.Barrel.firearm))
        .filter(models.ShotString.ammo_id == ammo_id)
        .order_by(models.ShotString.date_shot.desc())
        .all()
    )
    result = []
    for s in logs:
        firearm = s.barrel.firearm if s.barrel else None
        vel_list = [float(v) for v in s.velocities.split(",") if v.strip()] if s.velocities else []
        result.append({
            "id": s.id,
            "date": s.date_shot,
            "firearm_name": f"{firearm.brand} {firearm.model}" if firearm else "Unknown",
            "firearm_id": firearm.id if firearm else None,
            "caliber": s.barrel.caliber if s.barrel else "—",
            "shots": len(vel_list),
            "avg_velocity": s.avg_velocity,
            "group_size_inches": s.group_size_inches,
            "target_image_path": s.target_image_path,
        })
    return result


@router.get("/performance-log/firearm/{firearm_id}")
def get_logs_for_firearm(firearm_id: int, db: Session = Depends(get_db)):
    barrels = db.query(models.Barrel).filter(models.Barrel.firearm_id == firearm_id).all()
    barrel_ids = [b.id for b in barrels]
    if not barrel_ids:
        return []
    logs = (
        db.query(models.ShotString)
        .options(joinedload(models.ShotString.ammo), joinedload(models.ShotString.barrel))
        .filter(models.ShotString.barrel_id.in_(barrel_ids))
        .order_by(models.ShotString.date_shot.desc())
        .all()
    )
    result = []
    for s in logs:
        vel_list = [float(v) for v in s.velocities.split(",") if v.strip()] if s.velocities else []
        result.append({
            "id": s.id,
            "date": s.date_shot,
            "barrel_name": s.barrel.name or s.barrel.caliber,
            "caliber": s.barrel.caliber,
            "load_name": f"{s.ammo.brand} {s.ammo.line_or_powder or ''} {s.ammo.bullet_weight}gr".strip(),
            "bullet_bc": getattr(s.ammo, "bullet_bc", None),
            "shots": len(vel_list),
            "avg_velocity": s.avg_velocity,
            "extreme_spread": s.extreme_spread,
            "standard_deviation": s.standard_deviation,
            "group_size_inches": s.group_size_inches,
            "target_image_path": s.target_image_path,
        })
    return result
