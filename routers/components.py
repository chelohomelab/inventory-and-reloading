from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

import database as models
from dependencies import get_db
from schemas import PowderPatch, PrimerPatch, BulletComponentPatch, CasingPatch, DeductPayload

router = APIRouter()


# ── Serializers ────────────────────────────────────────────────────────────────

def _powder_dict(p: models.PowderInventory) -> dict:
    return {"id": p.id, "brand": p.brand, "name": p.name,
            "weight_lbs": p.weight_lbs, "price_paid": p.price_paid, "notes": p.notes}

def _primer_dict(p: models.PrimerInventory) -> dict:
    return {"id": p.id, "brand": p.brand, "primer_type": p.primer_type,
            "quantity": p.quantity, "price_paid": p.price_paid, "notes": p.notes}

def _bullet_dict(b: models.BulletInventory) -> dict:
    return {"id": b.id, "brand": b.brand, "product_line": b.product_line,
            "caliber": b.caliber, "weight_gr": b.weight_gr, "bullet_type": b.bullet_type,
            "bc_g1": b.bc_g1, "bc_g7": b.bc_g7,
            "quantity": b.quantity, "price_paid": b.price_paid, "notes": b.notes}

def _casing_dict(c: models.CasingInventory) -> dict:
    label = "New" if c.times_fired == 0 else f"{c.times_fired}x Fired"
    return {"id": c.id, "brand": c.brand, "caliber": c.caliber,
            "quantity": c.quantity, "times_fired": c.times_fired,
            "condition_label": label, "price_paid": c.price_paid, "notes": c.notes}

def _get_thresholds(db: Session) -> dict:
    rows = {s.key: float(s.value) for s in db.query(models.Setting).all()}
    return {
        "powder_lbs": rows.get("low_stock_powder_lbs", 0.5),
        "primers":    rows.get("low_stock_primers", 200),
        "bullets":    rows.get("low_stock_bullets", 100),
        "casings":    rows.get("low_stock_casings", 50),
    }


# ── Powders ────────────────────────────────────────────────────────────────────

@router.get("/components/powders/")
def list_powders(db: Session = Depends(get_db)):
    return [_powder_dict(p) for p in db.query(models.PowderInventory).all()]

@router.post("/components/powders/")
async def add_powder(
    brand: str = Form(...), name: str = Form(...),
    weight_lbs: float = Form(0.0), price: float = Form(0.0),
    notes: str = Form(None), db: Session = Depends(get_db),
):
    p = models.PowderInventory(brand=brand, name=name, weight_lbs=weight_lbs,
                               price_paid=price, notes=notes)
    db.add(p); db.commit(); db.refresh(p)
    return _powder_dict(p)

@router.patch("/components/powders/{item_id}")
def patch_powder(item_id: int, payload: PowderPatch, db: Session = Depends(get_db)):
    p = db.query(models.PowderInventory).filter(models.PowderInventory.id == item_id).first()
    if not p: raise HTTPException(404, "Not found")
    for k, v in payload.dict(exclude_none=True).items(): setattr(p, k, v)
    db.commit(); db.refresh(p)
    return _powder_dict(p)

@router.delete("/components/powders/{item_id}")
def delete_powder(item_id: int, db: Session = Depends(get_db)):
    p = db.query(models.PowderInventory).filter(models.PowderInventory.id == item_id).first()
    if not p: raise HTTPException(404, "Not found")
    db.delete(p); db.commit()
    return {"deleted": item_id}


# ── Primers ────────────────────────────────────────────────────────────────────

@router.get("/components/primers/")
def list_primers(db: Session = Depends(get_db)):
    return [_primer_dict(p) for p in db.query(models.PrimerInventory).all()]

@router.post("/components/primers/")
async def add_primer(
    brand: str = Form(...), primer_type: str = Form(...),
    quantity: int = Form(0), price: float = Form(0.0),
    notes: str = Form(None), db: Session = Depends(get_db),
):
    p = models.PrimerInventory(brand=brand, primer_type=primer_type,
                               quantity=quantity, price_paid=price, notes=notes)
    db.add(p); db.commit(); db.refresh(p)
    return _primer_dict(p)

@router.patch("/components/primers/{item_id}")
def patch_primer(item_id: int, payload: PrimerPatch, db: Session = Depends(get_db)):
    p = db.query(models.PrimerInventory).filter(models.PrimerInventory.id == item_id).first()
    if not p: raise HTTPException(404, "Not found")
    for k, v in payload.dict(exclude_none=True).items(): setattr(p, k, v)
    db.commit(); db.refresh(p)
    return _primer_dict(p)

@router.delete("/components/primers/{item_id}")
def delete_primer(item_id: int, db: Session = Depends(get_db)):
    p = db.query(models.PrimerInventory).filter(models.PrimerInventory.id == item_id).first()
    if not p: raise HTTPException(404, "Not found")
    db.delete(p); db.commit()
    return {"deleted": item_id}


# ── Bullets ────────────────────────────────────────────────────────────────────

@router.get("/components/bullets/")
def list_bullet_components(db: Session = Depends(get_db)):
    return [_bullet_dict(b) for b in db.query(models.BulletInventory).all()]

@router.post("/components/bullets/")
async def add_bullet_component(
    brand: str = Form(...), caliber: str = Form(...),
    weight_gr: float = Form(...), product_line: str = Form(None),
    bullet_type: str = Form(None), bc_g1: float = Form(None),
    bc_g7: float = Form(None), quantity: int = Form(0),
    price: float = Form(0.0), notes: str = Form(None),
    db: Session = Depends(get_db),
):
    b = models.BulletInventory(brand=brand, product_line=product_line, caliber=caliber,
                               weight_gr=weight_gr, bullet_type=bullet_type,
                               bc_g1=bc_g1, bc_g7=bc_g7,
                               quantity=quantity, price_paid=price, notes=notes)
    db.add(b); db.commit(); db.refresh(b)
    return _bullet_dict(b)

@router.patch("/components/bullets/{item_id}")
def patch_bullet_component(item_id: int, payload: BulletComponentPatch, db: Session = Depends(get_db)):
    b = db.query(models.BulletInventory).filter(models.BulletInventory.id == item_id).first()
    if not b: raise HTTPException(404, "Not found")
    for k, v in payload.dict(exclude_none=True).items(): setattr(b, k, v)
    db.commit(); db.refresh(b)
    return _bullet_dict(b)

@router.delete("/components/bullets/{item_id}")
def delete_bullet_component(item_id: int, db: Session = Depends(get_db)):
    b = db.query(models.BulletInventory).filter(models.BulletInventory.id == item_id).first()
    if not b: raise HTTPException(404, "Not found")
    db.delete(b); db.commit()
    return {"deleted": item_id}


# ── Casings ────────────────────────────────────────────────────────────────────

@router.get("/components/casings/")
def list_casings(db: Session = Depends(get_db)):
    return [_casing_dict(c) for c in db.query(models.CasingInventory).all()]

@router.post("/components/casings/")
async def add_casing(
    brand: str = Form(...), caliber: str = Form(...),
    quantity: int = Form(0), times_fired: int = Form(0),
    price: float = Form(0.0), notes: str = Form(None),
    db: Session = Depends(get_db),
):
    c = models.CasingInventory(brand=brand, caliber=caliber, quantity=quantity,
                               times_fired=times_fired, price_paid=price, notes=notes)
    db.add(c); db.commit(); db.refresh(c)
    return _casing_dict(c)

@router.patch("/components/casings/{item_id}")
def patch_casing(item_id: int, payload: CasingPatch, db: Session = Depends(get_db)):
    c = db.query(models.CasingInventory).filter(models.CasingInventory.id == item_id).first()
    if not c: raise HTTPException(404, "Not found")
    for k, v in payload.dict(exclude_none=True).items(): setattr(c, k, v)
    db.commit(); db.refresh(c)
    return _casing_dict(c)

@router.delete("/components/casings/{item_id}")
def delete_casing(item_id: int, db: Session = Depends(get_db)):
    c = db.query(models.CasingInventory).filter(models.CasingInventory.id == item_id).first()
    if not c: raise HTTPException(404, "Not found")
    db.delete(c); db.commit()
    return {"deleted": item_id}


# ── Deduct & Low-Stock ─────────────────────────────────────────────────────────

@router.post("/components/deduct/")
def deduct_components(payload: DeductPayload, db: Session = Depends(get_db)):
    t = _get_thresholds(db)
    warnings = []

    if payload.powder_inv_id and payload.powder_charge_gr and payload.rounds_loaded:
        p = db.query(models.PowderInventory).filter(models.PowderInventory.id == payload.powder_inv_id).first()
        if p:
            p.weight_lbs = max(0.0, (p.weight_lbs or 0) - (payload.powder_charge_gr * payload.rounds_loaded / 7000))
            db.commit()
            if p.weight_lbs < t["powder_lbs"]:
                warnings.append(f"Low powder: {p.brand} {p.name} — {p.weight_lbs:.3f} lbs remaining")

    if payload.primer_inv_id and payload.rounds_loaded:
        p = db.query(models.PrimerInventory).filter(models.PrimerInventory.id == payload.primer_inv_id).first()
        if p:
            p.quantity = max(0, (p.quantity or 0) - payload.rounds_loaded)
            db.commit()
            if p.quantity < t["primers"]:
                warnings.append(f"Low primers: {p.brand} {p.primer_type} — {p.quantity} remaining")

    if payload.bullet_inv_id and payload.rounds_loaded:
        b = db.query(models.BulletInventory).filter(models.BulletInventory.id == payload.bullet_inv_id).first()
        if b:
            b.quantity = max(0, (b.quantity or 0) - payload.rounds_loaded)
            db.commit()
            if b.quantity < t["bullets"]:
                warnings.append(f"Low bullets: {b.brand} {b.caliber} {b.weight_gr}gr — {b.quantity} remaining")

    if payload.casing_inv_id and payload.rounds_loaded:
        c = db.query(models.CasingInventory).filter(models.CasingInventory.id == payload.casing_inv_id).first()
        if c:
            c.quantity = max(0, (c.quantity or 0) - payload.rounds_loaded)
            db.commit()
            if c.quantity < t["casings"]:
                warnings.append(f"Low casings: {c.brand} {c.caliber} — {c.quantity} remaining")

    return {"ok": True, "warnings": warnings}


@router.get("/components/low-stock/")
def get_low_stock(db: Session = Depends(get_db)):
    t = _get_thresholds(db)
    items = []
    for p in db.query(models.PowderInventory).all():
        if (p.weight_lbs or 0) < t["powder_lbs"]:
            items.append({"type": "powder", "label": f"{p.brand} {p.name}", "value": f"{p.weight_lbs:.3f} lbs"})
    for p in db.query(models.PrimerInventory).all():
        if (p.quantity or 0) < t["primers"]:
            items.append({"type": "primer", "label": f"{p.brand} {p.primer_type}", "value": f"{p.quantity}"})
    for b in db.query(models.BulletInventory).all():
        if (b.quantity or 0) < t["bullets"]:
            items.append({"type": "bullet", "label": f"{b.brand} {b.caliber} {b.weight_gr}gr", "value": f"{b.quantity}"})
    for c in db.query(models.CasingInventory).all():
        if (c.quantity or 0) < t["casings"]:
            items.append({"type": "casing", "label": f"{c.brand} {c.caliber}", "value": f"{c.quantity}"})
    return items
