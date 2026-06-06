from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

import os as _os
_os.makedirs("data", exist_ok=True)

DATABASE_URL = "sqlite:///./data/reloading.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Kept for backward-compat with existing DB rows; not exposed in new UI
class Furniture(Base):
    __tablename__ = "furniture"
    id = Column(Integer, primary_key=True, index=True)
    firearm_id = Column(Integer, ForeignKey("firearms.id"), nullable=True)
    barrel_id = Column(Integer, ForeignKey("barrels.id"), nullable=True)
    type = Column(String)
    material = Column(String)
    price_paid = Column(Float, default=0.0)
    brand = Column(String, nullable=True)
    image_path = Column(String, nullable=True)

class Scope(Base):
    __tablename__ = "scopes"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String)
    model = Column(String)
    units = Column(String, default="MOA")
    price_paid = Column(Float, default=0.0)
    image_path = Column(String, nullable=True)

    firearms = relationship("Firearm", back_populates="scope")
    barrels = relationship("Barrel", back_populates="scope")

class Accessory(Base):
    __tablename__ = "accessories"
    id = Column(Integer, primary_key=True, index=True)
    firearm_id = Column(Integer, ForeignKey("firearms.id"), nullable=True)
    barrel_id = Column(Integer, ForeignKey("barrels.id"), nullable=True)
    name = Column(String)
    price_paid = Column(Float, default=0.0)

# Thompson Center receiver (Encore / Contender) — tracked separately from barrels
class TCReceiver(Base):
    __tablename__ = "tc_receivers"
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String)           # "Encore" or "Contender"
    serial_number = Column(String, nullable=True)
    price_paid = Column(Float, default=0.0)
    image_path = Column(String, nullable=True)
    is_sold = Column(Boolean, default=False)
    price_sold = Column(Float, nullable=True)

class Firearm(Base):
    __tablename__ = "firearms"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String)
    model = Column(String)
    frame_type = Column(String, default="Rifle")
    price_paid = Column(Float, default=0.0)
    image_path_1 = Column(String, nullable=True)
    image_path_2 = Column(String, nullable=True)
    scope_id = Column(Integer, ForeignKey("scopes.id"), nullable=True)
    is_sold = Column(Boolean, default=False)
    price_sold = Column(Float, nullable=True)

    scope = relationship("Scope", back_populates="firearms")
    barrels = relationship("Barrel", back_populates="firearm", cascade="all, delete-orphan")
    accessories = relationship("Accessory", foreign_keys=[Accessory.firearm_id])

class Barrel(Base):
    __tablename__ = "barrels"
    id = Column(Integer, primary_key=True, index=True)
    # nullable so TC barrels can exist without a parent Firearm
    firearm_id = Column(Integer, ForeignKey("firearms.id"), nullable=True)
    name = Column(String, nullable=True)
    caliber = Column(String)
    twist_rate = Column(String, nullable=True)
    price_paid = Column(Float, default=0.0)
    scope_id = Column(Integer, ForeignKey("scopes.id"), nullable=True)
    image_path = Column(String, nullable=True)
    # TC-specific fields (null for regular rifle barrels)
    tc_platform = Column(String, nullable=True)     # "Encore" or "Contender"
    barrel_length = Column(String, nullable=True)
    hardware_color = Column(String, nullable=True)
    is_threaded = Column(Boolean, default=False)
    has_muzzle_brake = Column(Boolean, default=False)

    firearm = relationship("Firearm", back_populates="barrels")
    scope = relationship("Scope", back_populates="barrels")
    accessories = relationship("Accessory", foreign_keys=[Accessory.barrel_id])
    shot_strings = relationship("ShotString", back_populates="barrel")

# --- RELOADING COMPONENT INVENTORY ---

class CasingInventory(Base):
    __tablename__ = "casing_inventory"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String)
    caliber = Column(String)
    quantity = Column(Integer, default=0)
    times_fired = Column(Integer, default=0)   # 0 = new, 1 = once fired, etc.
    price_paid = Column(Float, default=0.0)
    notes = Column(String, nullable=True)

class PowderInventory(Base):
    __tablename__ = "powder_inventory"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String)
    name = Column(String)               # e.g., "H4350", "Varget"
    weight_lbs = Column(Float, default=0.0)  # pounds on hand
    price_paid = Column(Float, default=0.0)
    notes = Column(String, nullable=True)

class PrimerInventory(Base):
    __tablename__ = "primer_inventory"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String)
    primer_type = Column(String)        # "Large Rifle", "Small Rifle Magnum", etc.
    quantity = Column(Integer, default=0)
    price_paid = Column(Float, default=0.0)   # per 1000
    notes = Column(String, nullable=True)

class BulletInventory(Base):
    __tablename__ = "bullet_inventory"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String)
    product_line = Column(String, nullable=True)  # "ELD-M", "MatchKing", "Hybrid"
    caliber = Column(String)
    weight_gr = Column(Float)
    bullet_type = Column(String, nullable=True)   # "BTHP", "Hybrid", "FMJ"
    bc_g1 = Column(Float, nullable=True)
    bc_g7 = Column(Float, nullable=True)
    quantity = Column(Integer, default=0)
    price_paid = Column(Float, default=0.0)       # per box/unit price
    notes = Column(String, nullable=True)

# --- AMMUNITION & PERFORMANCE LOGS ---
class Ammo(Base):
    __tablename__ = "ammo"
    id = Column(Integer, primary_key=True, index=True)
    is_handload = Column(Boolean, default=False)
    brand = Column(String)
    caliber = Column(String, nullable=True)
    line_or_powder = Column(String)
    bullet_weight = Column(Float)
    bullet_type = Column(String)
    bullet_bc = Column(Float, nullable=True)
    charge_weight = Column(Float, nullable=True)
    coal = Column(Float, nullable=True)
    image_path = Column(String, nullable=True)
    
    shot_strings = relationship("ShotString", back_populates="ammo")

class ShotString(Base):
    __tablename__ = "shot_strings"
    id = Column(Integer, primary_key=True, index=True)
    barrel_id = Column(Integer, ForeignKey("barrels.id"))
    ammo_id = Column(Integer, ForeignKey("ammo.id"))
    date_shot = Column(String)
    
    # Raw data from the chronograph
    velocities = Column(String, nullable=True) # e.g., "3010,2995,3005"
    
    # --- NEW: Automated Math Columns ---
    avg_velocity = Column(Float, nullable=True)
    extreme_spread = Column(Float, nullable=True)
    standard_deviation = Column(Float, nullable=True)
    
    # Group Tracking
    target_image_path = Column(String, nullable=True)
    group_size_inches = Column(Float, nullable=True)
    group_size_moa = Column(Float, nullable=True)
    
    barrel = relationship("Barrel", back_populates="shot_strings")
    ammo = relationship("Ammo", back_populates="shot_strings")

class LookupValue(Base):
    __tablename__ = "lookup_values"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False, index=True)
    value = Column(String, nullable=False)

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")

class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(String, nullable=False)

    user = relationship("User", back_populates="sessions")

class UserPreference(Base):
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(String, nullable=False, default="true")

    user = relationship("User", back_populates="preferences")

def init_db():
    Base.metadata.create_all(bind=engine)
    from sqlalchemy import text, inspect as sa_inspect
    inspector = sa_inspect(engine)

    def _add_col(table, col, ddl):
        existing = [c['name'] for c in inspector.get_columns(table)]
        if col not in existing:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                conn.commit()

    if 'ammo' in inspector.get_table_names():
        _add_col('ammo', 'caliber', 'caliber VARCHAR')
        _add_col('ammo', 'bullet_bc', 'bullet_bc FLOAT')

    if 'barrels' in inspector.get_table_names():
        _add_col('barrels', 'tc_platform',    'tc_platform VARCHAR')
        _add_col('barrels', 'barrel_length',  'barrel_length VARCHAR')
        _add_col('barrels', 'hardware_color', 'hardware_color VARCHAR')
        _add_col('barrels', 'is_threaded',    'is_threaded BOOLEAN DEFAULT FALSE')
        _add_col('barrels', 'has_muzzle_brake', 'has_muzzle_brake BOOLEAN DEFAULT FALSE')

    # Seed default threshold settings if they don't exist
    _defaults = {
        'low_stock_powder_lbs': '0.5',
        'low_stock_primers':    '200',
        'low_stock_bullets':    '100',
        'low_stock_casings':    '50',
    }
    db = SessionLocal()
    try:
        for key, val in _defaults.items():
            if not db.query(Setting).filter(Setting.key == key).first():
                db.add(Setting(key=key, value=val))
        db.commit()
    finally:
        db.close()