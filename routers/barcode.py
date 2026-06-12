import html
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
_FLARESOLVERR_URL = os.environ.get('FLARESOLVERR_URL', 'http://192.168.125.2:8191')


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
        (r'\b6\.5\s*(?:mm\s*)?creedmoor\b', '6.5 Creedmoor'),
        (r'\b6\.5\s*creed\b',               '6.5 Creedmoor'),
        (r'\b6\.5\s*cm\b',                  '6.5 Creedmoor'),
        (r'\b6\s*(?:mm\s*)?creedmoor\b',    '6 Creedmoor'),
        (r'\b6\.5\s*(?:mm\s*)?prc\b',       '6.5 PRC'),
        (r'\b6\.5\s*(?:mm\s*)?grendel\b',   '6.5 Grendel'),
        (r'\b6\.8\s*(?:mm\s*)?western\b',   '6.8 Western'),
        (r'\b7\s*mm\s*rem(?:ington)?\s*mag\b', '7mm Rem Mag'),
        (r'\b7\s*mm\s*prc\b',               '7mm PRC'),
        (r'\b308\s*win(?:chester)?\b',      '.308 Win'),
        (r'\b30\s*-\s*06\b',               '.30-06'),
        (r'\b300\s*win(?:chester)?\s*mag\b', '.300 Win Mag'),
        (r'\b338\s*lapua\b',               '.338 Lapua'),
        (r'\b243\s*win(?:chester)?\b',      '.243 Win'),
        (r'\b223\s*rem(?:ington)?\b',       '.223 Rem'),
        (r'\b5\.56\s*(?:mm\s*)?nato\b',     '5.56 NATO'),
        (r'\b224\s*valkyrie\b',            '.224 Valkyrie'),
        (r'\b6\s*mm\s*arc\b',              '6mm ARC'),
    ]
    for abbr, name in abbrevs:
        if re.search(abbr, t, re.IGNORECASE):
            return name

    patterns = [
        r'\b6\.5-284\b',
        r'\b6\.5x55\b',
        r'\b7mm-08\b',
        r'\b\.308\s*win(?:chester)?\b',
        r'\b\.30-06\b',
        r'\b\.300\s*prc\b',
        r'\b\.300\s*wsm\b',
        r'\b\.22-250\b',
        r'(?<!\d)\.\d{2,3}(?!\d)',   # .277, .264, .308 — lookbehind/ahead avoids matching decimals
        r'\b\d+(?:\.\d+)?mm\b',      # 7mm, 6.5mm — last resort numeric fallback
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
        'PSP BT', 'PSP', 'PSPBT',
        'FMJ', 'FMJBT', 'BTHP', 'HPBT', 'HP', 'SP', 'BT',
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
    # Aliases: product names as they appear in retailer titles → canonical bc_reference.json name
    if re.search(r'\bELD\s*-?\s*X\b', text, re.IGNORECASE):          return 'ELD-X'
    if re.search(r'\bELD\s*-?\s*M(?:atch)?\b', text, re.IGNORECASE): return 'ELD-M'
    # Bare "ELD" → ELD-M (Hornady Match uses ELD-M; ELD-X is always labelled with an X)
    if re.search(r'\bELD\b', text, re.IGNORECASE):
        return 'ELD-M'
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


_JUNK_BRANDS = {'brand', 'manufacturer', 'n/a', 'na', 'unknown', 'other', 'generic', 'misc'}

def _parse_brand(raw_brand: str, title: str) -> str | None:
    raw_brand = html.unescape(raw_brand or '').strip()
    known_brands = [
        'Hornady', 'Federal', 'Winchester', 'Remington', 'Nosler',
        'Sierra', 'Berger', 'Lapua', 'Barnes', 'Speer',
        'CCI', 'Fiocchi', 'PMC', 'Sellier & Bellot', 'PPU',
        'Black Hills', 'HSM', 'Weatherby', 'Magtech', 'Wolf',
        'Norma', 'Sako', 'Vihtavuori', 'Cutting Edge', 'Hammer',
    ]
    if raw_brand and raw_brand.lower() not in _JUNK_BRANDS:
        raw_l = raw_brand.lower()
        for b in known_brands:
            b_l = b.lower()
            # Match exact, or prefix ("Barnes Bullets" → "Barnes")
            if raw_l == b_l or raw_l.startswith(b_l + ' '):
                return b
        # Unrecognized but non-junk — still check title before accepting the raw value
        for b in known_brands:
            if re.search(r'\b' + re.escape(b) + r'\b', title, re.IGNORECASE):
                return b
        return raw_brand.title()
    for b in known_brands:
        if re.search(r'\b' + re.escape(b) + r'\b', title, re.IGNORECASE):
            return b
    return None


def _caliber_matches_hint(caliber: str, hint: str) -> bool:
    """True when the leading numeric part of caliber matches the hint (e.g. '6.5 Creedmoor' ~ '6.5mm')."""
    if not caliber or not hint:
        return False
    def _lead(s: str) -> str:
        m = re.match(r'^[.]?(\d+(?:\.\d+)?)', s.strip().lstrip('.'))
        return m.group(1) if m else ''
    return bool(_lead(caliber) and _lead(caliber) == _lead(hint))


def _lookup_bc(brand: str, product_line: str | None, weight_gr: float | None,
               caliber: str | None = None) -> dict:
    if weight_gr is None:
        return {}
    ref = _load_bc_ref()
    brand_l = brand.lower() if brand else ''
    line_l = product_line.lower() if product_line else ''

    # Tier 1: brand + product_line + weight
    if line_l:
        for entry in ref:
            if (entry['brand'] == brand_l and
                    entry['product_line'] == line_l and
                    abs(entry['weight_gr'] - weight_gr) < 0.6):
                return {'bc_g1': entry.get('bc_g1'), 'bc_g7': entry.get('bc_g7')}

    # Tier 2: brand + weight only (unique match)
    candidates = [e for e in ref if e['brand'] == brand_l and abs(e['weight_gr'] - weight_gr) < 0.6]
    if len(candidates) == 1:
        return {'bc_g1': candidates[0].get('bc_g1'), 'bc_g7': candidates[0].get('bc_g7')}

    # Tier 3: brand + weight + caliber (narrows multi-weight-matches by caliber)
    if caliber and candidates:
        cal_candidates = [e for e in candidates
                          if _caliber_matches_hint(caliber, e.get('caliber_hint', ''))]
        if len(cal_candidates) == 1:
            return {'bc_g1': cal_candidates[0].get('bc_g1'), 'bc_g7': cal_candidates[0].get('bc_g7')}
        # Multiple entries with same caliber — return if they all agree on BC values
        if cal_candidates:
            bc_set = {(e.get('bc_g1'), e.get('bc_g7')) for e in cal_candidates}
            if len(bc_set) == 1:
                c = cal_candidates[0]
                return {'bc_g1': c.get('bc_g1'), 'bc_g7': c.get('bc_g7')}

    return {}


def _scrape_barcodelookup(upc: str) -> dict | None:
    """Fetch product data from barcodelookup.com via FlareSolverr. Returns a raw-data dict or None."""
    if not _FLARESOLVERR_URL:
        return None
    try:
        payload = json.dumps({
            "cmd": "request.get",
            "url": f"https://www.barcodelookup.com/{upc}",
            "maxTimeout": 45000,
        }).encode()
        req = urllib.request.Request(
            f"{_FLARESOLVERR_URL}/v1",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=55) as resp:
            d = json.loads(resp.read().decode())
        body = d.get("solution", {}).get("response", "")
        if not body or len(body) < 500:
            return None

        # Confirm the page is a product page for this UPC (not a 404 / login wall)
        if upc not in body:
            return None
        h1 = re.search(r'<h1[^>]*>\s*UPC\s+' + re.escape(upc) + r'\s*</h1>', body, re.IGNORECASE)
        if not h1:
            return None

        # Product title from <h4> (first meaningful one is the product name)
        h4 = re.search(r'<h4[^>]*>\s*(.*?)\s*</h4>', body, re.DOTALL)
        title = re.sub(r'<[^>]+>', '', h4.group(1)).strip() if h4 else ''
        _noise = {'edit the product data', 'write a product review', 'log in to your api account', ''}
        if title.lower() in _noise:
            return None

        # Manufacturer lives inside a <span> after "Manufacturer: "
        mfr = re.search(r'Manufacturer:\s*<[^>]+>\s*([^<\n]{2,60})\s*</span>', body, re.IGNORECASE)
        raw_brand = mfr.group(1).strip() if mfr else ''

        # Store affiliate links carry product slugs in a nested ?url= query parameter
        raw_hrefs = re.findall(r'href="([^"]{20,})"', body)
        slug_words: list[str] = []
        for href in raw_hrefs:
            decoded = urllib.parse.unquote(href)
            parsed = urllib.parse.urlparse(decoded)
            qs = urllib.parse.parse_qs(parsed.query)
            inner_url = qs.get('url', [None])[0]
            if inner_url:
                inner_path = urllib.parse.urlparse(inner_url).path.rstrip('/')
                slug = inner_path.split('/')[-1]
                if len(slug) > 10:
                    slug_words.append(slug.replace('-', ' '))

        combined = f"{title} {raw_brand} {' '.join(slug_words[:6])}"

        return {"title": title, "raw_brand": raw_brand, "combined": combined}
    except Exception:
        return None


@router.get("/barcode/lookup")
def barcode_lookup(upc: str, db: Session = Depends(get_db)):
    if not re.match(r'^\d{6,14}$', upc):
        raise HTTPException(400, "Invalid UPC")

    # Local cache takes priority — user-corrected data is always best
    cached = db.query(_models.UpcCache).filter(_models.UpcCache.upc == upc).first()
    if cached:
        return _cache_to_response(cached)

    # ── Primary: UPC Item DB ──────────────────────────────────────────────────
    url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={urllib.parse.quote(upc)}"
    api_data: dict = {}
    _upcdb_ok = False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "homelab-inventory/1.6"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            api_data = json.loads(resp.read().decode())
        _upcdb_ok = True
    except Exception:
        pass

    items = api_data.get("items", []) if _upcdb_ok else []

    # ── Fallback: barcodelookup.com via FlareSolverr ──────────────────────────
    _scraped: dict | None = None
    if not items:
        _scraped = _scrape_barcodelookup(upc)
        if not _scraped and not _upcdb_ok:
            raise HTTPException(502, "UPC lookup failed: UPC Item DB unreachable and FlareSolverr unavailable")
        if not _scraped:
            raise HTTPException(404, "Barcode not found in UPC database")

    if _scraped:
        title = _scraped["title"]
        raw_brand = _scraped["raw_brand"]
        combined = _scraped["combined"]
        lowest_price = None
        api_images: list = []
    else:
        item = items[0]
        title = item.get("title") or item.get("description") or ""
        raw_brand = item.get("brand") or ""
        lowest_price = item.get("lowest_recorded_price")
        api_images = item.get("images") or []
        combined = title

    # Download product image once if available (UPC Item DB path only)
    image_path = None
    for img_url in api_images:
        if img_url:
            image_path = _download_upc_image(upc, img_url)
            if image_path:
                break

    brand = _parse_brand(raw_brand, combined)
    weight_gr = _parse_weight(combined)
    caliber = _parse_caliber(combined)
    bullet_type = _parse_bullet_type(combined)
    product_line = _parse_product_line(combined)
    rounds_per_box = _parse_rounds(combined)
    primer_type = _parse_primer_type(combined)
    powder_brand, powder_name = _parse_powder_name(combined)

    bc_data = _lookup_bc(brand or '', product_line, weight_gr, caliber)

    # Infer product type so the frontend can auto-navigate to the right form
    _is_ammo_title  = bool(re.search(r'\b(?:ammo|ammunition|centerfire|rimfire|shotshell|slug|buckshot)\b', combined, re.IGNORECASE))
    _is_bullet_title = bool(re.search(r'\bbullets?\b', combined, re.IGNORECASE))
    # Product lines that only appear on component bullets, never on factory-ammo boxes
    _component_only = {'eld-x','eld-m','a-tip','matchking','tipped matchking','vld','hybrid',
                       'accubond','partition','lrx','ttsx','tsx','tac-tx','rdf','juggernaut','e-tip'}
    _is_component_line = bool(product_line and product_line.lower() in _component_only)

    if powder_name:
        product_type = "powder"
    elif primer_type or re.search(r'\bprimer\b', combined, re.IGNORECASE):
        product_type = "primer"
    elif _is_ammo_title:
        product_type = "ammo"
    elif rounds_per_box and caliber and not _is_bullet_title and not _is_component_line:
        product_type = "ammo"
    elif weight_gr and (bullet_type or bc_data or product_line):
        product_type = "bullet"
    elif caliber and not weight_gr and not rounds_per_box:
        product_type = "casing"
    else:
        product_type = None

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
        "primer_model": _parse_primer_model(combined),
        "image_path": image_path,
        "source": "scrape" if _scraped else "api",
    }
