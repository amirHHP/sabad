"""
Comprehensive unit tests for Strict SKU Matching & Attribute Verification (Requirement R2).
Tests Persian unit suffixes, regex boundary fixes, verbal volumes, Persian decimal separators,
strict volume compatibility (including None bypass trap), and strict flavor exclusion.
"""

import pytest
from sabad.models.catalog import StoreItem
from sabad.models.grocery import ParsedGroceryItem
from sabad.normalizer.persian_digits import clean_persian_text, to_ascii_digits
from sabad.normalizer.parser import (
    extract_volume_weight,
    parse_single_item,
    parse_grocery_input,
)
from sabad.normalizer.matcher import (
    extract_volume_from_title,
    is_volume_compatible,
    is_flavor_compatible,
    is_product_type_compatible,
    is_fat_compatible,
    match_sku,
)


# ==============================================================================
# 1. Volume & Weight Extraction across Persian Unit Suffixes and Verbal Numbers
# ==============================================================================


@pytest.mark.parametrize(
    "phrase,expected_vol,expected_unit",
    [
        ("۱ کیلوگرمی", 1.0, "کیلوگرم"),
        ("۴ لیتری", 4.0, "لیتر"),
        ("۳۵۰ گرمی", 350.0, "گرم"),
        ("۹۵۵ میلی‌لیتر", 955.0, "میلی‌لیتر"),
        ("۹۵۵ میلی لیتر", 955.0, "میلی‌لیتر"),
        ("۹۵۵ میلی‌لیتری", 955.0, "میلی‌لیتر"),
        ("۹۵۵ میلی لیتری", 955.0, "میلی‌لیتر"),
        ("۱/۵ لیتری", 1.5, "لیتر"),
        ("۱٫۵ لیتری", 1.5, "لیتر"),
        ("نیم کیلو", 0.5, "کیلوگرم"),
        ("یک و نیم لیتری", 1.5, "لیتر"),
        ("یک و نیم لیتر", 1.5, "لیتر"),
        ("یک و نیم کیلو", 1.5, "کیلوگرم"),
        ("نیم لیتری", 0.5, "لیتر"),
        ("نیم لیتر", 0.5, "لیتر"),
        ("دو کیلو", 2.0, "کیلوگرم"),
        ("۲ کیلوگرمی", 2.0, "کیلوگرم"),
        ("۵۰۰ گرمی", 500.0, "گرم"),
        ("۲۵۰ سی‌سی", 250.0, "میلی‌لیتر"),
        ("۲۵۰ سی سی", 250.0, "میلی‌لیتر"),
    ],
)
def test_extract_volume_weight_parser(phrase, expected_vol, expected_unit):
    """Verifies that the parser extracts exact volume and unit from various Persian expressions."""
    vol, unit, rem = extract_volume_weight(phrase)
    assert vol == expected_vol, f"Parser failed volume on '{phrase}': got {vol}, expected {expected_vol}"
    assert unit == expected_unit, f"Parser failed unit on '{phrase}': got {unit}, expected {expected_unit}"


@pytest.mark.parametrize(
    "title,expected_vol,expected_unit",
    [
        ("مایع ظرفشویی ۱ کیلوگرمی پریل", 1.0, "کیلوگرم"),
        ("مایع ظرفشویی ۴ لیتری پریل", 4.0, "لیتر"),
        ("پنیر سفید ۳۵۰ گرمی ویلی", 350.0, "گرم"),
        ("شیر کم چرب ۹۵۵ میلی‌لیتر پاک", 955.0, "میلی‌لیتر"),
        ("شیر بطری ۹۵۵ میلی‌لیتری پگاه", 955.0, "میلی‌لیتر"),
        ("روغن سرخ کردنی ۱/۵ لیتری اویلا", 1.5, "لیتر"),
        ("روغن پخت و پز ۱٫۵ لیتری بهار", 1.5, "لیتر"),
        ("گوشت چرخ کرده نیم کیلو مهیا", 0.5, "کیلوگرم"),
        ("دوغ نعنایی یک و نیم لیتری عالیس", 1.5, "لیتر"),
        ("شیر پاکتی ۲۰۰ میلی لیتری میهن", 200.0, "میلی‌لیتر"),
    ],
)
def test_extract_volume_from_catalog_title(title, expected_vol, expected_unit):
    """Verifies that matcher extracts exact volume and unit from store catalog product titles."""
    vol, unit = extract_volume_from_title(title)
    assert vol == expected_vol, f"Matcher failed volume on '{title}': got {vol}, expected {expected_vol}"
    assert unit == expected_unit, f"Matcher failed unit on '{title}': got {unit}, expected {expected_unit}"


def test_parse_single_item_with_compound_suffixes():
    """Verifies that full items with compound suffixes and verbal numbers parse into ParsedGroceryItem correctly."""
    item1 = parse_single_item("شیر کم چرب ۹۵۵ میلی‌لیتری پاک")
    assert item1.name == "شیر"
    assert item1.brand == "پاک"
    assert item1.volume_weight == 955.0
    assert item1.unit == "میلی‌لیتر"
    assert item1.fat_percentage == 1.5
    assert item1.quantity == 1

    item2 = parse_single_item("دو تا مایع ظرفشویی پریل ۴ لیتری")
    assert item2.name == "مایع ظرفشویی"
    assert item2.brand == "پریل"
    assert item2.volume_weight == 4.0
    assert item2.unit == "لیتر"
    assert item2.quantity == 2

    item3 = parse_single_item("یه پنیر ویلی ۳۵۰ گرمی")
    assert item3.name == "پنیر"
    assert item3.brand == "ویلی"
    assert item3.volume_weight == 350.0
    assert item3.unit == "گرم"
    assert item3.quantity == 1

    item4 = parse_single_item("روغن مایع ۱/۵ لیتری اویلا")
    assert item4.name == "روغن مایع"
    assert item4.brand == "اویلا"
    assert item4.volume_weight == 1.5
    assert item4.unit == "لیتر"
    assert item4.quantity == 1


# ==============================================================================
# 2. Decimal Separators in Persian Digits (Slash / and Momayyez ٫)
# ==============================================================================


def test_persian_decimal_conversion():
    """Verifies Persian slash and momayyez are properly converted to ASCII dots in numbers."""
    assert to_ascii_digits("۱/۵") == "1.5"
    assert to_ascii_digits("۱٫۵") == "1.5"
    assert to_ascii_digits("۲/۷۵") == "2.75"
    assert clean_persian_text("۱/۵ لیتری") == "1.5 لیتری"
    assert clean_persian_text("شیر ۱٫۵ درصد چربی") == "شیر 1.5 درصد چربی"


# ==============================================================================
# 3. Strict Volume Verification & Exclusion of Incompatible Sizes (e.g. 4L vs 1kg)
# ==============================================================================


def test_volume_compatibility_4l_dishwashing_liquid():
    """Matching 4L dishwashing liquid strictly excludes 1kg and 1L variants."""
    assert is_volume_compatible(4.0, "لیتر", "مایع ظرفشویی ۱ کیلوگرمی پریل") is False
    assert is_volume_compatible(4.0, "لیتر", "مایع ظرفشویی ۱ لیتری پریل") is False
    assert is_volume_compatible(4.0, "لیتر", "مایع ظرفشویی ۷۵۰ گرمی پریل") is False
    assert is_volume_compatible(4.0, "لیتر", "مایع ظرفشویی ۴ لیتری پریل") is True
    assert is_volume_compatible(4.0, "لیتر", "مایع ظرفشویی پریل ۴ لیتری لیمویی") is True


def test_volume_compatibility_tolerance_and_none_guard():
    """Verifies 15% tolerance and None bypass protection."""
    # 955ml is within 15% of 1L
    assert is_volume_compatible(1.0, "لیتر", "شیر کم چرب ۹۵۵ میلی‌لیتر پاک") is True
    assert is_volume_compatible(1.0, "لیتر", "شیر پاکتی ۹۴۵ میلی لیتر پگاه") is True

    # 200ml is outside 15% tolerance of 1L
    assert is_volume_compatible(1.0, "لیتر", "شیر ۲۰۰ میلی لیتری میهن") is False

    # 350g cheese vs 1kg cheese
    assert is_volume_compatible(350.0, "گرم", "پنیر سفید ۱ کیلوگرمی کاله") is False
    assert is_volume_compatible(350.0, "گرم", "پنیر سفید ۳۵۰ گرمی ویلی") is True


def test_match_sku_4l_dishwashing_liquid_excludes_1kg_and_1l():
    """End-to-end test: query for 4L dishwashing liquid correctly pairs with 4L and strictly rejects 1kg and 1L."""
    query = ParsedGroceryItem(
        raw_text="مایع ظرفشویی پریل ۴ لیتری",
        name="مایع ظرفشویی",
        brand="پریل",
        quantity=1,
        volume_weight=4.0,
        unit="لیتر",
    )

    candidates = [
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="1kg",
            title="مایع ظرفشویی ۱ کیلوگرمی پریل",
            base_price=50000,
            discount_price=50000,
        ),
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="1l",
            title="مایع ظرفشویی ۱ لیتری پریل",
            base_price=52000,
            discount_price=52000,
        ),
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="4l",
            title="مایع ظرفشویی ۴ لیتری پریل",
            base_price=180000,
            discount_price=180000,
        ),
    ]

    matched = match_sku(query, candidates)
    assert matched is not None
    assert matched.product_id == "4l"
    assert "۴ لیتری" in matched.title

    # When 4L is absent, must return None instead of falling back to 1kg or 1L
    matched_without_4l = match_sku(query, candidates[:2])
    assert matched_without_4l is None


# ==============================================================================
# 4. Strict Flavor Exclusion (Plain Milk vs Flavored Milk)
# ==============================================================================


def test_flavor_compatibility_plain_milk_rejects_all_flavors():
    """Matching plain milk strictly rejects candidate titles with flavors."""
    plain_queries = [
        "شیر",
        "شیر پرچرب",
        "شیر کم چرب",
        "شیر بطری",
        "شیر پاستوریزه",
        "شیر پرچرب کاله یک لیتری",
    ]

    flavored_titles = [
        "شیر طالبی کاله ۱ لیتری",
        "شیر کاکائو پرچرب کاله ۱ لیتری",
        "شیر موز کاله ۱ لیتری",
        "شیر توت فرنگی پگاه ۱ لیتری",
        "شیر قهوه میهن ۱ لیتری",
        "شیر وانیل پاک ۱ لیتری",
        "شیر نارگیل دومینو ۱ لیتری",
        "شیر خرما کاله ۱ لیتری",
        "شیر عسل پگاه ۱ لیتری",
        "شیر پسته میهن ۱ لیتری",
    ]

    for q in plain_queries:
        for title in flavored_titles:
            assert is_flavor_compatible(q, title) is False, f"Plain query '{q}' should reject flavored title '{title}'"


def test_flavor_compatibility_plain_milk_accepts_plain_variants():
    """Plain milk queries accept unflavored milk varieties."""
    plain_titles = [
        "شیر پرچرب کاله ۱ لیتری",
        "شیر کم چرب کاله ۱ لیتری",
        "شیر پاستوریزه بطری پگاه",
        "شیر پاکتی پاک ۱ لیتری",
    ]
    for title in plain_titles:
        assert is_flavor_compatible("شیر پرچرب کاله یک لیتری", title) is True


def test_match_sku_plain_milk_excludes_flavored_varieties():
    """End-to-end test: query for plain milk returns None against flavored candidates."""
    query = ParsedGroceryItem(
        raw_text="شیر پرچرب کاله یک لیتری",
        name="شیر",
        brand="کاله",
        quantity=1,
        volume_weight=1.0,
        unit="لیتر",
        fat_percentage=3.0,
    )

    flavored_candidates = [
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="talebi",
            title="شیر طالبی کاله ۱ لیتری",
            base_price=45000,
            discount_price=45000,
        ),
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="kakao",
            title="شیر کاکائو پرچرب کاله ۱ لیتری",
            base_price=45000,
            discount_price=45000,
        ),
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="moz",
            title="شیر موز کاله ۱ لیتری",
            base_price=45000,
            discount_price=45000,
        ),
    ]

    matched = match_sku(query, flavored_candidates)
    assert matched is None, f"Plain milk must not match flavored milk, but matched: {matched}"

    # Adding a plain milk item should match it immediately
    plain_item = StoreItem(
        platform="snapp_market",
        store_id="s1",
        product_id="plain_milk",
        title="شیر پرچرب کاله ۱ لیتری",
        base_price=48000,
        discount_price=48000,
    )
    matched_plain = match_sku(query, flavored_candidates + [plain_item])
    assert matched_plain is not None
    assert matched_plain.product_id == "plain_milk"


def test_match_sku_flavored_milk_matching():
    """Verifies that requesting a flavored milk (e.g. شیر کاکائو) pairs only with cocoa milk."""
    query = parse_single_item("شیر کاکائو کاله یک لیتری")
    candidates = [
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="plain",
            title="شیر پرچرب کاله ۱ لیتری",
            base_price=48000,
            discount_price=48000,
        ),
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="talebi",
            title="شیر طالبی کاله ۱ لیتری",
            base_price=45000,
            discount_price=45000,
        ),
        StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="kakao",
            title="شیر کاکائو کاله ۱ لیتری",
            base_price=45000,
            discount_price=45000,
        ),
    ]
    matched = match_sku(query, candidates)
    assert matched is not None
    assert matched.product_id == "kakao"


# ==============================================================================
# 5. Product Type Distinction (Dishwashing Liquid vs Other Detergents)
# ==============================================================================


def test_product_type_compatibility():
    """Dishwashing liquid must not match hand soap or laundry detergent."""
    assert is_product_type_compatible("مایع ظرفشویی", "مایع ظرفشویی پریل ۴ لیتری") is True
    assert is_product_type_compatible("مایع ظرفشویی", "مایع دستشویی اکتیو ۴ لیتری") is False
    assert is_product_type_compatible("مایع ظرفشویی", "مایع لباسشویی پرسیل ۴ لیتری") is False
    assert is_product_type_compatible("مایع ظرفشویی", "قرص ماشین ظرفشویی پریل") is False


# ==============================================================================
# 6. Pack Size / Roll Count & Tissue Type Distinction
# ==============================================================================


def test_pack_count_and_milliliter_extraction():
    """Extracts pack counts (عددی, قلو, رول) and standalone milli units from titles."""
    assert extract_volume_from_title("دستمال توالت 4 لایه پاپیا 8 عددی") == (8.0, "عدد")
    assert extract_volume_from_title("دستمال توالت پاپیا ۴ قلو") == (4.0, "عدد")
    assert extract_volume_from_title("دستمال توالت پاپیا چهار لایه 2 رول") == (2.0, "عدد")
    assert extract_volume_from_title("مایع دستشویی اکتیو ۴۰۰ میلی") == (400.0, "میلی‌لیتر")
    assert extract_volume_from_title("مایع دستشویی اکتیو ۳/۷ کیلویی") == (3.7, "کیلوگرم")


def test_tissue_product_type_compatibility():
    """Toilet paper must not match facial tissue or paper towel."""
    assert is_product_type_compatible("دستمال توالت", "دستمال توالت 4 لایه پاپیا 8 عددی") is True
    assert is_product_type_compatible("دستمال توالت", "دستمال کاغذی سافت پک ۲۵۰ برگ") is False
    assert is_product_type_compatible("دستمال توالت", "دستمال حوله ای ۴ لایه پاپیا") is False


def test_pack_and_volume_incompatibility_rejection():
    """8-pack toilet paper rejects 2-pack; 3.7kg soap rejects 400ml."""
    assert is_volume_compatible(8.0, "عدد", "دستمال توالت پاپیا مدل رولی بسته 2 عددی") is False
    assert is_volume_compatible(8.0, "عدد", "دستمال توالت پاپیا چهار لایه 2 رول") is False
    assert is_volume_compatible(8.0, "عدد", "دستمال توالت 4 لایه پاپیا 8 عددی") is True

    assert is_volume_compatible(3.7, "کیلوگرم", "مایع دستشویی اکتیو ۴۰۰ میلی") is False
    assert is_volume_compatible(3.7, "کیلوگرم", "مایع دستشویی اکتیو مدل Moonlight Path وزن 3750 گرم") is True
    assert is_volume_compatible(400.0, "میلی‌لیتر", "مایع دستشویی اکتیو مدل Moonlight Path وزن 3750 گرم") is False
