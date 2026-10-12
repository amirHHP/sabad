"""
Empirical Adversarial Stress Harness for Sabad.
Covers:
1. Currency normalization under extreme/adversarial inputs (R1).
2. Digikala Jet out-of-stock 1-Toman hardening.
3. Okala undiscounted items exception immunity.
4. Extreme delivery fees & missing MOV resiliency.
5. Persian unit parsing under adversarial permutations & ZWNJ (R2).
6. Adversarial volume matching (4L dishwashing liquid vs 1kg, 1L, 500ml, 4000ml, 4kg).
7. Adversarial flavor matching (plain milk vs 20+ flavored varieties).
"""

import math
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
from sabad.models.catalog import StoreItem
from sabad.models.grocery import ParsedGroceryItem
from sabad.normalizer.parser import (
    extract_volume_weight,
    parse_single_item,
)
from sabad.normalizer.matcher import (
    extract_volume_from_title,
    is_volume_compatible,
    is_flavor_compatible,
    match_sku,
    DAIRY_FLAVORS,
)
from sabad.normalizer.persian_digits import clean_persian_text, to_ascii_digits


# ==============================================================================
# 1. Currency Normalization under Extreme & Adversarial Inputs (R1)
# ==============================================================================

class TestCurrencyNormalizationAdversarial:
    """Stress tests BaseStoreAdapter.rials_to_tomans across adversarial edge cases."""

    @pytest.mark.parametrize(
        "raw_input,fallback,expected",
        [
            # Negative inputs
            (-1, 0.0, 0.0),
            (-100, 25.0, 25.0),
            (-1000000, 0.0, 0.0),
            (-1e10, 50.0, 50.0),
            ("-5000", 0.0, 0.0),
            # Zero inputs
            (0, 0.0, 0.0),
            (0.0, 10.0, 10.0),
            ("0", 0.0, 0.0),
            ("0.0", 15.0, 15.0),
            # None inputs
            (None, 0.0, 0.0),
            (None, 25000.0, 25000.0),
            # Non-numeric strings
            ("abc", 0.0, 0.0),
            ("N/A", 100.0, 100.0),
            ("تومان", 0.0, 0.0),
            ("", 0.0, 0.0),
            ("   ", 0.0, 0.0),
            ("123abc", 0.0, 0.0),
            ("None", 0.0, 0.0),
            ("null", 0.0, 0.0),
            # Formatting with whitespace
            (" 1580000 \n", 0.0, 158000.0),
            # Float representations
            ("1580000.0", 0.0, 158000.0),
            # Small positive values
            (1, 0.0, 0.1),
            (9, 0.0, 0.9),
            (10, 0.0, 1.0),
            # Standard positive values
            (1580000, 0.0, 158000.0),
            (2290000, 0.0, 229000.0),
            (10000000, 0.0, 1000000.0),
            # Rounding to 1 decimal place
            (123456, 0.0, 12345.6),
            (123456.78, 0.0, 12345.7),
        ],
    )
    def test_rials_to_tomans_extreme_inputs(self, raw_input, fallback, expected):
        res = BaseStoreAdapter.rials_to_tomans(raw_input, fallback=fallback)
        assert res == expected

    def test_rials_to_tomans_non_primitive_types(self):
        """Objects, lists, and dicts must gracefully return fallback."""
        assert BaseStoreAdapter.rials_to_tomans([], fallback=99.0) == 99.0
        assert BaseStoreAdapter.rials_to_tomans({}, fallback=99.0) == 99.0
        assert BaseStoreAdapter.rials_to_tomans(object(), fallback=99.0) == 99.0

    def test_rials_to_tomans_nan_inf(self):
        """Special floating point values."""
        assert BaseStoreAdapter.rials_to_tomans(float("nan"), fallback=42.0) == 42.0
        assert BaseStoreAdapter.rials_to_tomans(float("-inf"), fallback=42.0) == 42.0
        # Positive inf
        assert math.isinf(BaseStoreAdapter.rials_to_tomans(float("inf")))


# ==============================================================================
# 2. Digikala Jet Out-of-Stock 1-Toman Hardening
# ==============================================================================

class TestDigikalaJetOutOfStockHardening:
    """
    Verifies that out-of-stock items in Digikala Jet NEVER produce 1-Toman products
    under any permutation of price structure or missing values.
    """

    @pytest.mark.asyncio
    async def test_search_out_of_stock_never_produces_1_toman_item(self):
        permutations = [
            {"id": 1, "title": "P1-NonePrice", "price": None, "stock": {"has_stock": False}},
            {"id": 2, "title": "P2-EmptyPriceDict", "price": {}, "stock": {"has_stock": False}},
            {"id": 3, "title": "P3-NoneValues", "price": {"price": None, "discount": None}, "stock": {"has_stock": False}},
            {"id": 4, "title": "P4-ZeroPrice", "price": {"price": 0, "discount": 0}, "stock": {"has_stock": False}},
            {"id": 5, "title": "P5-NegativePrice", "price": {"price": -5000, "discount": 0}, "stock": {"has_stock": False}},
            {"id": 6, "title": "P6-Shelf10Rials", "price": {"price": 10, "discount": 0}, "stock": {"has_stock": False}},
            {"id": 7, "title": "P7-Net10Rials", "price": {"price": 1000, "discount": 990}, "stock": {"has_stock": False}},
            {"id": 8, "title": "P8-100PctDiscount", "price": {"price": 500000, "discount": 500000}, "stock": {"has_stock": False}},
            {"id": 9, "title": "P9-StringPrice0", "price": "0", "stock": {"has_stock": False}},
            {"id": 10, "title": "P10-StringNone", "price": "None", "stock": {"has_stock": False}},
            {"id": 11, "title": "P11-IntPrice", "price": 10, "stock": {"has_stock": False}},
            {"id": 12, "title": "P12-StockNone", "price": None, "stock": None},
            {"id": 13, "title": "P13-StockHasStockNone", "price": None, "stock": {"has_stock": None}},
            {"id": 14, "title": "P14-StockBoolFalse", "price": None, "stock": False},
            {"id": 15, "title": "P15-StockIntZero", "price": None, "stock": 0},
            {"id": 16, "title": "P16-TopLevelHasStockZero", "price": None, "has_stock": 0},
            {"id": 17, "title": "P17-CompletelyEmpty"},
            {"id": 18, "title": "P18-StockDictEmpty", "price": None, "stock": {}},
        ]

        mock_resp = httpx.Response(200, json={"data": {"result": permutations}})
        adapter = DigikalaJetAdapter()
        with patch.object(adapter.client, "get", new=AsyncMock(return_value=mock_resp)):
            items = await adapter.search("test", 35.7, 51.4)

        assert len(items) == len(permutations)
        for it in items:
            # Must strictly be marked out of stock
            assert it.is_in_stock is False, f"Item {it.title} falsely marked in stock!"
            # If price was missing or zero, discount_price must be 0.0 (NEVER 1.0)
            if it.base_price <= 0:
                assert it.discount_price == 0.0, f"Item {it.title} produced 1-Toman price from missing price!"

    @pytest.mark.asyncio
    async def test_flash_deals_out_of_stock_hardening(self):
        """Verifies flash deals endpoint also guards against out-of-stock / missing price items."""
        main_page_payload = {
            "data": {
                "components": [
                    {
                        "component_type": "amazing-widget-on-other-lines",
                        "data": {"api": {"url": "/v3/amazing-products/"}},
                    }
                ]
            }
        }
        prods_payload = {
            "data": {
                "products": [
                    {"id": 901, "title": "Flash OOS None Price", "price": None, "stock": {"has_stock": False}},
                    {"id": 902, "title": "Flash OOS Zero Price", "price": {"price": 0}, "stock": False},
                    {"id": 903, "title": "Flash In-Stock Valid", "price": {"price": 500000, "discount": 100000, "discount_percentage": 20}, "stock": {"has_stock": True}},
                ]
            }
        }

        adapter = DigikalaJetAdapter()
        with patch.object(adapter.client, "get", new=AsyncMock(side_effect=[
            httpx.Response(200, json=main_page_payload),
            httpx.Response(200, json=prods_payload),
        ])):
            deals = await adapter.get_flash_deals(35.7, 51.4)

        assert len(deals) == 3
        # Deals 1 & 2 must be out of stock and have 0.0 price
        assert deals[0].is_in_stock is False
        assert deals[0].discount_price == 0.0
        assert deals[1].is_in_stock is False
        assert deals[1].discount_price == 0.0

        # Deal 3 is in stock
        assert deals[2].is_in_stock is True
        assert deals[2].base_price == 50000.0
        assert deals[2].discount_price == 40000.0


# ==============================================================================
# 3. Okala Undiscounted Items Exception Immunity
# ==============================================================================

class TestOkalaUndiscountedImmunity:
    """Verifies that Okala undiscounted items never raise exceptions under any type permutations."""

    @pytest.mark.asyncio
    async def test_search_undiscounted_permutations_no_exceptions(self):
        permutations = [
            {"id": 1, "name": "OK1-NoneDiscount", "price": 850000.0, "discountPercent": None, "okPrice": None, "quantity": 10},
            {"id": 2, "name": "OK2-ZeroDiscount", "price": 850000.0, "discountPercent": 0, "okPrice": None, "quantity": 10},
            {"id": 3, "name": "OK3-StringZero", "price": 850000.0, "discountPercent": "0", "okPrice": None, "quantity": 10},
            {"id": 4, "name": "OK4-EmptyString", "price": 850000.0, "discountPercent": "", "okPrice": None, "quantity": 10},
            {"id": 5, "name": "OK5-StringNone", "price": 850000.0, "discountPercent": "None", "okPrice": None, "quantity": 10},
            {"id": 6, "name": "OK6-OkPriceEqualBase", "price": 850000.0, "discountPercent": None, "okPrice": 850000.0, "quantity": 10},
            {"id": 7, "name": "OK7-OkPriceZero", "price": 850000.0, "discountPercent": None, "okPrice": 0, "quantity": 10},
            {"id": 8, "name": "OK8-OkPriceNegative", "price": 850000.0, "discountPercent": None, "okPrice": -100, "quantity": 10},
            {"id": 9, "name": "OK9-OkPriceInvalidString", "price": 850000.0, "discountPercent": None, "okPrice": "N/A", "quantity": 10},
            {"id": 10, "name": "OK10-PriceNone", "price": None, "discountPercent": None, "okPrice": None, "quantity": 0},
            {"id": 11, "name": "OK11-PriceZero", "price": 0, "discountPercent": None, "okPrice": None, "quantity": None},
            {"id": 12, "name": "OK12-PriceInvalidString", "price": "invalid", "discountPercent": None, "okPrice": None, "quantity": "invalid"},
        ]

        mock_resp = httpx.Response(200, json={"entities": permutations})
        adapter = OkalaAdapter()
        with patch.object(adapter, "_ensure_store_id", new=AsyncMock(return_value="2319")), \
             patch.object(adapter.client, "get", new=AsyncMock(return_value=mock_resp)):
            items = await adapter.search("test", 35.7, 51.4)

        assert len(items) == len(permutations)
        # Undiscounted items (1-9) should have base_price == discount_price == 85000.0
        for it in items[:9]:
            assert it.base_price == 85000.0
            assert it.discount_price == 85000.0
            assert it.discount_percent == 0.0
            assert it.is_in_stock is True

        # Items 10-12 are invalid/missing prices -> out of stock with 0.0 price
        for it in items[9:]:
            assert it.is_in_stock is False
            assert it.base_price == 0.0
            assert it.discount_price == 0.0


# ==============================================================================
# 4. Delivery Fees & MOV Adversarial Inputs
# ==============================================================================

class TestDeliveryFeeAndMOVResiliency:
    """Verifies that extreme delivery fees or missing MOV values gracefully fall back without throwing."""

    @pytest.mark.asyncio
    async def test_snappmarket_delivery_and_mov_resiliency(self):
        cases = [
            {"data": {"finalResult": [{"data": {"id": 1, "minimumOrderValue": None, "deliveryFee": None, "couponMinBasket": None}}]}},
            {"data": {"finalResult": [{"data": {"id": 2, "minimumOrderValue": 0, "deliveryFee": 0, "couponMinBasket": 0}}]}},
            {"data": {"finalResult": []}},
        ]
        adapter = SnappMarketAdapter()
        for c in cases:
            with patch.object(adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=c))):
                info = await adapter.get_store_info(35.7, 51.4)
                assert info is not None
                assert info.minimum_order_value > 0
                assert len(info.delivery_tiers) >= 1

    @pytest.mark.asyncio
    async def test_digikala_jet_delivery_and_mov_resiliency(self):
        cases = [
            {"data": {"result": [{"id": 1, "delivery": None}]}},
            {"data": {"result": [{"id": 2, "delivery": {"cost": None, "free_shipping_price": None}}]}},
            {"data": {"result": [{"id": 3, "delivery": {"cost": -100, "free_shipping_price": 0}}]}},
            {"data": {"result": []}},
        ]
        adapter = DigikalaJetAdapter()
        for c in cases:
            with patch.object(adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=c))):
                info = await adapter.get_store_info(35.7, 51.4)
                assert info is not None
                assert info.minimum_order_value > 0
                assert len(info.delivery_tiers) >= 1

    @pytest.mark.asyncio
    async def test_okala_delivery_and_mov_resiliency(self):
        cases = [
            ({"data": {"stores": []}}, {"data": {}}),
            ({"data": {"stores": [{"storeId": 10}]}}, {"data": {"minimumOrder": None, "cost": None}}),
            ({"data": {"stores": [{"storeId": 10}]}}, {"data": {"minimumOrder": 0, "cost": 0}}),
            ({"data": {"stores": [{"storeId": 10}]}}, None),
        ]
        adapter = OkalaAdapter()
        for sc, dc in cases:
            side_effects = [httpx.Response(200, json=sc)]
            if dc is not None:
                side_effects.append(httpx.Response(200, json=dc))
            else:
                side_effects.append(httpx.Response(500, content=b"Server Error"))

            with patch.object(adapter.client, "get", new=AsyncMock(side_effect=side_effects)):
                info = await adapter.get_store_info(35.7, 51.4)
                assert info is not None
                assert info.minimum_order_value > 0
                assert len(info.delivery_tiers) >= 1


# ==============================================================================
# 5. Persian Unit Parsing under Adversarial Permutations (R2)
# ==============================================================================

class TestPersianUnitParsingAdversarial:
    """Tests Persian unit extraction under exact specified permutations and boundary challenges."""

    @pytest.mark.parametrize(
        "phrase,expected_vol,expected_unit",
        [
            ("۱ کیلوگرمی", 1.0, "کیلوگرم"),
            ("۴ لیتری", 4.0, "لیتر"),
            ("۳۵۰ گرمی", 350.0, "گرم"),
            ("۹۵۵ میلی‌لیتر", 955.0, "میلی‌لیتر"),
            ("۹۵۵ میلی‌لیتری", 955.0, "میلی‌لیتر"),
            ("۱/۵ لیتری", 1.5, "لیتر"),
            ("نیم کیلو", 0.5, "کیلوگرم"),
        ],
    )
    def test_specified_core_phrases(self, phrase, expected_vol, expected_unit):
        vol, unit, rem = extract_volume_weight(phrase)
        assert vol == expected_vol
        assert unit == expected_unit

    @pytest.mark.parametrize(
        "phrase,expected_vol,expected_unit",
        [
            # Complex ZWNJ variations
            ("۱\u200cکیلوگرمی", 1.0, "کیلوگرم"),
            ("۱ کیلو\u200cگرمی", 1.0, "کیلوگرم"),
            ("۴\u200cلیتری", 4.0, "لیتر"),
            ("۳۵۰\u200cگرمی", 350.0, "گرم"),
            ("۹۵۵\u200cمیلی\u200cلیتر", 955.0, "میلی‌لیتر"),
            ("۹۵۵\u200cمیلی\u200cلیتری", 955.0, "میلی‌لیتر"),
            ("۱/۵\u200cلیتری", 1.5, "لیتر"),
            ("۱٫۵\u200cلیتری", 1.5, "لیتر"),
            ("۱.۵\u200cلیتری", 1.5, "لیتر"),
            ("نیم\u200cکیلو", 0.5, "کیلوگرم"),
            # No-space variations
            ("۴لیتری", 4.0, "لیتر"),
            ("۳۵۰گرمی", 350.0, "گرم"),
            ("۱کیلوگرمی", 1.0, "کیلوگرم"),
            # Persian decimal separator (momayyez ٫)
            ("۱٫۵ لیتری", 1.5, "لیتر"),
            ("۲٫۵ کیلوگرمی", 2.5, "کیلوگرم"),
            # Arabic digits
            ("١ کیلوگرمی", 1.0, "کیلوگرم"),
            ("٤ لیتری", 4.0, "لیتر"),
            ("٣٥٠ گرمی", 350.0, "گرم"),
            ("٩٥٥ میلی‌لیتر", 955.0, "میلی‌لیتر"),
            ("١٫٥ لیتری", 1.5, "لیتر"),
            ("١/٥ لیتری", 1.5, "لیتر"),
            # Verbal compound expressions
            ("یک و نیم لیتری", 1.5, "لیتر"),
            ("یک و نیم کیلو", 1.5, "کیلوگرم"),
            ("دو و نیم لیتری", 2.5, "لیتر"),
            ("نیم لیتری", 0.5, "لیتر"),
            ("نیم لیتر", 0.5, "لیتر"),
        ],
    )
    def test_zwnj_and_arabic_digits_permutations(self, phrase, expected_vol, expected_unit):
        vol, unit, rem = extract_volume_weight(phrase)
        assert vol == expected_vol, f"Failed on '{phrase}': got {vol}, expected {expected_vol}"
        assert unit == expected_unit, f"Failed on '{phrase}': got {unit}, expected {expected_unit}"


# ==============================================================================
# 6. Adversarial Volume Matching (4L Dishwashing Liquid)
# ==============================================================================

class TestAdversarialVolumeMatching:
    """Tests volume matching of 4L dishwashing liquid against 1kg, 1L, 500ml, 4000ml, 4kg."""

    @pytest.mark.parametrize(
        "candidate_title,should_be_compatible",
        [
            ("مایع ظرفشویی ۱ کیلوگرمی پریل", False),
            ("مایع ظرفشویی پریل ۱ لیتری", False),
            ("مایع ظرفشویی پریل ۵۰۰ میلی لیتر", False),
            ("مایع ظرفشویی پریل ۷۵۰ گرمی", False),
            ("مایع ظرفشویی پریل ۲۰۰ میلی لیتر", False),
            ("مایع ظرفشویی پریل ۴۰۰ میلی لیتر", False),
            ("مایع ظرفشویی پریل ۴۰۰۰ میلی لیتر", True),     # 4000ml is exactly 4L
            ("مایع ظرفشویی پریل ۴ کیلوگرمی", True),       # 4kg detergent gallon (density ~1kg/L)
            ("مایع ظرفشویی پریل ۴ لیتری", True),          # Exact 4L match
            ("مایع ظرفشویی پریل ۳۷۵۰ میلی لیتر", True),   # 3.75L is within 15% tolerance of 4L
        ],
    )
    def test_4l_dishwashing_liquid_volume_compatibility(self, candidate_title, should_be_compatible):
        result = is_volume_compatible(4.0, "لیتر", candidate_title)
        assert result is should_be_compatible, (
            f"Compatibility check failed for candidate '{candidate_title}': "
            f"expected {should_be_compatible}, got {result}"
        )

    def test_match_sku_4l_dishwashing_liquid_strict_selection(self):
        """End-to-end SKU matching strictly pairs 4L query with compatible volume and excludes incompatible ones."""
        query = parse_single_item("مایع ظرفشویی پریل ۴ لیتری")
        assert query.volume_weight == 4.0
        assert query.unit == "لیتر"

        candidates = [
            StoreItem(
                platform="snapp_market",
                store_id="1",
                product_id="sku_1kg",
                title="مایع ظرفشویی ۱ کیلوگرمی پریل",
                base_price=55000,
                discount_price=55000,
            ),
            StoreItem(
                platform="snapp_market",
                store_id="1",
                product_id="sku_1l",
                title="مایع ظرفشویی پریل ۱ لیتری",
                base_price=58000,
                discount_price=58000,
            ),
            StoreItem(
                platform="snapp_market",
                store_id="1",
                product_id="sku_500ml",
                title="مایع ظرفشویی پریل ۵۰۰ میلی لیتر",
                base_price=30000,
                discount_price=30000,
            ),
            StoreItem(
                platform="snapp_market",
                store_id="1",
                product_id="sku_4l",
                title="مایع ظرفشویی پریل ۴ لیتری",
                base_price=210000,
                discount_price=210000,
            ),
        ]

        # 1. With 4L present: strictly matches 4L
        matched = match_sku(query, candidates)
        assert matched is not None
        assert matched.product_id == "sku_4l"

        # 2. Incompatible only (1kg, 1L, 500ml): must return None (NO fallback pairings!)
        incompatible_only = candidates[:3]
        matched_incompat = match_sku(query, incompatible_only)
        assert matched_incompat is None, f"Expected None for incompatible candidates, but got {matched_incompat}"


# ==============================================================================
# 7. Adversarial Flavor Matching (Plain Cow's Milk vs 20+ Flavors)
# ==============================================================================

class TestAdversarialFlavorMatching:
    """Stress tests flavor matching between plain cow's milk and 20+ flavored varieties."""

    PLAIN_QUERIES = [
        "شیر",
        "شیر پرچرب",
        "شیر کم چرب",
        "شیر بطری",
        "شیر پاستوریزه",
        "شیر پرچرب کاله یک لیتری",
        "شیر تازه گاو",
        "شیر پاکتی",
    ]

    FLAVORED_TITLES = [
        "شیر طالبی کاله ۱ لیتری",
        "شیر کاکائو پرچرب کاله ۱ لیتری",
        "شیر موز کاله ۱ لیتری",
        "شیر قهوه میهن ۱ لیتری",
        "شیر توت فرنگی پگاه ۱ لیتری",
        "شیر توت‌فرنگی پاک ۱ لیتری",
        "شیر پسته میهن ۱ لیتری",
        "شیر وانیل پاک ۱ لیتری",
        "شیر خرما کاله ۱ لیتری",
        "شیر عسل پگاه ۱ لیتری",
        "شیر نارگیل دومینو ۱ لیتری",
        "شیر شکلات چوپان ۱ لیتری",
        "شیر چاکلت کاله ۱ لیتری",
        "شیر فندق روزانه ۱ لیتری",
        "شیر بادام رامک ۱ لیتری",
        "شیر گردو دامداران ۱ لیتری",
        "شیر کارامل پاک ۱ لیتری",
        "شیر مالت بهنوش ۱ لیتری",
        "شیر زعفران هراز ۱ لیتری",
        "شیر انبه میهن ۱ لیتری",
        "شیر طعم دار کاله ۱ لیتری",
        "شیر طعم‌دار پگاه ۱ لیتری",
    ]

    def test_plain_milk_rejects_all_20_plus_flavors(self):
        """Every plain query must reject every flavored variety."""
        failures = []
        for q in self.PLAIN_QUERIES:
            for title in self.FLAVORED_TITLES:
                if is_flavor_compatible(q, title):
                    failures.append((q, title))

        assert len(failures) == 0, f"Plain milk incorrectly matched flavored titles: {failures}"

    def test_plain_milk_accepts_unflavored_variants(self):
        """Plain queries must accept legitimate unflavored milk variants."""
        plain_titles = [
            "شیر پرچرب کاله ۱ لیتری",
            "شیر کم چرب پگاه ۱ لیتری",
            "شیر نیم چرب میهن ۱ لیتری",
            "شیر پاستوریزه بطری پاک ۱ لیتری",
            "شیر استریل پاکتی روزانه ۱ لیتری",
            "شیر سنتی گاومیش ۱ لیتری",
        ]
        for q in self.PLAIN_QUERIES:
            for title in plain_titles:
                assert is_flavor_compatible(q, title) is True, f"Plain query '{q}' falsely rejected '{title}'"

    def test_match_sku_plain_milk_against_20_plus_flavored_candidate_pool(self):
        """
        Adversarial SKU match: query plain milk against a catalog of 20+ flavored candidates
        plus 1 plain milk candidate. Guarantees zero false pairing with any flavor.
        """
        query = parse_single_item("شیر پرچرب کاله یک لیتری")
        assert query.name == "شیر"

        candidates = [
            StoreItem(
                platform="snapp_market",
                store_id="s1",
                product_id=f"flav_{i}",
                title=title,
                base_price=45000,
                discount_price=45000,
            )
            for i, title in enumerate(self.FLAVORED_TITLES)
        ]

        # 1. Pool with ONLY flavors -> MUST return None
        matched_none = match_sku(query, candidates)
        assert matched_none is None, f"Matched flavored item: {matched_none.title if matched_none else None}"

        # 2. Add plain milk candidate -> MUST match only the plain candidate
        plain_candidate = StoreItem(
            platform="snapp_market",
            store_id="s1",
            product_id="plain_kalleh",
            title="شیر پرچرب کاله ۱ لیتری",
            base_price=48000,
            discount_price=48000,
        )
        matched_plain = match_sku(query, candidates + [plain_candidate])
        assert matched_plain is not None
        assert matched_plain.product_id == "plain_kalleh"
        assert matched_plain.title == "شیر پرچرب کاله ۱ لیتری"
