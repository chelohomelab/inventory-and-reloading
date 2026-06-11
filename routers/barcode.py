import json
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import database as _models
from dependencies import get_db

router = APIRouter()

_UPC_CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'upc_cache')


def _download_upc_image(upc: str, url: str) -> str | None:
    """Download a product image and save locally. Returns the /static/… path or None."""
    os.makedirs(_UPC_CACHE_DIR, exist_ok=True)
    ext = '.jpg'
    for suffix in ('.png', '.webp', '.gif'):
        if url.lower().split('?')[0].endswith(suffix):
            ext = suffix
            break
    dest = os.path.join(_UPC_CACHE_DIR, f"{upc}{ext}")
    if os.path.exists(dest):
        return f"/static/uploads/upc_cache/{upc}{ext}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "homelab-inventory/1.6"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = resp.read()
        with open(dest, 'wb') as f:
            f.write(data)
        return f"/static/uploads/upc_cache/{upc}{ext}"
    except Exception:
        return None


def upsert_upc_cache(db: Session, upc: str, **kwargs) -> None:
    """Create or update a UPC cache entry with the supplied keyword fields."""
    if not upc:
        return
    entry = db.query(_models.UpcCache).filter(_models.UpcCache.upc == upc).first()
    if entry is None:
        entry = _models.UpcCache(upc=upc)
        db.add(entry)
    for k, v in kwargs.items():
        if v is not None and hasattr(entry, k):
            setattr(entry, k, v)
    entry.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()


def _cache_to_response(entry: "_models.UpcCache") -> dict:
    return {
        "upc": entry.upc,
        "title": entry.title,
        "product_type": entry.product_type,
        "brand": entry.brand,
        "product_line": entry.product_line,
        "powder_name": entry.powder_name,
        "caliber": entry.caliber,
        "weight_gr": entry.weight_gr,
        "bullet_type": entry.bullet_type,
        "rounds_per_box": entry.rounds_per_box,
        "price": None,
        "bc_g1": entry.bc_g1,
        "bc_g7": entry.bc_g7,
        "primer_type": entry.primer_type,
        "primer_model": entry.primer_model,
        "image_path": entry.image_path,
        "source": "cache",
    }

_BC_REF: list[dict] | None = None

def _load_bc_ref() -> list[dict]:
    global _BC_REF
    if _BC_REF is None:
        path = os.path.join(os.path.dirname(__file__), '..', 'static', 'bc_reference.json')
        with open(os.path.abspath(path)) as f:
            _BC_REF = json.load(f)
    return _BC_REF


def _parse_weight(text: str) -> float | None:
    # Match "140gr", "140 gr", "140grains", "129g" (Barnes-style bare "g")
    m = re.search(r'(\d+(?:\.\d+)?)\s*g(?:r(?:ain)?s?)?\b', text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    # Speer/Sierra "caliber-weight-style" format: e.g. "277-130-BT" → weight=130
    m2 = re.search(r'(?<!\d)(?:2[2-9]\d|3[0-9]\d|4[0-5]\d)-(\d{2,3})-[A-Za-z]', text)
    if m2:
        return float(m2.group(1))
    return None


def _parse_rounds(text: str) -> int | None:
    m = re.search(r'(\d+)\s*(?:count|ct\.?|rounds?|rds?\.?|pack|pk|box)\b', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m2 = re.search(r'\b(\d+)\s*-?\s*(?:count|pack|pk|rd)\b', text, re.IGNORECASE)
    if m2:
        return int(m2.group(1))
    # Shotgun pack: "5 100" at end = 5-round box, 100 per case
    m3 = re.search(r'\b(\d{1,2})\s+\d{2,4}\s*$', text.strip())
    if m3 and int(m3.group(1)) <= 25:
        return int(m3.group(1))
    # "20/200" box/case format — take the box count
    m4 = re.search(r'\b(\d{1,3})/(\d{2,4})\b', text)
    if m4:
        box, case = int(m4.group(1)), int(m4.group(2))
        if box <= 100 and case > box:
            return box
    return None


def _parse_caliber(text: str) -> str | None:
    t = text.lower()

    # Shotgun gauges — check before generic patterns
    gauge_map = [
        (r'\b12\s*ga(?:uge)?\b', '12 Gauge'),
        (r'\b20\s*ga(?:uge)?\b', '20 Gauge'),
        (r'\b28\s*ga(?:uge)?\b', '28 Gauge'),
        (r'\.410\b|410\s*(?:bore|ga(?:uge)?)', '.410 Bore'),
    ]
    for gp, label in gauge_map:
        if re.search(gp, t, re.IGNORECASE):
            return label

    # Speer/Sierra "caliber-weight-style" format: e.g. "277-130-BT" → caliber=.277
    m = re.search(r'(?<!\d)(2[2-9]\d|3[0-9]\d|4[0-5]\d)-\d{2,3}-[A-Za-z]', text)
    if m:
        return f'.{m.group(1)}'

    # Named abbreviations that need explicit return values
    abbrevs = [
        (r'\b6\.5\s*creed\b', '6.5 Creedmoor'),
        (r'\b6\.5\s*cm\b', '6.5 Creedmoor'),
    ]
    for abbr, name in abbrevs:
        if re.search(abbr, t, re.IGNORECASE):
            return name

    patterns = [
        r'\b6\.5\s*creedmoor\b',
        r'\b6\.5\s*prc\b',
        r'\b6\.5\s*grendel\b',
        r'\b6\s*creedmoor\b',
        r'\b6\s*mm\s*creedmoor\b',
        r'\b6\.8\s*western\b',
        r'\b6\.5-284\b',
        r'\b6\.5x55\b',
        r'\b7mm\s*rem(?:ington)?\s*mag\b',
        r'\b7mm-08\b',
        r'\b7mm\s*prc\b',
        r'\b\.308\s*win(?:chester)?\b',
        r'\b308\s*win(?:chester)?\b',
        r'\b\.30-06\b',
        r'\b30-06\b',
        r'\b\.300\s*win(?:chester)?\s*mag\b',
        r'\b\.300\s*prc\b',
        r'\b\.300\s*wsm\b',
        r'\b\.338\s*lapua\b',
        r'\b\.243\s*win(?:chester)?\b',
        r'\b243\s*win(?:chester)?\b',
        r'\b\.22-250\b',
        r'\b\.223\s*rem(?:ington)?\b',
        r'\b5\.56\s*nato\b',
        r'\b\.224\s*valkyrie\b',
        r'\b6mm\s*arc\b',
        r'\b6\.5\b.*?\b(?:creedmoor|prc|grendel)\b',
        r'(?<!\d)\.\d{2,3}(?!\d)',   # .277, .264, .308 — lookbehind/ahead avoids matching decimals
        r'\b\d+(?:\.\d+)?mm\b',      # 7mm, 6.5mm — fractional form prevents "5mm" from "6.5mm"
    ]
    for p in patterns:
        m = re.search(p, t, re.IGNORECASE)
        if m:
            raw = m.group(0).strip()
            if raw.endswith('mm'):
                return raw.lower()  # 6.5mm, 7mm — keep lowercase
            return raw.upper() if raw.startswith('.') or raw[0].isdigit() else raw.title()
    return None


def _parse_bullet_type(text: str) -> str | None:
    # Barnes abbreviated product names used in UPC databases
    if re.search(r'\bLr\s*Xbt\b', text, re.IGNORECASE): return 'LRX'
    if re.search(r'\bTt\s*Sx\b', text, re.IGNORECASE):  return 'TTSX'
    if re.search(r'\bTac\s*Tx\b', text, re.IGNORECASE): return 'TAC-TX'
    keywords = [
        'ELD-X', 'ELD-M', 'ELD Match', 'A-TIP', 'SST', 'GMX', 'FTX', 'InterBond',
        'InterLock', 'XTP', 'V-Max',
        'MatchKing', 'Tipped MatchKing', 'TMK', 'GameKing', 'ProHunter',
        'Hybrid', 'OTM', 'VLD', 'Juggernaut',
        'AccuBond', 'Ballistic Tip', 'Partition', 'E-Tip', 'RDF',
        'TTSX', 'TSX', 'LRX', 'TAC-TX',
        'Scenar', 'Mega', 'FMJ', 'FMJBT', 'Lock Base',
        'Trophy Bonded', 'Fusion', 'Power-Shok',
        'Gold Dot', 'Hot-Cor', 'DeepCurl',
        'FMJ', 'BTHP', 'HPBT', 'HP', 'SP', 'BT',
        'Soft Point', 'Hollow Point', 'Boat Tail',
        'Power-Point', 'Silvertip',
        'Core-Lokt', 'CoreLokt',
        'Slug', 'Sabot Slug', 'Buckshot', 'Birdshot',
    ]
    t = text
    for kw in keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', t, re.IGNORECASE):
            return kw
    return None


def _parse_product_line(text: str) -> str | None:
    # Barnes abbreviated product names used in UPC databases
    if re.search(r'\bLr\s*Xbt\b', text, re.IGNORECASE): return 'LRX'
    if re.search(r'\bTt\s*Sx\b', text, re.IGNORECASE):  return 'TTSX'
    if re.search(r'\bTac\s*Tx\b', text, re.IGNORECASE): return 'TAC-TX'
    known_lines = [
        'ELD-X', 'ELD-M', 'A-TIP', 'SST', 'GMX', 'FTX', 'V-Max', 'XTP',
        'MatchKing', 'Tipped MatchKing', 'GameKing',
        'Hybrid', 'OTM', 'VLD', 'Juggernaut',
        'AccuBond Long Range', 'AccuBond', 'Ballistic Tip', 'Partition', 'RDF',
        'TTSX', 'TSX', 'LRX',
        'Scenar-L', 'Scenar', 'Mega', 'Lock Base',
        'Gold Medal Match', 'Gold Medal Berger', 'Trophy Bonded Tip',
        'Fusion', 'Power-Shok', 'American Eagle',
        'Precision Hunter', 'Match', 'Black Hills',
        'Expedition Big Game Long Range', 'Expedition Big Game',
        'Power-Point', 'Silvertip', 'Super-X',
        'Core-Lokt', 'Premier Match',
        'Gold Dot', 'Hot-Cor',
        'AccuTip', 'Slugger', 'Express', 'Managed-Recoil',
    ]
    t = text
    for line in sorted(known_lines, key=len, reverse=True):
        if re.search(r'\b' + re.escape(line) + r'\b', t, re.IGNORECASE):
            return line
    return None


def _parse_primer_model(text: str) -> str | None:
    # Must have a letter suffix (e.g. 41A, 209A) OR be a known primer model number
    # Avoid matching generic counts like "97 Count", "20 Rounds"
    _KNOWN_MODELS = {'41', '34', '200', '205', '209', '210', '215', '250', '400', '450', '500'}
    m = re.search(r'\b(\d{2,3}[A-Za-z]{1,3}(?:SC)?)\b', text)
    if m:
        suffix = re.sub(r'^\d+', '', m.group(1)).upper()
        if suffix not in ('G', 'GR', 'GRS'):
            return m.group(1)
    m2 = re.search(r'\b(\d{2,3})\b', text)
    if m2 and m2.group(1) in _KNOWN_MODELS:
        return m2.group(1)
    return None


def _parse_primer_type(text: str) -> str | None:
    t = text.lower()
    if re.search(r'small\s*rifle\s*magnum', t): return 'Small Rifle Magnum'
    if re.search(r'large\s*rifle\s*magnum', t): return 'Large Rifle Magnum'
    if re.search(r'small\s*rifle', t):          return 'Small Rifle'
    if re.search(r'large\s*rifle', t):          return 'Large Rifle'
    if re.search(r'small\s*pistol\s*magnum', t): return 'Small Pistol Magnum'
    if re.search(r'large\s*pistol\s*magnum', t): return 'Large Pistol Magnum'
    if re.search(r'small\s*pistol', t):          return 'Small Pistol'
    if re.search(r'large\s*pistol', t):          return 'Large Pistol'
    return None


def _parse_powder_name(title: str) -> tuple[str | None, str | None]:
    """Returns (brand, name) for powder products."""
    known = {
        'hodgdon': ['H4350', 'H4831', 'H4831SC', 'H1000', 'H4895', 'Varget', 'Benchmark',
                    'CFE 223', 'CFE BLK', 'H322', 'H335', 'H380', 'Lil\'Gun', 'Retumbo',
                    'IMR 4350', 'IMR 4831', 'IMR 4064', 'IMR 4166', 'IMR 4451',
                    'IMR 8208 XBR', 'Trail Boss'],
        'alliant':  ['Reloder 16', 'Reloder 17', 'Reloder 19', 'Reloder 23', 'Reloder 26',
                     'Power Pro 2000-MR', 'Power Pro 300-MP', 'AR-Comp', 'Power Pro 4000-MR'],
        'vihtavuori': ['N140', 'N150', 'N160', 'N165', 'N170', 'N555', 'N560', 'N565',
                       '20N29', '24N41', 'N133', 'N135'],
        'accurate': ['2230', '2460', '2495', '4064', '4350', 'LT-30', 'LT-32', 'No. 5',
                     'No. 7', 'No. 9'],
        'ramshot': ['Hunter', 'Big Game', 'Magnum', 'LRT', 'TAC', 'X-Terminator'],
        'shooters world': ['Precision', 'Long Rifle', 'Match Rifle', 'Duty Pistol'],
    }
    t = title
    for brand, names in known.items():
        for name in sorted(names, key=len, reverse=True):
            if re.search(r'\b' + re.escape(name) + r'\b', t, re.IGNORECASE):
                return brand.title(), name
    return None, None


def _parse_brand(raw_brand: str, title: str) -> str | None:
    known_brands = [
        'Hornady', 'Federal', 'Winchester', 'Remington', 'Nosler',
        'Sierra', 'Berger', 'Lapua', 'Barnes', 'Speer',
        'CCI', 'Fiocchi', 'PMC', 'Sellier & Bellot', 'PPU',
        'Black Hills', 'HSM', 'Weatherby', 'Magtech', 'Wolf',
        'Norma', 'Sako', 'Vihtavuori', 'Cutting Edge', 'Hammer',
    ]
    if raw_brand:
        raw_l = raw_brand.lower()
        for b in known_brands:
            b_l = b.lower()
            # Match exact, or prefix ("Barnes Bullets" → "Barnes")
            if raw_l == b_l or raw_l.startswith(b_l + ' '):
                return b
        return raw_brand.title()
    for b in known_brands:
        if re.search(r'\b' + re.escape(b) + r'\b', title, re.IGNORECASE):
            return b
    return None


def _lookup_bc(brand: str, product_line: str | None, weight_gr: float | None) -> dict:
    if weight_gr is None:
        return {}
    ref = _load_bc_ref()
    brand_l = brand.lower() if brand else ''
    line_l = product_line.lower() if product_line else ''

    # Try brand + product_line + weight (exact)
    if line_l:
        for entry in ref:
            if (entry['brand'] == brand_l and
                    entry['product_line'] == line_l and
                    abs(entry['weight_gr'] - weight_gr) < 0.6):
                return {'bc_g1': entry.get('bc_g1'), 'bc_g7': entry.get('bc_g7')}

    # Try brand + weight only
    candidates = [e for e in ref if e['brand'] == brand_l and abs(e['weight_gr'] - weight_gr) < 0.6]
    if len(candidates) == 1:
        return {'bc_g1': candidates[0].get('bc_g1'), 'bc_g7': candidates[0].get('bc_g7')}

    return {}


@router.get("/barcode/lookup")
def barcode_lookup(upc: str, db: Session = Depends(get_db)):
    if not re.match(r'^\d{6,14}$', upc):
        raise HTTPException(400, "Invalid UPC")

    # Local cache takes priority — user-corrected data is always best
    cached = db.query(_models.UpcCache).filter(_models.UpcCache.upc == upc).first()
    if cached:
        return _cache_to_response(cached)

    url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={urllib.parse.quote(upc)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "homelab-inventory/1.6"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            api_data = json.loads(resp.read().decode())
    except Exception as e:
        raise HTTPException(502, f"UPC lookup failed: {e}")

    items = api_data.get("items", [])
    if not items:
        raise HTTPException(404, "Barcode not found in UPC database")

    item = items[0]
    title = item.get("title") or item.get("description") or ""
    raw_brand = item.get("brand") or ""
    lowest_price = item.get("lowest_recorded_price")

    # Download product image once if available
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

    bc_data = _lookup_bc(brand or '', product_line, weight_gr)

    # Infer product type so the frontend can auto-navigate to the right form
    _is_ammo_title  = bool(re.search(r'\b(?:ammo|ammunition|centerfire|rimfire|shotshell|slug|buckshot)\b', title, re.IGNORECASE))
    _is_bullet_title = bool(re.search(r'\bbullets?\b', title, re.IGNORECASE))
    # Product lines that only appear on component bullets, never on factory-ammo boxes
    _component_only = {'eld-x','eld-m','a-tip','matchking','tipped matchking','vld','hybrid',
                       'accubond','partition','lrx','ttsx','tsx','tac-tx','rdf','juggernaut','e-tip'}
    _is_component_line = bool(product_line and product_line.lower() in _component_only)

    if powder_name:
        product_type = "powder"
    elif primer_type or re.search(r'\bprimer\b', title, re.IGNORECASE):
        product_type = "primer"
    elif _is_ammo_title:
        product_type = "ammo"          # explicit ammo keyword in title
    elif rounds_per_box and caliber and not _is_bullet_title and not _is_component_line:
        product_type = "ammo"          # rounds+caliber → factory ammo, unless clearly a component bullet
    elif weight_gr and (bullet_type or bc_data or product_line):
        product_type = "bullet"        # component bullet
    elif caliber and not weight_gr and not rounds_per_box:
        product_type = "casing"
    else:
        product_type = None            # unknown, keep current form

    return {
        "upc": upc,
        "title": title,
        "product_type": product_type,
        "brand": powder_brand or brand,
        "product_line": product_line,
        "powder_name": powder_name,
        "caliber": caliber,
        "weight_gr": weight_gr,
        "bullet_type": bullet_type,
        "rounds_per_box": rounds_per_box,
        "price": lowest_price,
        "bc_g1": bc_data.get("bc_g1"),
        "bc_g7": bc_data.get("bc_g7"),
        "primer_type": primer_type,
        "primer_model": _parse_primer_model(title),
        "image_path": image_path,
        "source": "api",
    }
