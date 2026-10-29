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
    ("دستمال حوله", "سلولزی"),
    ("دستمال", "سلولزی"),
    ("پتی بور", "تنقلات"),
    ("پودر کاکائو", "خواربار"),
    ("شیر", "لبنیات"),
    ("ماست", "لبنیات"),
    ("پنیر ماسکارپونه", "لبنیات"),
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
    """Extracts volume or weight attribute (e.g. 1 لیتری, 350 گرمی, 4 لیتر, یک لیتری, نیم کیلو)."""
    cleaned_text = clean_persian_text(text)

    # 1. First check verbal volumes (compound numbers e.g. "یک و نیم" first)
    verbal_vol_patterns = [
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

        # Pack / roll counts (toilet paper, tissue rolls)
        (r'(?:\b|^)(?:دو|۲)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 2.0, "عدد"),
        (r'(?:\b|^)(?:چهار|۴)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 4.0, "عدد"),
        (r'(?:\b|^)(?:شش|۶)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 6.0, "عدد"),
        (r'(?:\b|^)(?:هشت|۸)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 8.0, "عدد"),
        (r'(?:\b|^)(?:ده|۱۰)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 10.0, "عدد"),
        (r'(?:\b|^)(?:دوازده|۱۲)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 12.0, "عدد"),
        (r'(?:\b|^)(?:شانزده|۱۶)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 16.0, "عدد"),
        (r'(?:\b|^)(?:بیست و چهار|۲۴)\s*(?:قلو|رول)(?![آ-ی\w\u0600-\u06FF])', 24.0, "عدد"),
    ]
    for pat, val, unit in verbal_vol_patterns:
        match = re.search(pat, cleaned_text)
        if match:
            cleaned = cleaned_text[:match.start()] + " " + cleaned_text[match.end():]
            return val, unit, cleaned.strip()

    # 2. Check numeric volumes like "350 گرمی", "1 لیتری", "4 لیتر", "۹۵۵ میلی‌لیتر", "۱/۵ لیتری", "۸ عددی", "۴۰۰ میلی"
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

    match = re.search(pattern, cleaned_text)
    if match:
        val_str = match.group(1).replace('٫', '.').replace('/', '.')
        val = float(val_str)
        unit_raw = match.group(2).replace(" ", "").replace("\u200c", "")

        # Strict substring classification order: میلی before لیتر, کیلو before گرم
        if "میلی" in unit_raw or "سی" in unit_raw or "میل" in unit_raw:
            unit = "میلی‌لیتر"
        elif "کیلو" in unit_raw:
            unit = "کیلوگرم"
        elif "لیتر" in unit_raw:
            unit = "لیتر"
        elif "گرم" in unit_raw:
            unit = "گرم"
        elif any(u in unit_raw for u in ["عددی", "تایی", "قلو", "رول"]):
            unit = "عدد"
        elif "برگ" in unit_raw:
            unit = "برگ"
        else:
            unit = "عدد"

        cleaned = cleaned_text[:match.start()] + " " + cleaned_text[match.end():]
        return val, unit, cleaned.strip()

    return None, None, cleaned_text.strip()


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


def fold_grocery_aliases(text: str) -> str:
    """Collapse spelling variants that voice notes use for the same grocery item."""
    text = clean_persian_text(text)
    text = re.sub(r"پتی\s*بور|پتیبور|پیتی\s*بور|پتیت\s*بور", "پتی بور", text)
    text = re.sub(r"مسکارپونه", "ماسکارپونه", text)
    text = re.sub(r"ماسکارپون(?!ه)", "ماسکارپونه", text)
    text = re.sub(r"پنیر\s*ماسکارپونه", "پنیر ماسکارپونه", text)
    text = re.sub(r"(?<!پنیر )ماسکارپونه", "پنیر ماسکارپونه", text)
    text = re.sub(r"پودر\s*کاکائو|پودر\s*کاکاو", "پودر کاکائو", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_product(text: str, name: str) -> bool:
    """True when ``name`` is a whole word or phrase, not a prefix of a longer word."""
    return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text) is not None


_LIST_FILLERS = {"خوب", "خب", "آره", "بله", "من", "لطفا", "بعد", "بعدش", "حالا", "دیگه", "هم"}
# Voice notes often list items as «پتی بور میخوام شیر میخوام …» with no comma or «و».
_REQUEST_SPLIT_RE = re.compile(
    r"(?:^|\s+)(?:می\s*خوام(?:ش)?(?:\s+که)?|می\s*خواستم|لازم\s*دارم)(?:\s+|$)"
)


def _strip_list_fillers(text: str) -> str:
    words = text.replace("،", " ").split()
    while words and (words[0] in _LIST_FILLERS or words[0] == "و"):
        words.pop(0)
    while words and words[-1] in _LIST_FILLERS:
        words.pop()
    return " ".join(words).strip()


def _split_on_requests(chunk: str) -> List[str]:
    parts = [part.strip() for part in _REQUEST_SPLIT_RE.split(chunk)]
    parts = [part for part in parts if part]
    return parts or [chunk]


def extract_product_and_category(text: str) -> Tuple[str, Optional[str]]:
    """Identifies the core product noun and general category."""
    found = [(name, cat) for name, cat in KNOWN_PRODUCTS if _contains_product(text, name)]
    if found:
        found.sort(key=lambda item: len(item[0]), reverse=True)
        return found[0]

    words = [w for w in text.split() if len(w) > 1 and w not in ["عدد", "تا", "بسته", "کیلو", "یک", "دو"]]
    fallback_name = " ".join(words[:2]) if words else text
    return fallback_name or "کالای عمومی", None


def parse_single_item(raw_phrase: str) -> ParsedGroceryItem:
    """Parses a single grocery line or item expression into a ParsedGroceryItem."""
    cleaned = fold_grocery_aliases(raw_phrase)
    
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


def parse_grocery_input_rule_based(raw_input: str) -> ParsedGroceryBasket:
    """
    Deterministically parses a multi-item Persian user input text using rule-based regex patterns.
    Handles delimiters: commas (، ,), newlines, conjunctions like ' و ', and
    repeated request verbs such as 'میخوام' in dictated lists.
    """
    if not raw_input or not raw_input.strip():
        return ParsedGroceryBasket(raw_input="", items=[], engine="rule_based")

    cleaned_input = fold_grocery_aliases(raw_input)
    phrases = re.split(r'[,،\n;؛]+', cleaned_input)
    
    items: List[ParsedGroceryItem] = []
    product_starts = sorted((name for name, _ in KNOWN_PRODUCTS), key=len, reverse=True)
    next_item = r"(?:یک|دو|سه|چهار|پنج|یه|\d+)\s+|" + "|".join(re.escape(p) for p in product_starts)
    for chunk in phrases:
        chunk = chunk.strip()
        if not chunk:
            continue

        # «میخوام» separates dictated items. «و» still separates items even
        # when the next one has no quantity.
        for requested in _split_on_requests(chunk):
            requested = _strip_list_fillers(requested)
            if not requested:
                continue
            sub_chunks = re.split(rf"\s+و\s+(?=(?:{next_item}))", requested)
            for sub in sub_chunks:
                sub = _strip_list_fillers(sub)
                if sub:
                    items.append(parse_single_item(sub))

    return ParsedGroceryBasket(raw_input=raw_input, items=items, engine="rule_based")


def parse_grocery_input(
    raw_input: str,
    use_llm: bool = True,
    *args,
    **kwargs,
) -> ParsedGroceryBasket:
    """
    Parses a multi-item Persian user input text into a structured ParsedGroceryBasket.
    When use_llm=True and GEMINI_API_KEY is configured, uses Gemini (gemini-3.5-flash-lite)
    for high-fidelity semantic parsing, with automatic fallback to rule-based parser.
    Accepts both positional and keyword arguments (use_llm, use_ai) and absorbs extra args safely.
    """
    if not raw_input or not raw_input.strip():
        return ParsedGroceryBasket(raw_input="", items=[], engine="rule_based")

    if "use_ai" in kwargs:
        effective_use_llm = bool(kwargs["use_ai"])
    elif "use_llm" in kwargs:
        effective_use_llm = bool(kwargs["use_llm"])
    else:
        effective_use_llm = bool(use_llm)

    if effective_use_llm:
        import os
        import sabad.config as config
        gemini_key = getattr(config, "GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "")).strip()
        if gemini_key:
            try:
                from sabad.normalizer.gemini_parser import parse_grocery_input_gemini
                gemini_basket = parse_grocery_input_gemini(raw_input, api_key=gemini_key)
                if gemini_basket and gemini_basket.items:
                    return gemini_basket
            except Exception:
                pass

    return parse_grocery_input_rule_based(raw_input)
