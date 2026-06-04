import os
import uuid
import database as db
import math_engine
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

app = FastAPI(title="Homelab Modular Firearm Catalog")
db.init_db()

# --- NEW: Mount the static uploads folder so you can see images in your browser ---
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup template routing engine
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Changed from template_response to TemplateResponse
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/index.html", response_class=HTMLResponse)
async def read_index_explicit(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/firearm-detail.html", response_class=HTMLResponse)
async def read_detail(request: Request):
    return templates.TemplateResponse("firearm-detail.html", {"request": request})

def get_db():
    database = db.SessionLocal()
    try:
        yield database
    finally:
        database.close()

# --- FIREARMS (Configured for Pistol or Rifle Frames) ---
@app.post("/firearms/")
async def create_firearm(
    brand: str = Form(...),
    model: str = Form(...),
    price: float = Form(...),
    caliber: str = Form(...), # ADD THIS
    frame_type: str = Form(...),
    image_1: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Save image logic...
    
    new_gun = db.Firearm(
        brand=brand,
        model=model,
        price_paid=price,
        caliber=caliber, # ADD THIS
        frame_type=frame_type,
        image_path_1=saved_image_path
    )
    db.add(new_gun)
    db.commit()
    return new_gun

# --- FURNITURE MANAGEMENT ---
@app.post("/furniture/")
async def add_furniture(
    furniture_type: str = Form(...), 
    material: str = Form(...), 
    price: float = Form(0.0), 
    firearm_id: int = Form(None), 
    barrel_id: int = Form(None), 
    image: UploadFile = File(None),
    database: Session = Depends(get_db)
):
    img_path = await save_uploaded_file(image, "furniture")
    new_furniture = db.Furniture(
        type=furniture_type, material=material, price_paid=price, 
        firearm_id=firearm_id, barrel_id=barrel_id, image_path=img_path
    )
    database.add(new_furniture)
    database.commit()
    database.refresh(new_furniture)
    return new_furniture

# --- BARRELS ---
@app.post("/barrels/")
async def create_barrel(
    firearm_id: int = Form(...), 
    caliber: str = Form(...), 
    name: str = Form(None), 
    price: float = Form(0.0), 
    twist: str = Form(None), 
    image: UploadFile = File(None),
    database: Session = Depends(get_db)
):
    img_path = await save_uploaded_file(image, "barrel")
    new_barrel = db.Barrel(
        firearm_id=firearm_id, caliber=caliber, name=name, 
        price_paid=price, twist_rate=twist, image_path=img_path
    )
    database.add(new_barrel)
    database.commit()
    database.refresh(new_barrel)
    return new_barrel

# --- SCOPES ---
@app.post("/scopes/")
async def create_scope(
    brand: str = Form(...), 
    model: str = Form(...), 
    units: str = Form("MOA"), 
    price: float = Form(0.0), 
    image: UploadFile = File(None),
    database: Session = Depends(get_db)
):
    img_path = await save_uploaded_file(image, "scope")
    new_scope = db.Scope(brand=brand, model=model, units=units, price_paid=price, image_path=img_path)
    database.add(new_scope)
    database.commit()
    database.refresh(new_scope)
    return new_scope

# --- AMMUNITION ---
@app.post("/ammo/")
async def add_ammo(
    brand: str = Form(...), 
    bullet_type: str = Form(...), 
    weight: float = Form(...), 
    is_handload: bool = Form(False), 
    powder_or_line: str = Form(None), 
    image: UploadFile = File(None),
    database: Session = Depends(get_db)
):
    img_path = await save_uploaded_file(image, "ammo")
    new_ammo = db.Ammo(
        brand=brand, bullet_type=bullet_type, bullet_weight=weight, 
        is_handload=is_handload, line_or_powder=powder_or_line, image_path=img_path
    )
    database.add(new_ammo)
    database.commit()
    database.refresh(new_ammo)
    return new_ammo

# --- PERFORMANCE LOGS ---
@app.post("/performance-log/")
async def log_group(
    barrel_id: int = Form(...),
    ammo_id: int = Form(...),
    date: str = Form(...),
    velocities_csv: str = Form(None),
    group_size: float = Form(None),
    target_image: UploadFile = File(None),  # Accepts an optional target image file
    database: Session = Depends(get_db)
):
    # Verify components exist
    barrel = database.query(db.Barrel).filter(db.Barrel.id == barrel_id).first()
    ammo = database.query(db.Ammo).filter(db.Ammo.id == ammo_id).first()
    if not barrel or not ammo:
        raise HTTPException(status_code=404, detail="Barrel or Ammo profile selection invalid")
        
    # Process image if provided
    saved_image_path = None
    if target_image:
        # Generate a unique filename using a UUID to prevent overwriting files with the same name
        file_extension = os.path.splitext(target_image.filename)[1]
        unique_filename = f"target_{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Read the uploaded file chunks and save them locally to your homelab
        with open(file_path, "wb") as buffer:
            content = await target_image.read()
            buffer.write(content)
            
        saved_image_path = f"/static/uploads/{unique_filename}"

    # Run the automatic calculations on shot velocities
    metrics = math_engine.calculate_shot_metrics(velocities_csv)
    
    log = db.ShotString(
        barrel_id=barrel_id,
        ammo_id=ammo_id,
        date_shot=date,
        velocities=velocities_csv,
        avg_velocity=metrics["avg"],
        extreme_spread=metrics["es"],
        standard_deviation=metrics["sd"],
        group_size_inches=group_size,
        target_image_path=saved_image_path  # Saves the accessible path to DB
    )
    
    database.add(log)
    database.commit()
    database.refresh(log)
    return log

# --- HELPER FUNCTION FOR SAVING IMAGES ---
async def save_uploaded_file(file: UploadFile, prefix: str) -> str:
    if not file:
        return None
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{prefix}_{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    return f"/static/uploads/{unique_filename}"

@app.get("/catalog/")
def get_entire_catalog(database: Session = Depends(get_db)):
    return database.query(db.Firearm).all()
