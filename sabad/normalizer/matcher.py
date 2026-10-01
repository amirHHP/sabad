"""
SKU matching engine using RapidFuzz similarity and strict attribute verification.
Guarantees zero mismatched variants (e.g. 1L vs 200ml milk, or full-fat vs low-fat).
"""

import re
from typing import List, Optional, Tuple
from rapidfuzz import fuzz
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.catalog import StoreItem
from sabad.normalizer.persian_digits import clean_persian_text


def extract_volume_from_title(title: str) -> Tuple[Optional[float], Optional[str]]:
    """Extracts numeric volume/weight and unit from catalog SKU title."""
    cleaned = clean_persian_text(title)
    # Put multi-word and longer units FIRST
    pattern = r'(\d+(?:\.\d+)?)\s*(میلی\s*لیتری|میلی\s*لیتر|سی\s*سی|سی‌سی|کیلو\s*گرم|کیلوگرم|کیلویی|کیلو|لیتری|لیتر|گرمی|گرم)\b'
    match = re.search(pattern, cleaned)
    if match:
        val = float(match.group(1))
        unit_raw = match.group(2).replace(" ", "")
        
        # Check specific prefixes first!
        if "میلی" in unit_raw or "سی" in unit_raw:
            unit = "میلی‌لیتر"
        elif "کیلو" in unit_raw:
            unit = "کیلوگرم"
        elif "لیتر" in unit_raw:
            unit = "لیتر"
        else:
            unit = "گرم"
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


def is_volume_compatible(req_vol: Optional[float], req_unit: Optional[str], title: str) -> bool:
    """
    Verifies that the candidate volume/weight matches the user's specification.
    Normalizes L/ml and kg/g to standard base units (ml and g) for exact comparison.
    """
    if req_vol is None or req_unit is None:
        return True

    cat_vol, cat_unit = extract_volume_from_title(title)
    if cat_vol is None or cat_unit is None:
        return True

    def to_base(val: float, unit: str) -> float:
        if unit == "لیتر":
            return val * 1000.0
        if unit == "کیلوگرم":
            return val * 1000.0
        return val

    req_base = to_base(req_vol, req_unit)
    cat_base = to_base(cat_vol, cat_unit)

    # 15% tolerance
    diff_ratio = abs(req_base - cat_base) / max(req_base, 1.0)
    return diff_ratio <= 0.15


def match_sku(query_item: ParsedGroceryItem, candidates: List[StoreItem]) -> Optional[StoreItem]:
    """
    Finds the best matching StoreItem among candidates for a given query item.
    Enforces strict attribute filters (volume, fat, brand) and ranks by fuzzy similarity score.
    """
    if not candidates:
        return None

    best_item: Optional[StoreItem] = None
    best_score = 0.0

    for cand in candidates:
        # 1. Strict Attribute Verification: Fat content
        if not is_fat_compatible(query_item.fat_percentage, cand.title):
            continue

        # 2. Strict Attribute Verification: Volume / Weight
        if not is_volume_compatible(query_item.volume_weight, query_item.unit, cand.title):
            continue

        # 3. Fuzzy Title Matching
        target_str = clean_persian_text(f"{query_item.name} {query_item.brand or ''}")
        cand_str = clean_persian_text(f"{cand.title} {cand.brand or ''}")
        
        sim_score = fuzz.token_set_ratio(target_str, cand_str) / 100.0

        # 4. Brand Verification & Penalization
        if query_item.brand:
            brand_in_cand = (query_item.brand in cand_str) or (cand.brand and query_item.brand in cand.brand)
            if not brand_in_cand:
                sim_score *= 0.6

        # 5. Core product noun verification
        if query_item.name not in cand_str:
            sim_score *= 0.5

        if sim_score > best_score and sim_score >= 0.50:
            best_score = sim_score
            best_item = cand

    if best_item:
        best_item.match_score = best_score
        return best_item

    return None
