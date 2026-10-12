"""
Gemini-powered semantic parser for Persian natural language grocery lists.
Uses Google Gemini (e.g. gemini-3.5-flash-lite) to accurately extract product names,
brands, quantities, volumes, weights, fat percentages, and categories from colloquial Persian.
"""

import json
import logging
from typing import List, Optional
import httpx

import os
import sabad.config as config

GEMINI_API_KEY = getattr(config, "GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "")).strip()
GEMINI_MODEL = getattr(config, "GEMINI_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")).strip()
from sabad.models.grocery import ParsedGroceryItem, ParsedGroceryBasket

logger = logging.getLogger(__name__)

GEMINI_API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)

SYSTEM_PROMPT = """تو یک سیستم هوشمند و دقیق برای استخراج اقلام لیست خرید سوپرمارکتی از متن‌های فارسی (محاوره‌ای و رسمی) هستی.
وظیفه تو این است که هر قلم کالا را تحلیل کرده و در قالب آرایه‌ای از اشیای JSON با مشخصات زیر برگردانی:

قوانین استخراج:
- raw_text: دقیقا همان عبارت مربوط به این قلم در متن ورودی کاربر.
- name: نام اصلی و کاتالوگی کالا بدون برند، بدون حجم/وزن و بدون درصد چربی (مثلاً: شیر، ماست، پنیر، مایع ظرفشویی، مایع دستشویی، روغن سرخ کردنی، روغن مایع، برنج، شکر، رب گوجه فرنگی، تن ماهی، دستمال کاغذی، دستمال توالت، تخم مرغ).
- brand: نام برند کالا (مثلاً: کاله، میهن، پگاه، روزانه، چوپان، دامداران، ویلی، پریل، اکتیو، تاژ، پرسیل، اویلا، لادن، بهار، طبیعت، دلپذیر، تبرک، پاپیا، تنرو) در صورت ذکر شدن؛ در غیر این صورت مقدار null.
- quantity: تعداد بسته‌ها یا واحدهای درخواستی به صورت عدد صحیح بزرگتر یا مساوی ۱ (پیش‌فرض ۱).
- volume_weight: عدد مربوط به وزن یا حجم کالا (مثلاً 1.0 یا 0.5 یا 350 یا 4.0 یا 900)؛ در صورتی که مشخص نشده باشد null.
- unit: واحد استاندارد کالا، شامل یکی از این موارد: "لیتر"، "میلی‌لیتر"، "کیلوگرم"، "گرم"، "عدد". برای اقلام بسته‌ای مانند دستمال چند عددی/قلو/رول (مثلاً دستمال ۸ عددی)، volume_weight عدد ۸ و unit مقدار "عدد" باشد؛ در غیر این صورت null.
- fat_percentage: فقط در صورتی که در متن ورودی کاربر صراحتاً درصد چربی یا کلماتی مانند «پرچرب»، «کم‌چرب» یا «نیم‌چرب» برای لبنیات قید شده باشد (مثلاً پرچرب = 3.0، کم‌چرب = 1.5، یا درصدی مانند 1.5%). اگر کاربر در متن به چربی اشاره نکرده است (مثلا فقط گفته پنیر ویلی ۳۵۰ گرمی)، حتماً مقدار null باشد.
- category: دسته‌بندی کلی کالا، شامل یکی از موارد: "لبنیات"، "شوینده"، "خواربار"، "سلولزی"، "کنسرو"، "نوشیدنی"، "پروتئینی"، "تنقلات".
"""

RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "raw_text": {"type": "string"},
            "name": {"type": "string"},
            "brand": {"type": "string"},
            "quantity": {"type": "integer"},
            "volume_weight": {"type": "number"},
            "unit": {"type": "string"},
            "fat_percentage": {"type": "number"},
            "category": {"type": "string"},
        },
        "required": ["raw_text", "name", "quantity"],
    },
}


def _sanitize_items(raw_items: List[dict]) -> List[ParsedGroceryItem]:
    """Sanitizes raw JSON dicts returned from Gemini into validated ParsedGroceryItems."""
    cleaned_items: List[ParsedGroceryItem] = []
    
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
            
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
            
        raw_text = str(raw.get("raw_text", "")).strip() or name
        brand = raw.get("brand")
        if brand is not None:
            brand = str(brand).strip()
            if not brand or brand.lower() in ("null", "none"):
                brand = None
                
        category = raw.get("category")
        if category is not None:
            category = str(category).strip()
            if not category or category.lower() in ("null", "none"):
                category = None

        unit = raw.get("unit")
        if unit is not None:
            unit = str(unit).strip()
            if not unit or unit.lower() in ("null", "none"):
                unit = None

        vol_weight = raw.get("volume_weight")
        if vol_weight is not None:
            try:
                vol_weight = float(vol_weight)
            except (ValueError, TypeError):
                vol_weight = None

        fat = raw.get("fat_percentage")
        if fat is not None:
            try:
                fat = float(fat)
                # If non-dairy or 0.0 or not explicitly mentioned in raw_text, clear it
                fat_indicators = ["چرب", "چربی", "%", "٪", "درصد"]
                if category != "لبنیات" or fat <= 0 or not any(ind in raw_text for ind in fat_indicators):
                    fat = None
            except (ValueError, TypeError):
                fat = None

        qty = raw.get("quantity", 1)
        try:
            qty = max(1, int(qty))
        except (ValueError, TypeError):
            qty = 1

        cleaned_items.append(
            ParsedGroceryItem(
                raw_text=raw_text,
                name=name,
                brand=brand,
                quantity=qty,
                volume_weight=vol_weight,
                unit=unit,
                fat_percentage=fat,
                category=category,
            )
        )

    return cleaned_items


def parse_grocery_input_gemini(
    raw_input: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 12.0,
) -> Optional[ParsedGroceryBasket]:
    """
    Synchronously parses Persian grocery input text using Gemini API.
    Returns ParsedGroceryBasket or None if parsing fails.
    """
    raw_key = api_key if api_key is not None else (getattr(config, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", ""))
    key = raw_key.strip() if raw_key else ""
    if not key or not raw_input or not raw_input.strip():
        return None

    model_name = (model or getattr(config, "GEMINI_MODEL", "") or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")).strip()
    url = GEMINI_API_URL_TEMPLATE.format(model=model_name, key=key)

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": f"متن لیست خرید کاربر:\n{raw_input.strip()}"}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.1,
        },
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(
                    f"Gemini API returned status {resp.status_code}: {resp.text[:200]}"
                )
                return None

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return None

            json_text = parts[0].get("text", "")
            raw_items = json.loads(json_text)
            parsed_items = _sanitize_items(raw_items)

            if parsed_items:
                return ParsedGroceryBasket(raw_input=raw_input, items=parsed_items, engine="gemini")
            return None

    except Exception as e:
        logger.warning(f"Gemini semantic parsing failed: {e}")
        return None


async def async_parse_grocery_input_gemini(
    raw_input: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 12.0,
) -> Optional[ParsedGroceryBasket]:
    """
    Asynchronously parses Persian grocery input text using Gemini API.
    Returns ParsedGroceryBasket or None if parsing fails.
    """
    raw_key = api_key if api_key is not None else (getattr(config, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", ""))
    key = raw_key.strip() if raw_key else ""
    if not key or not raw_input or not raw_input.strip():
        return None

    model_name = (model or getattr(config, "GEMINI_MODEL", "") or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")).strip()
    url = GEMINI_API_URL_TEMPLATE.format(model=model_name, key=key)

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": f"متن لیست خرید کاربر:\n{raw_input.strip()}"}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.1,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(
                    f"Gemini API returned status {resp.status_code}: {resp.text[:200]}"
                )
                return None

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return None

            json_text = parts[0].get("text", "")
            raw_items = json.loads(json_text)
            parsed_items = _sanitize_items(raw_items)

            if parsed_items:
                return ParsedGroceryBasket(raw_input=raw_input, items=parsed_items, engine="gemini")
            return None

    except Exception as e:
        logger.warning(f"Async Gemini semantic parsing failed: {e}")
        return None
