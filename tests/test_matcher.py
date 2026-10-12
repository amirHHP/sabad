"""
Unit tests for sabad.normalizer.matcher module.
Tests attribute filters, fuzzy ranking, volume compatibility, flavor compatibility, and product type checks.
"""

import pytest
from sabad.models.catalog import StoreItem
from sabad.models.grocery import ParsedGroceryItem
from sabad.normalizer.matcher import (
    extract_volume_from_title,
    is_fat_compatible,
    is_volume_compatible,
    is_flavor_compatible,
    is_product_type_compatible,
    match_sku,
)


def test_extract_volume_from_title_units():
    assert extract_volume_from_title("مایع ظرفشویی پریل ۴ لیتری") == (4.0, "لیتر")
    assert extract_volume_from_title("مایع ظرفشویی پریل ۱ کیلوگرمی") == (1.0, "کیلوگرم")
    assert extract_volume_from_title("پنیر سفید ۳۵۰ گرمی ویلی") == (350.0, "گرم")
    assert extract_volume_from_title("شیر کم چرب ۹۵۵ میلی‌لیتر پاک") == (955.0, "میلی‌لیتر")
    assert extract_volume_from_title("شیر بطری ۹۵۵ میلی‌لیتری پگاه") == (955.0, "میلی‌لیتر")
    assert extract_volume_from_title("روغن سرخ کردنی ۱/۵ لیتری بهار") == (1.5, "لیتر")
    assert extract_volume_from_title("روغن پخت و پز ۱٫۵ لیتری اویلا") == (1.5, "لیتر")
    assert extract_volume_from_title("شیر نیم لیتری میهن") == (0.5, "لیتر")
    assert extract_volume_from_title("گوشت چرخ کرده نیم کیلو مهیا") == (0.5, "کیلوگرم")


def test_is_fat_compatible():
    assert is_fat_compatible(None, "شیر پرچرب کاله") is True
    assert is_fat_compatible(3.0, "شیر پرچرب کاله") is True
    assert is_fat_compatible(3.0, "شیر کم چرب پگاه") is False
    assert is_fat_compatible(1.5, "شیر کم چرب پگاه") is True
    assert is_fat_compatible(1.5, "شیر پرچرب کاله") is False


def test_is_flavor_compatible():
    # Plain milk
    assert is_flavor_compatible("شیر", "شیر پرچرب کاله") is True
    assert is_flavor_compatible("شیر", "شیر طالبی کاله") is False
    assert is_flavor_compatible("شیر پرچرب", "شیر کاکائو کاله") is False
    assert is_flavor_compatible("شیر کم چرب", "شیر موز کاله") is False

    # Flavored milk
    assert is_flavor_compatible("شیر کاکائو", "شیر کاکائو کاله") is True
    assert is_flavor_compatible("شیر کاکائو", "شیر طالبی کاله") is False
    assert is_flavor_compatible("شیر موز", "شیر موز پگاه") is True
    assert is_flavor_compatible("شیر موز", "شیر قهوه پگاه") is False


def test_is_product_type_compatible():
    assert is_product_type_compatible("مایع ظرفشویی", "مایع ظرفشویی پریل ۴ لیتری") is True
    assert is_product_type_compatible("مایع ظرفشویی", "مایع دستشویی صحت ۴ لیتری") is False
    assert is_product_type_compatible("مایع ظرفشویی", "مایع لباسشویی تاژ ۴ لیتری") is False
    assert is_product_type_compatible("مایع دستشویی", "مایع دستشویی صحت ۴ لیتری") is True
    assert is_product_type_compatible("مایع دستشویی", "مایع ظرفشویی پریل ۴ لیتری") is False


def test_is_volume_compatible():
    assert is_volume_compatible(None, None, "مایع ظرفشویی پریل") is True
    assert is_volume_compatible(4.0, "لیتر", "مایع ظرفشویی پریل ۴ لیتری") is True
    assert is_volume_compatible(4.0, "لیتر", "مایع ظرفشویی پریل ۱ کیلوگرمی") is False
    assert is_volume_compatible(4.0, "لیتر", "مایع ظرفشویی پریل ۱ لیتری") is False
    assert is_volume_compatible(1.0, "لیتر", "شیر کم چرب ۹۵۵ میلی‌لیتر پاک") is True
    assert is_volume_compatible(1.0, "لیتر", "شیر ۲۰۰ میلی لیتری میهن") is False


def test_match_sku_ranking_and_filters():
    query = ParsedGroceryItem(
        raw_text="مایع ظرفشویی پریل ۴ لیتری",
        name="مایع ظرفشویی",
        brand="پریل",
        quantity=1,
        volume_weight=4.0,
        unit="لیتر",
    )
    cands = [
        StoreItem(platform="s1", store_id="1", product_id="c1", title="مایع دستشویی پریل ۴ لیتری", base_price=100, discount_price=100),
        StoreItem(platform="s1", store_id="1", product_id="c2", title="مایع ظرفشویی پریل ۱ کیلوگرمی", base_price=100, discount_price=100),
        StoreItem(platform="s1", store_id="1", product_id="c3", title="مایع ظرفشویی پریل ۴ لیتری", base_price=100, discount_price=100),
    ]
    matched = match_sku(query, cands)
    assert matched is not None
    assert matched.product_id == "c3"
