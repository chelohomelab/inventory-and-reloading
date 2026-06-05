from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

DATABASE_URL = "sqlite:///./reloading.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- NEW: FURNITURE MODEL (Stocks, Grips, Forearms) ---
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

# --- REFACTORED COMPONENTS & ACCESSORIES ---
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

# --- REFACTORED FIREARMS & BARRELS ---
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
    firearm_id = Column(Integer, ForeignKey("firearms.id")) 
    name = Column(String, nullable=True)                    
    caliber = Column(String)                                
    twist_rate = Column(String, nullable=True)
    price_paid = Column(Float, default=0.0)                 
    scope_id = Column(Integer, ForeignKey("scopes.id"), nullable=True) 
    image_path = Column(String, nullable=True)
    
    firearm = relationship("Firearm", back_populates="barrels")
    scope = relationship("Scope", back_populates="barrels")
    accessories = relationship("Accessory", foreign_keys=[Accessory.barrel_id])
    shot_strings = relationship("ShotString", back_populates="barrel")

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

def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe migration: add caliber column to ammo table if not present
    from sqlalchemy import text, inspect as sa_inspect
    inspector = sa_inspect(engine)
    if 'ammo' in inspector.get_table_names():
        existing = [col['name'] for col in inspector.get_columns('ammo')]
        if 'caliber' not in existing:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE ammo ADD COLUMN caliber VARCHAR"))
                conn.commit()
        if 'bullet_bc' not in existing:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE ammo ADD COLUMN bullet_bc FLOAT"))
                conn.commit()