from pydantic import BaseModel
from typing import Optional


class SoldPayload(BaseModel):
    is_sold: bool
    price_sold: float = 0.0


class FirearmPatchPayload(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    caliber: Optional[str] = None
    scope_optic: Optional[str] = None
    price_paid: Optional[float] = None


class ScopeMountPayload(BaseModel):
    mount_type: Optional[str] = None  # "firearm", "barrel", or null to unmount
    mount_id: Optional[int] = None


class AmmoPatchPayload(BaseModel):
    brand: Optional[str] = None
    caliber: Optional[str] = None
    bullet_type: Optional[str] = None
    bullet_weight: Optional[float] = None
    bullet_bc: Optional[float] = None
    line_or_powder: Optional[str] = None
    charge_weight: Optional[float] = None
    coal: Optional[float] = None


class PowderPatch(BaseModel):
    brand: Optional[str] = None
    name: Optional[str] = None
    weight_lbs: Optional[float] = None
    price_paid: Optional[float] = None
    notes: Optional[str] = None


class PrimerPatch(BaseModel):
    brand: Optional[str] = None
    primer_type: Optional[str] = None
    quantity: Optional[int] = None
    price_paid: Optional[float] = None
    notes: Optional[str] = None


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


class CasingPatch(BaseModel):
    brand: Optional[str] = None
    caliber: Optional[str] = None
    quantity: Optional[int] = None
    times_fired: Optional[int] = None
    price_paid: Optional[float] = None
    notes: Optional[str] = None


class DeductPayload(BaseModel):
    powder_inv_id: Optional[int] = None
    primer_inv_id: Optional[int] = None
    bullet_inv_id: Optional[int] = None
    casing_inv_id: Optional[int] = None
    rounds_loaded: int = 0
    powder_charge_gr: Optional[float] = None


class SettingsPatch(BaseModel):
    low_stock_powder_lbs: Optional[str] = None
    low_stock_primers: Optional[str] = None
    low_stock_bullets: Optional[str] = None
    low_stock_casings: Optional[str] = None


class AdminUserPatch(BaseModel):
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
