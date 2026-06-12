import html
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

import database as _models
from dependencies import get_db, save_uploaded_file

router = APIRouter(prefix="/scanner", tags=["scanner"])


def _require_admin(request: Request):
    if not getattr(request.state, "user", None) or not request.state.user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")


def _entry_dict(e: "_models.ScannerEntry") -> dict:
    data = {}
    if e.data_json:
        try:
            data = json.loads(e.data_json)
        except Exception:
            pass
    return {
        "id": e.id,
        "category": e.category,
        "upc": e.upc,
        "title": e.title,
        "brand": e.brand,
        "caliber": e.caliber,
        "notes": e.notes,
        "image_path_1": e.image_path_1,
        "image_path_2": e.image_path_2,
        "image_path_3": e.image_path_3,
        "data": data,
        "created_at": e.created_at,
        "is_reviewed": e.is_reviewed,
    }


def _is_complete(entry: "_models.ScannerEntry") -> bool:
    """Return False if any required field for the category is missing."""
    if not entry.brand:
        return False
    cat = entry.category
    if cat == "ammo":
        return bool(entry.caliber)
    if cat in ("firearm", "optic"):
        data = {}
        if entry.data_json:
            try:
                data = json.loads(entry.data_json)
            except Exception:
                pass
        return bool(data.get("model"))
    if cat == "tc_barrel":
        data = {}
        if entry.data_json:
            try:
                data = json.loads(entry.data_json)
            except Exception:
                pass
        return bool(entry.caliber and data.get("platform"))
    if cat == "component":
        return True  # brand alone is enough for components
    return True


@router.get("/entries")
def list_entries(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    entries = db.query(_models.ScannerEntry).order_by(_models.ScannerEntry.id.desc()).all()
    result = []
    for e in entries:
        d = _entry_dict(e)
        d["is_complete"] = _is_complete(e)
        result.append(d)
    return result


@router.post("/entries")
async def create_entry(
    request: Request,
    category: str = Form(default=""),
    upc: Optional[str] = Form(default=None),
    title: Optional[str] = Form(default=None),
    brand: Optional[str] = Form(default=None),
    caliber: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
    data_json: Optional[str] = Form(default=None),
    photo: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(request)
    image_path = await save_uploaded_file(photo, "scan") if photo else None
    entry = _models.ScannerEntry(
        category=category or "ammo",
        upc=upc or None,
        title=title or None,
        brand=brand or None,
        caliber=caliber or None,
        notes=notes or None,
        data_json=data_json or None,
        image_path_1=image_path,
        created_at=datetime.now(timezone.utc).date().isoformat(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    d = _entry_dict(entry)
    d["is_complete"] = _is_complete(entry)
    return d


@router.patch("/entries/{entry_id}")
async def update_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request)
    entry = db.query(_models.ScannerEntry).filter(_models.ScannerEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(404, "Not found")
    body = await request.json()
    for field in ("category", "upc", "title", "brand", "caliber", "notes", "data_json", "is_reviewed"):
        if field in body:
            setattr(entry, field, body[field])
    db.commit()
    d = _entry_dict(entry)
    d["is_complete"] = _is_complete(entry)
    return d


@router.post("/entries/{entry_id}/add-photo")
async def add_photo(
    entry_id: int,
    request: Request,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _require_admin(request)
    entry = db.query(_models.ScannerEntry).filter(_models.ScannerEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(404, "Not found")
    path = await save_uploaded_file(photo, "scan")
    if not path:
        raise HTTPException(400, "Upload failed")
    if not entry.image_path_1:
        entry.image_path_1 = path
    elif not entry.image_path_2:
        entry.image_path_2 = path
    elif not entry.image_path_3:
        entry.image_path_3 = path
    else:
        raise HTTPException(400, "Max 3 photos per entry")
    db.commit()
    return {"image_path_1": entry.image_path_1, "image_path_2": entry.image_path_2, "image_path_3": entry.image_path_3}


@router.delete("/entries/{entry_id}/photos/{slot}")
def delete_photo(
    entry_id: int,
    slot: int,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request)
    entry = db.query(_models.ScannerEntry).filter(_models.ScannerEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(404, "Not found")
    if slot == 1:
        entry.image_path_1 = None
    elif slot == 2:
        entry.image_path_2 = None
    elif slot == 3:
        entry.image_path_3 = None
    db.commit()
    return {"ok": True}


@router.delete("/entries/reviewed")
def delete_reviewed_entries(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    count = db.query(_models.ScannerEntry).filter(_models.ScannerEntry.is_reviewed == True).delete()
    db.commit()
    return {"deleted": count}


@router.delete("/entries/{entry_id}")
def delete_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_admin(request)
    entry = db.query(_models.ScannerEntry).filter(_models.ScannerEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(404, "Not found")
    db.delete(entry)
    db.commit()
    return {"deleted": entry_id}


@router.post("/entries/{entry_id}/autofill")
def autofill_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Look up the entry's UPC and return proposed field changes without applying them."""
    _require_admin(request)
    entry = db.query(_models.ScannerEntry).filter(_models.ScannerEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(404, "Not found")
    if not entry.upc:
        raise HTTPException(400, "No UPC on this entry")

    # Reuse the cache-first lookup from barcode.py
    import re, urllib.request, urllib.parse, json as _json
    from routers.barcode import (
        _parse_brand, _parse_caliber, _parse_weight, _parse_bullet_type,
        _parse_product_line, _parse_rounds, _parse_primer_type, _parse_primer_model,
        _parse_powder_name, _lookup_bc, _cache_to_response, _download_upc_image,
        upsert_upc_cache,
    )

    upc = entry.upc
    cached = db.query(_models.UpcCache).filter(_models.UpcCache.upc == upc).first()
    if cached:
        info = _cache_to_response(cached)
    else:
        url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={urllib.parse.quote(upc)}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "homelab-inventory/1.7"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                api_data = _json.loads(resp.read().decode())
        except Exception as e:
            raise HTTPException(502, f"UPC lookup failed: {e}")
        items = api_data.get("items", [])
        if not items:
            raise HTTPException(404, "UPC not found in external database")
        item = items[0]
        title = item.get("title") or item.get("description") or ""
        raw_brand = html.unescape(item.get("brand") or "")
        api_images = item.get("images") or []
        image_path = None
        for img_url in api_images:
            if img_url:
                image_path = _download_upc_image(upc, img_url)
                if image_path:
                    break
        brand = _parse_brand(raw_brand, title)
        weight_gr = _parse_weight(title)
        caliber = _parse_caliber(title)
        bullet_type = _parse_bullet_type(title)
        product_line = _parse_product_line(title)
        rounds_per_box = _parse_rounds(title)
        primer_type = _parse_primer_type(title)
        powder_brand, powder_name = _parse_powder_name(title)
        bc_data = _lookup_bc(brand or '', product_line, weight_gr, caliber)
        info = {
            "upc": upc, "title": title, "brand": powder_brand or brand,
            "product_line": product_line, "powder_name": powder_name,
            "caliber": caliber, "weight_gr": weight_gr, "bullet_type": bullet_type,
            "rounds_per_box": rounds_per_box, "bc_g1": bc_data.get("bc_g1"),
            "bc_g7": bc_data.get("bc_g7"), "primer_type": primer_type,
            "primer_model": _parse_primer_model(title), "image_path": image_path,
        }
        # Persist to cache so future lookups (and the main barcode endpoint) are instant
        upsert_upc_cache(db, upc,
                         title=title, product_type=None,
                         brand=powder_brand or brand, product_line=product_line,
                         powder_name=powder_name, caliber=caliber,
                         weight_gr=weight_gr, bullet_type=bullet_type,
                         rounds_per_box=rounds_per_box,
                         bc_g1=bc_data.get("bc_g1"), bc_g7=bc_data.get("bc_g7"),
                         primer_type=primer_type,
                         primer_model=_parse_primer_model(title),
                         image_path=image_path)

    # Map to proposed entry fields
    proposed_base = {}
    proposed_data = {}

    if info.get("title") and not entry.title:
        proposed_base["title"] = info["title"]
    if info.get("brand") and not entry.brand:
        proposed_base["brand"] = info["brand"]
    if info.get("caliber") and not entry.caliber:
        proposed_base["caliber"] = info["caliber"]

    existing_data = {}
    if entry.data_json:
        try:
            existing_data = _json.loads(entry.data_json)
        except Exception:
            pass

    for key in ("product_line", "weight_gr", "bullet_type", "rounds_per_box",
                "bc_g1", "bc_g7", "primer_type", "primer_model", "powder_name"):
        val = info.get(key)
        if val is not None and not existing_data.get(key):
            proposed_data[key] = val

    if info.get("image_path") and not entry.image_path_1:
        proposed_base["image_path_1"] = info["image_path"]

    return {
        "proposed_base": proposed_base,
        "proposed_data": proposed_data,
        "source": info.get("source", "api"),
    }
