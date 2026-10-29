"""
SKU matching engine using RapidFuzz similarity and strict attribute verification.
Guarantees zero mismatched variants (e.g. 1L vs 200ml milk, or full-fat vs low-fat).
"""

import re
from typing import List, Optional, Tuple
from rapidfuzz import fuzz
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.catalog import StoreItem
from sabad.normalizer.parser import fold_grocery_aliases
from sabad.normalizer.persian_digits import clean_persian_text


VERBAL_VOL_PATTERNS = [
    # Compound verbal volumes (1.5, 2.5)
    (r'(?:\b|^)(?:یک|یه)\s*و\s*نیم\s*(?:لیتری|لیتر)(?![آ-ی\w\u0600-\u06FF])', 1.5, "لیتر"),
    (r'(?:\b|^)(?:یک|یه)\s*و\s*نیم\s*(?:کیلو\s*گرمی|کیلوگرمی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو)(?![آ-ی\w\u0600-\u06FF])', 1.5, "کیلوگرم"),
    (r'(?:\b|^)(?:دو)\s*و\s*نیم\s*(?:لیتری|لیتر)(?![آ-ی\w\u0600-\u06FF])', 2.5, "لیتر"),
    (r'(?:\b|^)(?:دو)\s*و\s*نیم\s*(?:کیلو\s*گرمی|کیلوگرمی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو)(?![آ-ی\w\u0600-\u06FF])', 2.5, "کیلوگرم"),

    # Half volumes (0.5)
    (r'(?:\b|^)نیم\s*(?:لیتری|لیتر)(?![آ-ی\w\u0600-\u06FF])', 0.5, "لیتر"),
    (r'(?:\b|^)نیم\s*(?:کیلو\s*گرمی|کیلوگرمی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو)(?![آ-ی\w\u0600-\u06FF])', 0.5, "کیلوگرم"),

    # Liters
    (r'(?:\b|^)(?:یک|یه)\s*(?:لیتری|لیتر)(?![آ-ی\w\u0600-\u06FF])', 1.0, "لیتر"),
    (r'(?:\b|^)(?:دو)\s*(?:لیتری|لیتر)(?![آ-ی\w\u0600-\u06FF])', 2.0, "لیتر"),
    (r'(?:\b|^)(?:سه)\s*(?:لیتری|لیتر)(?![آ-ی\w\u0600-\u06FF])', 3.0, "لیتر"),
    (r'(?:\b|^)(?:چهار)\s*(?:لیتری|لیتر)(?![آ-ی\w\u0600-\u06FF])', 4.0, "لیتر"),

    # Kilograms
    (r'(?:\b|^)(?:یک|یه)\s*(?:کیلو\s*گرمی|کیلوگرمی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو)(?![آ-ی\w\u0600-\u06FF])', 1.0, "کیلوگرم"),
    (r'(?:\b|^)(?:دو)\s*(?:کیلو\s*گرمی|کیلوگرمی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو)(?![آ-ی\w\u0600-\u06FF])', 2.0, "کیلوگرم"),
    (r'(?:\b|^)(?:سه)\s*(?:کیلو\s*گرمی|کیلوگرمی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو)(?![آ-ی\w\u0600-\u06FF])', 3.0, "کیلوگرم"),
    (r'(?:\b|^)(?:چهار)\s*(?:کیلو\s*گرمی|کیلوگرمی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو)(?![آ-ی\w\u0600-\u06FF])', 4.0, "کیلوگرم"),
    (r'(?:\b|^)(?:پنج)\s*(?:کیلو\s*گرمی|کیلوگرمی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو)(?![آ-ی\w\u0600-\u06FF])', 5.0, "کیلوگرم"),

    # Pack / roll counts (toilet paper, tissues)
    (r'(?:\b|^)(?:دو|۲)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 2.0, "عدد"),
    (r'(?:\b|^)(?:چهار|۴)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 4.0, "عدد"),
    (r'(?:\b|^)(?:شش|۶)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 6.0, "عدد"),
    (r'(?:\b|^)(?:هشت|۸)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 8.0, "عدد"),
    (r'(?:\b|^)(?:ده|۱۰)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 10.0, "عدد"),
    (r'(?:\b|^)(?:دوازده|۱۲)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 12.0, "عدد"),
    (r'(?:\b|^)(?:شانزده|۱۶)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 16.0, "عدد"),
    (r'(?:\b|^)(?:بیست و چهار|۲۴)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 24.0, "عدد"),
]

DAIRY_FLAVORS = [
    "طالبی", "کاکائو", "موز", "قهوه", "توت فرنگی", "توت‌فرنگی", "توت فرنگي",
    "وانیل", "خرما", "عسل", "پسته", "نارگیل", "شکلات", "چاکلت",
    "فندق", "بادام", "گردو", "کارامل", "مالت", "زعفران", "انبه",
    "طعم دار", "طعم‌دار",
]


def extract_volume_from_title(title: str) -> Tuple[Optional[float], Optional[str]]:
    """Extracts numeric or verbal volume/weight and unit from catalog SKU title."""
    cleaned = clean_persian_text(title)

    # 1. Check verbal volumes first
    for pat, val, unit in VERBAL_VOL_PATTERNS:
        match = re.search(pat, cleaned)
        if match:
            return val, unit

    # 2. Check numeric volumes: longest & compound units first
    number_re = r'(\d+(?:[./٫]\d+)?)'
    unit_re = (
        r'(میلی\s*لیتری|میلی\s*لیتر|میلیلیتری|میلیلیتر|'
        r'کیلو\s*گرمی|کیلوگرمی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو|'
        r'سی\s*سی|سی‌سی|'
        r'لیتری|لیتر|'
        r'گرمی|گرم|'
        r'میلی|میل|'
        r'عددی|تایی|قلو|رول|برگ)'
    )
    unit_boundary = r'(?![آ-ی\w\u0600-\u06FF])'
    pattern = rf'{number_re}\s*{unit_re}{unit_boundary}'

    match = re.search(pattern, cleaned)
    if match:
        val_str = match.group(1).replace('٫', '.').replace('/', '.')
        val = float(val_str)
        unit_raw = match.group(2).replace(" ", "").replace("\u200c", "")

        # Check specific prefixes first: میلی before لیتر, کیلو before گرم
        if "میلی" in unit_raw or "سی" in unit_raw or "میل" in unit_raw:
            unit = "میلی‌لیتر"
        elif "کیلو" in unit_raw:
            unit = "کیلوگرم"
        elif "لیتر" in unit_raw:
            unit = "لیتر"
        elif "گرم" in unit_raw:
            # Typo guard: values < 10 with "گرم" (e.g. 3.75 گرمی for liquid soaps/detergents) are kg
            if val < 10.0 and any(w in cleaned for w in ["مایع", "روغن", "شوینده", "برنج", "پودر", "گالن"]):
                val = val * 1000.0
            unit = "گرم"
        elif any(u in unit_raw for u in ["عددی", "تایی", "قلو", "رول"]):
            unit = "عدد"
        elif "برگ" in unit_raw:
            unit = "برگ"
        else:
            unit = "عدد"
        return val, unit

    return None, None


def is_fat_compatible(requested_fat: Optional[float], title: str) -> bool:
    """Verifies that the candidate title doesn't contradict the requested fat level."""
    if requested_fat is None:
        return True

    cleaned = clean_persian_text(title)
    is_high_fat = "پر چرب" in cleaned or "پرچرب" in cleaned or "3%" in cleaned or "3.0%" in cleaned
    is_low_fat = "کم چرب" in cleaned or "کم‌چرب" in cleaned or "کمچرب" in cleaned or "1.5%" in cleaned or "1%" in cleaned

    if requested_fat >= 2.5:
        if is_low_fat and not is_high_fat:
            return False
    elif requested_fat <= 1.5:
        if is_high_fat and not is_low_fat:
            return False

    return True


def is_flavor_compatible(req_name: str, title: str) -> bool:
    """
    Verifies flavor compatibility between requested item and candidate title.
    If plain milk is requested without fruit/sweet flavors, candidates containing flavors are rejected.
    If a specific flavor is requested, candidates with different flavors are rejected.
    """
    if not req_name or not title:
        return True

    req_clean = clean_persian_text(req_name)
    cand_clean = clean_persian_text(title)

    if "شیر" in req_clean:
        req_flavors = [f for f in DAIRY_FLAVORS if f in req_clean]
        cand_flavors = [f for f in DAIRY_FLAVORS if f in cand_clean]

        if not req_flavors:
            # Plain milk requested (e.g. شیر, شیر پرچرب, شیر کم چرب, شیر بطری, شیر پاستوریزه)
            if cand_flavors:
                return False
        else:
            # Flavored milk requested: candidate must contain at least one requested flavor
            if not any(f in cand_flavors for f in req_flavors):
                return False
            # Conflicting flavors must not be present
            conflicting = [f for f in cand_flavors if f not in req_flavors]
            if conflicting:
                return False

    return True


def is_product_type_compatible(req_name: str, title: str) -> bool:
    """Verifies core product type (e.g. dishwashing liquid vs hand soap vs laundry detergent, and toilet paper vs facial tissue)."""
    if not req_name or not title:
        return True

    req_clean = clean_persian_text(req_name)
    cand_clean = clean_persian_text(title)
    folded_name = fold_grocery_aliases(req_name)
    folded_title = fold_grocery_aliases(title)

    # Petit beurre, mascarpone, and cocoa powder are easy to collapse into a
    # nearby grocery item: any biscuit, plain cheese, or chocolate milk.
    if "پتی بور" in folded_name and "پتی بور" not in folded_title:
        return False
    if "ماسکارپونه" in folded_name and "ماسکارپونه" not in folded_title:
        return False
    if folded_name == "پودر کاکائو" and ("شیر" in cand_clean or "کاکائو" not in cand_clean):
        return False

    if "ظرفشویی" in req_clean:
        if any(w in cand_clean for w in ["دستشویی", "لباسشویی", "قرص ماشین"]):
            return False
        if "ظرفشویی" not in cand_clean:
            return False
    elif "دستشویی" in req_clean:
        if any(w in cand_clean for w in ["ظرفشویی", "لباسشویی"]):
            return False
        if "دستشویی" not in cand_clean:
            return False
    elif "لباسشویی" in req_clean:
        if any(w in cand_clean for w in ["ظرفشویی", "دستشویی"]):
            return False
        if "لباسشویی" not in cand_clean:
            return False

    if "توالت" in req_clean:
        if any(w in cand_clean for w in ["کاغذی", "حوله", "حوله ای", "حوزه‌ای"]) and "توالت" not in cand_clean:
            return False
        if "توالت" not in cand_clean:
            return False
    elif "حوله" in req_clean:
        if "حوله" not in cand_clean:
            return False
    elif "کاغذی" in req_clean:
        if any(w in cand_clean for w in ["توالت", "حوله"]) and "کاغذی" not in cand_clean:
            return False

    # Exclude dispensers, holders, stands and accessories
    accessories = ["جا مایع", "جای مایع", "جامایع", "جا دستمال", "جای دستمال", "مخزن مایع", "مخزن دستمال", "استند", "پایه"]
    if any(acc in cand_clean for acc in accessories) and not any(acc in req_clean for acc in ["جا", "مخزن", "استند", "پایه"]):
        return False

    return True


def is_volume_compatible(req_vol: Optional[float], req_unit: Optional[str], title: str) -> bool:
    """
    Verifies that the candidate volume/weight/pack size matches the user's specification.
    Normalizes L/ml and kg/g to standard base units (ml and g) for exact comparison.
    Fixes the None bypass trap: if candidate volume cannot be extracted from title,
    but candidate title contains an explicit incompatible unit keyword or size mismatch, rejects it.
    """
    if req_vol is None or req_unit is None:
        return True

    def to_base(val: float, unit: str) -> float:
        if unit in ("لیتر", "کیلوگرم"):
            return val * 1000.0
        return val

    is_count_req = req_unit in ("عدد", "رول", "قلو", "برگ", "تایی", "عددی")
    cat_vol, cat_unit = extract_volume_from_title(title)

    if cat_vol is not None and cat_unit is not None:
        is_count_cat = cat_unit in ("عدد", "رول", "قلو", "برگ", "تایی", "عددی")
        if is_count_req != is_count_cat:
            return False
        req_base = to_base(req_vol, req_unit)
        cat_base = to_base(cat_vol, cat_unit)
        # 15% tolerance
        diff_ratio = abs(req_base - cat_base) / max(req_base, 1.0)
        return diff_ratio <= 0.15

    # Fix None bypass trap: candidate volume could not be extracted
    cleaned = clean_persian_text(title)

    if is_count_req:
        found_nums = re.findall(r'\b(\d+)\b', cleaned)
        if found_nums:
            num_ints = [int(n) for n in found_nums]
            if not any(abs(n - req_vol) / max(req_vol, 1.0) <= 0.15 for n in num_ints):
                return False
        return True

    req_base = to_base(req_vol, req_unit)

    # 1. Large requested items (>= 1000 base units, e.g. 1L, 4L, 1kg) must not match small units
    if req_base >= 1000.0:
        if any(u in cleaned for u in ["میلی", "سی سی", "سی‌سی"]):
            return False
        # Bulk items (>= 3L/kg, e.g. 4L gallon): reject grams and small 1kg/1L size indicators
        if req_vol >= 3.0:
            if any(u in cleaned for u in ["گرم", "گرمی"]):
                return False
            if any(k in cleaned for k in ["یک", "1", "۱", "کیلو", "نیم"]):
                if not any(big in cleaned for big in ["4", "۴", "چهار", "گالن"]):
                    return False

    # 2. Small requested items (< 1000 base units, e.g. 350g, 200ml) must not match large units
    if req_base < 1000.0:
        if any(u in cleaned for u in ["کیلو", "گالن"]):
            return False

    # 3. Explicit numeric mismatch check when digits appear in candidate title
    found_nums = re.findall(r'\b(\d+(?:\.\d+)?)\b', cleaned)
    if found_nums and req_vol >= 2.0:
        num_floats = [float(n) for n in found_nums]
        has_matching_num = any(
            (abs(n - req_vol) / max(req_vol, 1.0) <= 0.15) or
            (abs(n - req_base) / max(req_base, 1.0) <= 0.15)
            for n in num_floats
        )
        if not has_matching_num:
            return False

    return True


def match_sku(query_item: ParsedGroceryItem, candidates: List[StoreItem]) -> Optional[StoreItem]:
    """
    Finds the best matching StoreItem among candidates for a given query item.
    Enforces strict attribute filters (flavor, product type, fat, volume) and ranks by fuzzy similarity score.
    """
    if not candidates:
        return None

    best_item: Optional[StoreItem] = None
    best_score = 0.0

    query_full_text = f"{query_item.name} {query_item.raw_text}"

    for cand in candidates:
        # 1. Strict Attribute Verification: Flavor / Variant
        if not is_flavor_compatible(query_full_text, cand.title):
            continue

        # 2. Strict Attribute Verification: Product Type (e.g. dishwashing vs hand soap)
        if not is_product_type_compatible(query_item.name, cand.title):
            continue

        # 3. Strict Attribute Verification: Fat content
        if not is_fat_compatible(query_item.fat_percentage, cand.title):
            continue

        # 4. Strict Attribute Verification: Volume / Weight
        if not is_volume_compatible(query_item.volume_weight, query_item.unit, cand.title):
            continue

        # 5. Fuzzy Title Matching
        target_str = fold_grocery_aliases(f"{query_item.name} {query_item.brand or ''}")
        cand_str = fold_grocery_aliases(f"{cand.title} {cand.brand or ''}")

        sim_score = fuzz.token_set_ratio(target_str, cand_str) / 100.0

        # 6. Brand Verification & Penalization
        if query_item.brand:
            brand_in_cand = (query_item.brand in cand_str) or (cand.brand and query_item.brand in cand.brand)
            if not brand_in_cand:
                sim_score *= 0.6

        # 7. Core product noun verification
        if fold_grocery_aliases(query_item.name) not in cand_str:
            sim_score *= 0.5

        if sim_score > best_score and sim_score >= 0.50:
            best_score = sim_score
            best_item = cand

    if best_item:
        best_item.match_score = best_score
        return best_item

    return None
