import os
import uuid
import database as models   # renamed alias: "models" to avoid collision with the SQLAlchemy session param "db"
import math_engine
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Homelab Modular Firearm Catalog")
models.init_db()

# Mount the static uploads folder
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


# ── Template Routes ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/index.html", response_class=HTMLResponse)
async def read_index_explicit(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/firearm-detail.html", response_class=HTMLResponse)
async def read_detail(request: Request):
    return templates.TemplateResponse("firearm-detail.html", {"request": request})

@app.get("/ammo-detail.html", response_class=HTMLResponse)
async def read_ammo_detail(request: Request):
    return templates.TemplateResponse("ammo-detail.html", {"request": request})


# ── DB Session Dependency ──────────────────────────────────────────────────────

def get_db():
    session = models.SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ── Helper ─────────────────────────────────────────────────────────────────────

async def save_uploaded_file(file: UploadFile, prefix: str) -> Optional[str]:
    if not file or not file.filename:
        return None
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{prefix}_{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    return f"/static/uploads/{unique_filename}"


# ── Firearms ───────────────────────────────────────────────────────────────────

@app.post("/firearms/")
async def create_firearm(
    brand: str = Form(...),
    model: str = Form(...),
    price: float = Form(...),
    caliber: str = Form(...),
    frame_type: str = Form(...),
    twist_rate: str = Form(None),
    scope_optic: str = Form(None),
    image_1: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """Creates a Firearm + primary Barrel. Optionally creates a linked Scope."""
    img_path = await save_uploaded_file(image_1, "firearm")

    new_gun = models.Firearm(
        brand=brand, model=model, price_paid=price,
        frame_type=frame_type, image_path_1=img_path
    )
    db.add(new_gun)
    db.flush()

    db.add(models.Barrel(
        firearm_id=new_gun.id, caliber=caliber,
        name="Primary", twist_rate=twist_rate, price_paid=0.0
    ))

    if scope_optic and scope_optic.strip() and scope_optic.strip().lower() not in ("none",):
        new_scope = models.Scope(brand=scope_optic.strip(), model="", units="MOA", price_paid=0.0)
        db.add(new_scope)
        db.flush()
        new_gun.scope_id = new_scope.id

    db.commit()
    db.refresh(new_gun)
    return new_gun


@app.get("/firearms/{firearm_id}")
def get_firearm(firearm_id: int, db: Session = Depends(get_db)):
    """Returns full firearm record with barrels, scope, accessories, and furniture."""
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


class SoldPayload(BaseModel):
    is_sold: bool
    price_sold: float = 0.0


class FirearmPatchPayload(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    caliber: Optional[str] = None
    scope_optic: Optional[str] = None
    price_paid: Optional[float] = None


@app.patch("/firearms/{firearm_id}")
def patch_firearm(firearm_id: int, payload: FirearmPatchPayload, db: Session = Depends(get_db)):
    """Partial update of a firearm's core fields from the detail-page edit form."""
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
        primary_barrel = (
            db.query(models.Barrel)
            .filter(models.Barrel.firearm_id == firearm_id)
            .first()
        )
        if primary_barrel:
            primary_barrel.caliber = payload.caliber

    if payload.scope_optic is not None:
        optic_val = payload.scope_optic.strip()
        if not optic_val or optic_val.lower() == "none":
            gun.scope_id = None
        else:
            existing_scope = db.query(models.Scope).filter(models.Scope.brand == optic_val).first()
            if existing_scope:
                gun.scope_id = existing_scope.id
            else:
                new_scope = models.Scope(brand=optic_val, model="", units="MOA", price_paid=0.0)
                db.add(new_scope)
                db.flush()
                gun.scope_id = new_scope.id

    db.commit()
    db.refresh(gun)
    return gun


def mark_firearm_sold(firearm_id: int, payload: SoldPayload, db: Session = Depends(get_db)):
    """Flags a firearm as sold and records the sale price."""
    gun = db.query(models.Firearm).filter(models.Firearm.id == firearm_id).first()
    if not gun:
        raise HTTPException(status_code=404, detail="Firearm not found")

    # Add is_sold / price_sold columns if they don't exist yet — see database.py note
    gun.is_sold = payload.is_sold
    gun.price_sold = payload.price_sold
    db.commit()
    db.refresh(gun)
    return gun


@app.post("/firearms/{firearm_id}/update-photo/")
async def update_firearm_photo(
    firearm_id: int,
    image_1: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Replaces the primary profile photo of a firearm."""
    gun = db.query(models.Firearm).filter(models.Firearm.id == firearm_id).first()
    if not gun:
        raise HTTPException(status_code=404, detail="Firearm not found")

    img_path = await save_uploaded_file(image_1, "firearm")
    gun.image_path_1 = img_path
    db.commit()
    db.refresh(gun)
    return gun


@app.get("/catalog/")
def get_entire_catalog(db: Session = Depends(get_db)):
    """
    Returns all firearms with their first barrel loaded so the
    frontend can display caliber without a second request.
    """
    guns = (
        db.query(models.Firearm)
        .options(joinedload(models.Firearm.barrels))
        .all()
    )

    result = []
    for gun in guns:
        primary_barrel = gun.barrels[0] if gun.barrels else None
        result.append({
            "id": gun.id,
            "brand": gun.brand,
            "model": gun.model,
            "frame_type": gun.frame_type,
            "price_paid": gun.price_paid,
            "image_path_1": gun.image_path_1,
            "is_sold": getattr(gun, "is_sold", False),
            "price_sold": getattr(gun, "price_sold", None),
            # Caliber pulled from the primary barrel
            "caliber": primary_barrel.caliber if primary_barrel else None,
        })
    return result


# ── Barrels ────────────────────────────────────────────────────────────────────

@app.post("/barrels/")
async def create_barrel(
    firearm_id: int = Form(...),
    caliber: str = Form(...),
    name: str = Form(None),
    price: float = Form(0.0),
    twist: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    img_path = await save_uploaded_file(image, "barrel")
    new_barrel = models.Barrel(
        firearm_id=firearm_id, caliber=caliber, name=name,
        price_paid=price, twist_rate=twist, image_path=img_path
    )
    db.add(new_barrel)
    db.commit()
    db.refresh(new_barrel)
    return new_barrel


# ── Scopes ─────────────────────────────────────────────────────────────────────

def _scope_dict(s: models.Scope) -> dict:
    mounted_on = None
    mounted_firearm_id = None
    mounted_barrel_id = None
    mount_type = None
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


@app.get("/scopes/")
def list_scopes(db: Session = Depends(get_db)):
    scopes = (
        db.query(models.Scope)
        .options(joinedload(models.Scope.firearms), joinedload(models.Scope.barrels))
        .all()
    )
    return [_scope_dict(s) for s in scopes]


@app.post("/scopes/")
async def create_scope(
    brand: str = Form(...),
    model: str = Form(...),
    units: str = Form("MOA"),
    price: float = Form(0.0),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    img_path = await save_uploaded_file(image, "scope")
    new_scope = models.Scope(brand=brand, model=model, units=units, price_paid=price, image_path=img_path)
    db.add(new_scope)
    db.commit()
    db.refresh(new_scope)
    return _scope_dict(
        db.query(models.Scope)
        .options(joinedload(models.Scope.firearms), joinedload(models.Scope.barrels))
        .filter(models.Scope.id == new_scope.id).first()
    )


@app.get("/available-mounts/")
def get_available_mounts(for_scope_id: int = None, db: Session = Depends(get_db)):
    """
    Returns all firearms and TC barrels that have no scope mounted,
    plus the current mount of for_scope_id (so it appears in the dropdown).
    """
    firearms = (
        db.query(models.Firearm)
        .filter(
            models.Firearm.is_sold == False,
            (models.Firearm.scope_id == None) | (models.Firearm.scope_id == for_scope_id)
        )
        .options(joinedload(models.Firearm.barrels))
        .all()
    )
    tc_barrels = (
        db.query(models.Barrel)
        .filter(
            models.Barrel.tc_platform.isnot(None),
            (models.Barrel.scope_id == None) | (models.Barrel.scope_id == for_scope_id)
        )
        .all()
    )
    return {
        "firearms": [
            {"id": f.id, "label": f"{f.brand} {f.model}", "type": "firearm"}
            for f in firearms
        ],
        "tc_barrels": [
            {"id": b.id, "label": f"{b.tc_platform} {b.caliber}", "type": "barrel"}
            for b in tc_barrels
        ],
    }


class ScopeMountPayload(BaseModel):
    mount_type: Optional[str] = None   # "firearm", "barrel", or null to unmount
    mount_id: Optional[int] = None


@app.patch("/scopes/{scope_id}/mount")
def mount_scope(scope_id: int, payload: ScopeMountPayload, db: Session = Depends(get_db)):
    """Mounts or unmounts a scope. Clears any previous mount first."""
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
    updated = (
        db.query(models.Scope)
        .options(joinedload(models.Scope.firearms), joinedload(models.Scope.barrels))
        .filter(models.Scope.id == scope_id).first()
    )
    return _scope_dict(updated)


# ── Thompson Center ────────────────────────────────────────────────────────────

def _tc_receiver_dict(r: models.TCReceiver) -> dict:
    return {
        "id": r.id,
        "platform": r.platform,
        "serial_number": r.serial_number,
        "price_paid": r.price_paid,
        "image_path": r.image_path,
        "is_sold": r.is_sold,
        "price_sold": r.price_sold,
    }

def _tc_barrel_dict(b: models.Barrel) -> dict:
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


@app.get("/tc-receivers/")
def list_tc_receivers(db: Session = Depends(get_db)):
    return [_tc_receiver_dict(r) for r in db.query(models.TCReceiver).all()]


@app.post("/tc-receivers/")
async def create_tc_receiver(
    platform: str = Form(...),
    serial_number: str = Form(None),
    price: float = Form(0.0),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    img_path = await save_uploaded_file(image, "tc_receiver")
    r = models.TCReceiver(platform=platform, serial_number=serial_number,
                          price_paid=price, image_path=img_path)
    db.add(r)
    db.commit()
    db.refresh(r)
    return _tc_receiver_dict(r)


@app.post("/tc-receivers/{receiver_id}/mark-sold/")
def mark_tc_receiver_sold(receiver_id: int, payload: SoldPayload, db: Session = Depends(get_db)):
    r = db.query(models.TCReceiver).filter(models.TCReceiver.id == receiver_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="TC Receiver not found")
    r.is_sold = payload.is_sold
    r.price_sold = payload.price_sold
    db.commit()
    db.refresh(r)
    return _tc_receiver_dict(r)


@app.get("/tc-barrels/")
def list_tc_barrels(db: Session = Depends(get_db)):
    barrels = db.query(models.Barrel).filter(models.Barrel.tc_platform.isnot(None)).all()
    return [_tc_barrel_dict(b) for b in barrels]


@app.post("/tc-barrels/")
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
    db: Session = Depends(get_db)
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
        image_path=img_path
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return _tc_barrel_dict(b)


# ── Ammunition ─────────────────────────────────────────────────────────────────

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


@app.post("/ammo/")
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
    db: Session = Depends(get_db)
):
    img_path = await save_uploaded_file(image, "ammo")
    new_ammo = models.Ammo(
        brand=recipe_name or brand or "Unknown",
        caliber=caliber,
        bullet_type=bullet_id or bullet_type or "Unknown",
        bullet_weight=bullet_weight,
        bullet_bc=bullet_bc,
        is_handload=is_handload,
        line_or_powder=ammo_model or powder_id,
        charge_weight=powder_charge,
        coal=coal,
        image_path=img_path
    )
    db.add(new_ammo)
    db.commit()
    db.refresh(new_ammo)
    return _ammo_dict(new_ammo)


@app.get("/ammo/")
def list_ammo(db: Session = Depends(get_db)):
    return [_ammo_dict(a) for a in db.query(models.Ammo).all()]


@app.get("/ammo/{ammo_id}")
def get_ammo(ammo_id: int, db: Session = Depends(get_db)):
    a = db.query(models.Ammo).filter(models.Ammo.id == ammo_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Ammo not found")
    usage = db.query(models.ShotString).filter(models.ShotString.ammo_id == ammo_id).count()
    result = _ammo_dict(a)
    result["usage_count"] = usage
    return result


class AmmoPatchPayload(BaseModel):
    brand: Optional[str] = None
    caliber: Optional[str] = None
    bullet_type: Optional[str] = None
    bullet_weight: Optional[float] = None
    bullet_bc: Optional[float] = None
    line_or_powder: Optional[str] = None
    charge_weight: Optional[float] = None
    coal: Optional[float] = None


@app.patch("/ammo/{ammo_id}")
def patch_ammo(ammo_id: int, payload: AmmoPatchPayload, db: Session = Depends(get_db)):
    a = db.query(models.Ammo).filter(models.Ammo.id == ammo_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Ammo not found")
    for field, value in payload.dict(exclude_none=True).items():
        setattr(a, field, value)
    db.commit()
    db.refresh(a)
    return _ammo_dict(a)


@app.delete("/ammo/{ammo_id}")
def delete_ammo(ammo_id: int, db: Session = Depends(get_db)):
    a = db.query(models.Ammo).filter(models.Ammo.id == ammo_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Ammo not found")
    usage = db.query(models.ShotString).filter(models.ShotString.ammo_id == ammo_id).count()
    if usage > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {usage} range session(s) reference this load. Delete those sessions first."
        )
    db.delete(a)
    db.commit()
    return {"deleted": ammo_id}


# ── Reloading Components ───────────────────────────────────────────────────────

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


@app.get("/components/powders/")
def list_powders(db: Session = Depends(get_db)):
    return [_powder_dict(p) for p in db.query(models.PowderInventory).all()]

@app.post("/components/powders/")
async def add_powder(
    brand: str = Form(...), name: str = Form(...),
    weight_lbs: float = Form(0.0), price: float = Form(0.0),
    notes: str = Form(None), db: Session = Depends(get_db)
):
    p = models.PowderInventory(brand=brand, name=name, weight_lbs=weight_lbs,
                               price_paid=price, notes=notes)
    db.add(p); db.commit(); db.refresh(p)
    return _powder_dict(p)

class PowderPatch(BaseModel):
    brand: Optional[str] = None
    name: Optional[str] = None
    weight_lbs: Optional[float] = None
    price_paid: Optional[float] = None
    notes: Optional[str] = None

@app.patch("/components/powders/{item_id}")
def patch_powder(item_id: int, payload: PowderPatch, db: Session = Depends(get_db)):
    p = db.query(models.PowderInventory).filter(models.PowderInventory.id == item_id).first()
    if not p: raise HTTPException(status_code=404, detail="Not found")
    for k, v in payload.dict(exclude_none=True).items(): setattr(p, k, v)
    db.commit(); db.refresh(p)
    return _powder_dict(p)

@app.delete("/components/powders/{item_id}")
def delete_powder(item_id: int, db: Session = Depends(get_db)):
    p = db.query(models.PowderInventory).filter(models.PowderInventory.id == item_id).first()
    if not p: raise HTTPException(status_code=404, detail="Not found")
    db.delete(p); db.commit()
    return {"deleted": item_id}


@app.get("/components/primers/")
def list_primers(db: Session = Depends(get_db)):
    return [_primer_dict(p) for p in db.query(models.PrimerInventory).all()]

@app.post("/components/primers/")
async def add_primer(
    brand: str = Form(...), primer_type: str = Form(...),
    quantity: int = Form(0), price: float = Form(0.0),
    notes: str = Form(None), db: Session = Depends(get_db)
):
    p = models.PrimerInventory(brand=brand, primer_type=primer_type,
                               quantity=quantity, price_paid=price, notes=notes)
    db.add(p); db.commit(); db.refresh(p)
    return _primer_dict(p)

class PrimerPatch(BaseModel):
    brand: Optional[str] = None
    primer_type: Optional[str] = None
    quantity: Optional[int] = None
    price_paid: Optional[float] = None
    notes: Optional[str] = None

@app.patch("/components/primers/{item_id}")
def patch_primer(item_id: int, payload: PrimerPatch, db: Session = Depends(get_db)):
    p = db.query(models.PrimerInventory).filter(models.PrimerInventory.id == item_id).first()
    if not p: raise HTTPException(status_code=404, detail="Not found")
    for k, v in payload.dict(exclude_none=True).items(): setattr(p, k, v)
    db.commit(); db.refresh(p)
    return _primer_dict(p)

@app.delete("/components/primers/{item_id}")
def delete_primer(item_id: int, db: Session = Depends(get_db)):
    p = db.query(models.PrimerInventory).filter(models.PrimerInventory.id == item_id).first()
    if not p: raise HTTPException(status_code=404, detail="Not found")
    db.delete(p); db.commit()
    return {"deleted": item_id}


@app.get("/components/bullets/")
def list_bullet_components(db: Session = Depends(get_db)):
    return [_bullet_dict(b) for b in db.query(models.BulletInventory).all()]

@app.post("/components/bullets/")
async def add_bullet_component(
    brand: str = Form(...), caliber: str = Form(...),
    weight_gr: float = Form(...), product_line: str = Form(None),
    bullet_type: str = Form(None), bc_g1: float = Form(None),
    bc_g7: float = Form(None), quantity: int = Form(0),
    price: float = Form(0.0), notes: str = Form(None),
    db: Session = Depends(get_db)
):
    b = models.BulletInventory(brand=brand, product_line=product_line, caliber=caliber,
                               weight_gr=weight_gr, bullet_type=bullet_type,
                               bc_g1=bc_g1, bc_g7=bc_g7,
                               quantity=quantity, price_paid=price, notes=notes)
    db.add(b); db.commit(); db.refresh(b)
    return _bullet_dict(b)

class BulletComponentPatch(BaseModel):
    brand: Optional[str] = None
    product_line: Optional[str] = None
    caliber: Optional[str] = None
    weight_gr: Optional[float] = None
    bullet_type: Optional[str] = None
    bc_g1: Optional[float] = None
    bc_g7: Optional[float] = None
    quantity: Optional[int] = None
    price_paid: Optional[float] = None
    notes: Optional[str] = None

@app.patch("/components/bullets/{item_id}")
def patch_bullet_component(item_id: int, payload: BulletComponentPatch, db: Session = Depends(get_db)):
    b = db.query(models.BulletInventory).filter(models.BulletInventory.id == item_id).first()
    if not b: raise HTTPException(status_code=404, detail="Not found")
    for k, v in payload.dict(exclude_none=True).items(): setattr(b, k, v)
    db.commit(); db.refresh(b)
    return _bullet_dict(b)

@app.delete("/components/bullets/{item_id}")
def delete_bullet_component(item_id: int, db: Session = Depends(get_db)):
    b = db.query(models.BulletInventory).filter(models.BulletInventory.id == item_id).first()
    if not b: raise HTTPException(status_code=404, detail="Not found")
    db.delete(b); db.commit()
    return {"deleted": item_id}


# ── Performance Logs ───────────────────────────────────────────────────────────

@app.post("/performance-log/")
async def log_group(
    barrel_id: int = Form(...),
    ammo_id: int = Form(...),
    date: str = Form(...),
    velocities_csv: str = Form(None),
    group_size: float = Form(None),
    target_image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    barrel = db.query(models.Barrel).filter(models.Barrel.id == barrel_id).first()
    ammo = db.query(models.Ammo).filter(models.Ammo.id == ammo_id).first()
    if not barrel or not ammo:
        raise HTTPException(status_code=404, detail="Barrel or Ammo profile selection invalid")

    img_path = await save_uploaded_file(target_image, "target")
    metrics = math_engine.calculate_shot_metrics(velocities_csv)

    log = models.ShotString(
        barrel_id=barrel_id,
        ammo_id=ammo_id,
        date_shot=date,
        velocities=velocities_csv,
        avg_velocity=metrics["avg"],
        extreme_spread=metrics["es"],
        standard_deviation=metrics["sd"],
        group_size_inches=group_size,
        target_image_path=img_path
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@app.delete("/performance-log/{log_id}")
def delete_performance_log(log_id: int, db: Session = Depends(get_db)):
    log = db.query(models.ShotString).filter(models.ShotString.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")
    db.delete(log)
    db.commit()
    return {"deleted": log_id}


@app.get("/performance-log/ammo/{ammo_id}")
def get_performance_logs_for_ammo(ammo_id: int, db: Session = Depends(get_db)):
    """Returns all range sessions that used a specific ammo load."""
    logs = (
        db.query(models.ShotString)
        .options(
            joinedload(models.ShotString.barrel).joinedload(models.Barrel.firearm)
        )
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


@app.get("/performance-log/firearm/{firearm_id}")
def get_performance_logs_for_firearm(firearm_id: int, db: Session = Depends(get_db)):
    """
    Returns all shot strings for every barrel on a given firearm.
    Used by the firearm-detail page's performance matrix.
    """
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