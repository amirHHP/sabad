"""
Unit tests for Persian Natural Language Normalizer & SKU Matcher.
"""

import pytest
from sabad.normalizer.persian_digits import clean_persian_text, to_ascii_digits
from sabad.normalizer.parser import parse_grocery_input, parse_single_item
from sabad.normalizer.matcher import match_sku, is_volume_compatible, is_fat_compatible
from sabad.models.catalog import StoreItem


def test_persian_digits_conversion():
    assert to_ascii_digits("۰۱۲۳۴۵۶۷۸۹") == "0123456789"
    assert to_ascii_digits("٠١٢٣٤٥٦٧٨٩") == "0123456789"
    assert clean_persian_text("شير پر‌چرب") == "شیر پر چرب"


def test_parse_single_item():
    item1 = parse_single_item("دو تا شیر پرچرب کاله یک لیتری")
    assert item1.name == "شیر"
    assert item1.brand == "کاله"
    assert item1.quantity == 2
    assert item1.volume_weight == 1.0
    assert item1.unit == "لیتر"
    assert item1.fat_percentage == 3.0

    item2 = parse_single_item("یه پنیر ویلی ۳۵۰ گرمی")
    assert item2.name == "پنیر"
    assert item2.brand == "ویلی"
    assert item2.quantity == 1
    assert item2.volume_weight == 350.0
    assert item2.unit == "گرم"

    item3 = parse_single_item("یه مایع ظرفشویی پریل ۴ لیتری")
    assert item3.name == "مایع ظرفشویی"
    assert item3.brand == "پریل"
    assert item3.quantity == 1
    assert item3.volume_weight == 4.0
    assert item3.unit == "لیتر"


def test_parse_multi_item_basket():
    text = "دو تا شیر پرچرب کاله یک لیتری، یه پنیر ویلی ۳۵۰ گرمی، یه مایع ظرفشویی پریل ۴ لیتری"
    basket = parse_grocery_input(text)
    assert len(basket.items) == 3
    assert basket.items[0].name == "شیر"
    assert basket.items[1].name == "پنیر"
    assert basket.items[2].name == "مایع ظرفشویی"


import os
import sabad.config as config
_has_gemini_key = bool(os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", ""))


@pytest.mark.skipif(not _has_gemini_key, reason="GEMINI_API_KEY not configured or unavailable")
def test_gemini_semantic_parser_live():
    from sabad.normalizer.gemini_parser import parse_grocery_input_gemini
    text = "دو تا شیر پرچرب کاله یک لیتری و یه مایع ظرفشویی پریل ۴ لیتری"
    basket = parse_grocery_input_gemini(text)
    if basket is None:
        pytest.skip("Gemini API quota exceeded or service unavailable")
    assert basket is not None
    assert len(basket.items) == 2
    assert basket.items[0].name == "شیر"
    assert basket.items[0].brand == "کاله"
    assert basket.items[0].quantity == 2
    assert basket.items[0].volume_weight == 1.0
    assert basket.items[0].unit == "لیتر"
    assert basket.items[1].name == "مایع ظرفشویی"
    assert basket.items[1].brand == "پریل"


def test_gemini_fallback_on_invalid_key():
    from sabad.normalizer.gemini_parser import parse_grocery_input_gemini
    # Invalid key returns None
    result = parse_grocery_input_gemini("دو تا شیر کاله", api_key="INVALID_KEY")
    assert result is None
    # Main parser falls back smoothly to rule-based
    fallback_basket = parse_grocery_input("دو تا شیر کاله", use_llm=False)
    assert len(fallback_basket.items) == 1
    assert fallback_basket.items[0].name == "شیر"


def test_parse_grocery_input_signature_compatibility():
    """Validates that parse_grocery_input accepts positional, keyword, and alias arguments."""
    text = "دو تا شیر کاله"

    # Default invocation
    b1 = parse_grocery_input(text)
    assert len(b1.items) == 1

    # Positional use_llm=False
    b2 = parse_grocery_input(text, False)
    assert len(b2.items) == 1

    # Keyword use_llm=False
    b3 = parse_grocery_input(text, use_llm=False)
    assert len(b3.items) == 1

    # Legacy alias use_ai=False
    b4 = parse_grocery_input(text, use_ai=False)
    assert len(b4.items) == 1

    # Tolerant to extra kwargs and args (prevents unexpected keyword argument crashes)
    b5 = parse_grocery_input(text, False, "extra_pos", unknown_kwarg=42)
    assert len(b5.items) == 1


def test_importlib_reload_and_cache_resilience():
    """Simulates Streamlit hot-reloading submodules and verifies signature stability."""
    import importlib
    import sabad.normalizer.parser as parser_mod
    import sabad.normalizer as normalizer_pkg
    from app import safe_parse_grocery_input

    # Reload modules like Streamlit does
    importlib.reload(parser_mod)
    importlib.reload(normalizer_pkg)

    # Invoke via safe_parse_grocery_input
    basket = safe_parse_grocery_input("یه ماست سون کاله", use_ai=False)
    assert len(basket.items) == 1
    assert basket.items[0].name == "ماست"


def test_legacy_signature_fallback_simulation():
    """Simulates encountering a legacy in-memory function signature without use_llm parameter."""
    import inspect

    def legacy_parse(raw_text: str):
        return parse_grocery_input(raw_text, use_llm=False)

    sig = inspect.signature(legacy_parse)
    assert "use_llm" not in sig.parameters

    # Verify fallback logic
    user_input = "یه پنیر ویلی"
    use_ai = True
    try:
        if "use_llm" in sig.parameters:
            basket = legacy_parse(user_input, use_llm=use_ai)
        else:
            basket = legacy_parse(user_input)
    except TypeError:
        basket = legacy_parse(user_input)

    assert len(basket.items) == 1
    assert basket.items[0].name == "پنیر"


def test_strict_volume_matching():
    # 1L should NOT match 200ml
    assert is_volume_compatible(1.0, "لیتر", "شیر کم چرب کاله 1 لیتری") is True
    assert is_volume_compatible(1.0, "لیتر", "شیر کاکائو 200 میلی لیتری") is False
    assert is_volume_compatible(1.0, "لیتر", "شیر پاکتی 945 میلی لیتر") is True  # within 15% tolerance


def test_strict_fat_matching():
    # Full-fat (3%) must not match low-fat (1.5%)
    assert is_fat_compatible(3.0, "شیر کم چرب پگاه") is False
    assert is_fat_compatible(3.0, "شیر پرچرب کاله") is True
    assert is_fat_compatible(1.5, "شیر پرچرب کاله") is False
    assert is_fat_compatible(1.5, "شیر کم چرب روزانه") is True


def test_sku_matcher_ranking():
    query = parse_single_item("شیر پرچرب کاله یک لیتری")
    
    candidates = [
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="p1",
            title="شیر کم چرب کاله 1 لیتری",
            base_price=45000,
            discount_price=45000
        ),
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="p2",
            title="شیر پرچرب کاله 1 لیتری",
            base_price=48000,
            discount_price=48000
        ),
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="p3",
            title="شیر پرچرب میهن 200 میلی لیتری",
            base_price=15000,
            discount_price=15000
        ),
    ]

    matched = match_sku(query, candidates)
    assert matched is not None
    assert matched.product_id == "p2"  # Exact match for full-fat 1L
