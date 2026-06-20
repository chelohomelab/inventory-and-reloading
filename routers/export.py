import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

import database as models
from dependencies import get_db

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/firearms.csv")
def export_firearms(db: Session = Depends(get_db)):
    guns = (
        db.query(models.Firearm)
        .options(joinedload(models.Firearm.barrels))
        .filter(models.Firearm.is_deleted == False)
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Brand", "Model", "Frame Type", "Caliber", "Twist Rate", "Serial Number", "Price Paid", "Is Sold", "Price Sold"])
    for g in guns:
        barrel = g.barrels[0] if g.barrels else None
        w.writerow([
            g.brand, g.model, g.frame_type,
            barrel.caliber if barrel else "",
            barrel.twist_rate if barrel else "",
            getattr(g, "serial_number", ""),
            g.price_paid or 0,
            "Yes" if getattr(g, "is_sold", False) else "No",
            getattr(g, "price_sold", "") or "",
        ])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=firearms.csv"})


@router.get("/scopes.csv")
def export_scopes(db: Session = Depends(get_db)):
    scopes = db.query(models.Scope).filter(models.Scope.is_deleted == False).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Brand", "Model", "Magnification", "Units", "Quantity", "Price Paid"])
    for s in scopes:
        w.writerow([s.brand, s.model, s.magnification, s.units, getattr(s, "quantity", 1) or 1, s.price_paid or 0])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=scopes.csv"})


@router.get("/ammo.csv")
def export_ammo(db: Session = Depends(get_db)):
    ammos = db.query(models.Ammo).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Brand", "Caliber", "Line/Powder", "Bullet Weight", "Bullet Type", "BC", "Sealed Boxes", "Open Rounds", "Rounds/Box", "Price Paid", "Handload"])
    for a in ammos:
        w.writerow([
            a.brand, getattr(a, "caliber", ""), a.line_or_powder,
            a.bullet_weight, a.bullet_type, getattr(a, "bullet_bc", ""),
            getattr(a, "qty_sealed", 0) or 0, getattr(a, "qty_open", 0) or 0,
            getattr(a, "rounds_per_box", 20) or 20,
            getattr(a, "price_paid", 0) or 0,
            "Yes" if a.is_handload else "No",
        ])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=ammo.csv"})


@router.get("/components.csv")
def export_components(db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Type", "Brand", "Name/Model", "Caliber", "Weight/Qty", "Price Paid", "Notes"])
    for p in db.query(models.PowderInventory).all():
        w.writerow(["Powder", p.brand, p.name, "", f"{p.weight_lbs} lbs", p.price_paid or 0, p.notes or ""])
    for p in db.query(models.PrimerInventory).all():
        w.writerow(["Primer", p.brand, p.model, "", p.quantity, p.price_paid or 0, p.notes or ""])
    for b in db.query(models.BulletInventory).all():
        w.writerow(["Bullet", b.brand, b.product_line, getattr(b, "caliber", ""), f"{b.weight_gr}gr", b.price_paid or 0, b.notes or ""])
    for c in db.query(models.CasingInventory).all():
        w.writerow(["Casing", c.brand, "", c.caliber, c.quantity, c.price_paid or 0, c.notes or ""])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=components.csv"})
