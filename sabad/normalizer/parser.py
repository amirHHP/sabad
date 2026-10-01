"""
Rule-based Persian natural language grocery input parser.
Extracts canonical product names, brands, quantities, volumes/weights, and fat percentages.
"""

import re
from typing import List, Optional, Tuple
from sabad.models.grocery import ParsedGroceryItem, ParsedGroceryBasket
from sabad.normalizer.persian_digits import clean_persian_text, PERSIAN_WORD_NUMBERS

KNOWN_BRANDS = [
    # Dairy
    "کاله", "میهن", "پگاه", "روزانه", "چوپان", "دامداران", "رامک", "پاک", "هراز",
    "ویلی", "کیبی", "پاژن", "سحر", "ماهشام", "مانیزان", "دوشه",
    # Detergents & Hygiene
    "پریل", "تاژ", "پرسیل", "اکتیو", "گلرنگ", "صحت", "سافتلن", "اوه", "دامستوس",
    "سیف", "هوم پلاس", "درماکلین", "پریمیر", "سپید", "تیرک", "رخشا", "راپیدو",
    "سافتلین", "لطیفه", "کلیر", "داو", "مای",
    # Cooking Oils & Food Staples
    "اویلا", "لادن", "بهار", "غنچه", "فاملا", "طبیعت", "آفتاب", "سمن",
    "زر ماکارون", "تک ماکارون", "مانا", "سمیرا", "مک",
    # Condiments & Canned Goods
    "دلپذیر", "تبرک", "بهروز", "مهرام", "بیژن", "چین چین", "روژین", "رعنا", "یک و یک",
    "شیلتون", "تحفه", "اصالت", "برتر", "ترخینه",
    # Beverages & Tea
    "سن ایچ", "رانی", "عالیس", "ایستک", "هیولا", "پپسی", "کوکاکولا", "فانتا",
    "گلستان", "احمد", "دبش", "محمود", "شهرزاد", "دوغابان",
    # Paper & Tissues
    "پاپیا", "تنرو", "پرفکس", "سافتکس", "حریر", "گلریز", "شکوه", "مرحبا",
    # Bakery & Sweets
    "شیرین عسل", "آناتا", "مینو", "فرمند", "آیدین", "چی توز", "مبینا", "پفک نمکی",
]

KNOWN_PRODUCTS = [
    ("مایع ظرفشویی", "شوینده"),
    ("مایع دستشویی", "شوینده"),
    ("مایع لباسشویی", "شوینده"),
    ("پودر لباسشویی", "شوینده"),
    ("مایع سفید کننده", "شوینده"),
    ("جرم گیر", "شوینده"),
    ("نرم کننده حوله و لباس", "شوینده"),
    ("اسکاچ", "شوینده"),
    ("دستمال توالت", "سلولزی"),
    ("دستمال کاغذی", "سلولزی"),
    ("شیر", "لبنیات"),
    ("ماست", "لبنیات"),
    ("پنیر", "لبنیات"),
    ("خامه", "لبنیات"),
    ("کره", "لبنیات"),
    ("دوغ", "لبنیات"),
    ("کشک", "لبنیات"),
    ("تخم مرغ", "پروتئینی"),
    ("روغن سرخ کردنی", "خواربار"),
    ("روغن پخت و پز", "خواربار"),
    ("روغن مایع", "خواربار"),
    ("روغن زیتون", "خواربار"),
    ("روغن", "خواربار"),
    ("رب گوجه فرنگی", "کنسرو"),
    ("رب گوجه", "کنسرو"),
    ("کنسرو ماهی تن", "کنسرو"),
    ("تن ماهی", "کنسرو"),
    ("ماکارونی", "خواربار"),
    ("رشته سوپ", "خواربار"),
    ("برنج", "خواربار"),
    ("شکر", "خواربار"),
    ("قند", "خواربار"),
    ("چای", "نوشیدنی"),
    ("قهوه", "نوشیدنی"),
    ("آبمیوه", "نوشیدنی"),
    ("سس مایونز", "سس و چاشنی"),
    ("سس کچاپ", "سس و چاشنی"),
    ("سس", "سس و چاشنی"),
]


def extract_volume_weight(text: str) -> Tuple[Optional[float], Optional[str], str]:
    """Extracts volume or weight attribute (e.g. 1 لیتری, 350 گرمی, 4 لیتر, یک لیتری)."""
    # 1. First check verbal volumes like "یک لیتری", "نیم لیتری", "دو لیتری"
    verbal_vol_patterns = [
        (r'\b(یک|یه)\s*(?:لیتر|لیتری)\b', 1.0, "لیتر"),
        (r'\b(دو)\s*(?:لیتر|لیتری)\b', 2.0, "لیتر"),
        (r'\b(سه)\s*(?:لیتر|لیتری)\b', 3.0, "لیتر"),
        (r'\b(چهار)\s*(?:لیتر|لیتری)\b', 4.0, "لیتر"),
        (r'\b(نیم)\s*(?:لیتر|لیتری|کیلو|کیلویی)\b', 0.5, "لیتر"),
        (r'\b(یک|یه)\s*(?:کیلو|کیلویی|کیلوگرم)\b', 1.0, "کیلوگرم"),
    ]
    for pat, val, unit in verbal_vol_patterns:
        match = re.search(pat, text)
        if match:
            cleaned = text[:match.start()] + " " + text[match.end():]
            return val, unit, cleaned.strip()

    # 2. Check numeric volumes like "350 گرمی", "1 لیتری", "4 لیتر"
    pattern = r'(\d+(?:\.\d+)?)\s*(لیتر|لیتری|میلی\s*لیتر|سی\s*سی|سی‌سی|گرم|گرمی|کیلوگرم|کیلو|کیلویی)\b'
    match = re.search(pattern, text)
    if match:
        val = float(match.group(1))
        unit_raw = match.group(2).replace(" ", "")
        
        if "لیتر" in unit_raw:
            unit = "لیتر"
        elif "میلی" in unit_raw or "سی" in unit_raw:
            unit = "میلی‌لیتر"
        elif "کیلو" in unit_raw:
            unit = "کیلوگرم"
        else:
            unit = "گرم"
            
        cleaned = text[:match.start()] + " " + text[match.end():]
        return val, unit, cleaned.strip()

    return None, None, text


def extract_fat_percentage(text: str) -> Tuple[Optional[float], str]:
    """Extracts fat content (e.g. پرچرب, کم چرب, 1.5 درصد)."""
    cleaned = text
    if "پر چرب" in cleaned or "پرچرب" in cleaned:
        cleaned = re.sub(r'\bپر\s*چرب\b', '', cleaned)
        return 3.0, cleaned.strip()
    if "کم چرب" in cleaned or "کم‌چرب" in cleaned or "کمچرب" in cleaned:
        cleaned = re.sub(r'\bکم\s*چرب\b', '', cleaned)
        return 1.5, cleaned.strip()
    if "نیم چرب" in cleaned or "نیم‌چرب" in cleaned:
        cleaned = re.sub(r'\bنیم\s*چرب\b', '', cleaned)
        return 2.5, cleaned.strip()

    pct_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:درصد|٪)\s*(?:چربی)?', cleaned)
    if pct_match:
        val = float(pct_match.group(1))
        cleaned = cleaned[:pct_match.start()] + " " + cleaned[pct_match.end():]
        return val, cleaned.strip()

    return None, cleaned


def extract_quantity(text: str) -> Tuple[int, str]:
    """Extracts requested count and returns (quantity, cleaned_text)."""
    # 1. Verbal numbers at the beginning or with counters e.g. "دو تا", "یه", "سه تا"
    for word, qty in sorted(PERSIAN_WORD_NUMBERS.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = rf'^\s*{word}(?:\s*(?:تا|عدد|بسته|دونه|بطری|قوطی|جعبه|پاکت))?\b|\b{word}\s*(?:تا|عدد|بسته|دونه|بطری|قوطی|جعبه|پاکت)\b'
        match = re.search(pattern, text)
        if match:
            cleaned = text[:match.start()] + " " + text[match.end():]
            return int(qty) if qty >= 1 else 1, cleaned.strip()

    # 2. Check for numeric digits with counter words e.g. "2 تا", "3 عدد"
    num_match = re.search(r'^\s*(\d+)\s*(?:تا|عدد|بسته|دونه|بطری|قوطی|جعبه|پاکت)?\b|\b(\d+)\s*(?:تا|عدد|بسته|دونه|بطری|قوطی|جعبه|پاکت)\b', text)
    if num_match:
        val_str = num_match.group(1) or num_match.group(2)
        qty = int(val_str)
        cleaned = text[:num_match.start()] + " " + text[num_match.end():]
        return max(1, qty), cleaned.strip()

    return 1, text


def extract_brand(text: str) -> Tuple[Optional[str], str]:
    """Finds matching brand from known FMCG brands list."""
    cleaned = text
    for brand in KNOWN_BRANDS:
        pattern = rf'\b{brand}\b'
        if re.search(pattern, cleaned):
            cleaned = re.sub(pattern, " ", cleaned, count=1).strip()
            return brand, cleaned

    return None, cleaned


def extract_product_and_category(text: str) -> Tuple[str, Optional[str]]:
    """Identifies the core product noun and general category."""
    for prod_name, cat in KNOWN_PRODUCTS:
        if prod_name in text:
            return prod_name, cat
    
    words = [w for w in text.split() if len(w) > 1 and w not in ["عدد", "تا", "بسته", "کیلو", "یک", "دو"]]
    fallback_name = " ".join(words[:2]) if words else text
    return fallback_name or "کالای عمومی", None


def parse_single_item(raw_phrase: str) -> ParsedGroceryItem:
    """Parses a single grocery line or item expression into a ParsedGroceryItem."""
    cleaned = clean_persian_text(raw_phrase)
    
    # Priority 1: Extract volume / weight FIRST to avoid consuming volumes as quantities
    vol_weight, unit, cleaned = extract_volume_weight(cleaned)
    
    # Priority 2: Extract fat percentage
    fat, cleaned = extract_fat_percentage(cleaned)
    
    # Priority 3: Extract quantity
    qty, cleaned = extract_quantity(cleaned)
    
    # Priority 4: Extract brand
    brand, cleaned = extract_brand(cleaned)
    
    # Priority 5: Extract product name & category
    prod_name, cat = extract_product_and_category(cleaned)

    return ParsedGroceryItem(
        raw_text=raw_phrase.strip(),
        name=prod_name,
        brand=brand,
        quantity=qty,
        volume_weight=vol_weight,
        unit=unit,
        fat_percentage=fat,
        category=cat
    )


def parse_grocery_input(raw_input: str) -> ParsedGroceryBasket:
    """
    Parses a multi-item Persian user input text.
    Handles delimiters: commas (، ,), newlines, and conjunction words like ' و '.
    """
    if not raw_input or not raw_input.strip():
        return ParsedGroceryBasket(raw_input="", items=[])

    cleaned_input = clean_persian_text(raw_input)
    phrases = re.split(r'[,،\n;؛]+', cleaned_input)
    
    items: List[ParsedGroceryItem] = []
    for chunk in phrases:
        chunk = chunk.strip()
        if not chunk:
            continue
            
        sub_chunks = re.split(r'\s+و\s+(?=(?:یک|دو|سه|چهار|پنج|یه|\d+)\s+)', chunk)
        for sub in sub_chunks:
            sub = sub.strip()
            if sub:
                parsed = parse_single_item(sub)
                items.append(parsed)

    return ParsedGroceryBasket(raw_input=raw_input, items=items)
