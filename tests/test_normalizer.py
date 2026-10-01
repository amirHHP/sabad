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
