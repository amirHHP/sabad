"""
Tests for Store Pricing & Currency Normalization across Sabad Adapters.
Verifies that SnappMarket, Digikala Jet, and Okala prices, delivery fees,
and MOV are consistently represented in Tomans without 10x discrepancies.
"""

import httpx
import pytest
from unittest.mock import AsyncMock, patch
from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter


class TestRialsToTomans:
    """Verifies BaseStoreAdapter.rials_to_tomans utility."""

    def test_standard_conversions(self):
        # 1,580,000 Rials = 158,000 Tomans
        assert BaseStoreAdapter.rials_to_tomans(1580000) == 158000.0
        # 2,290,000 Rials = 229,000 Tomans
        assert BaseStoreAdapter.rials_to_tomans(2290000.0) == 229000.0
        # 378,000 Rials = 37,800 Tomans
        assert BaseStoreAdapter.rials_to_tomans(378000) == 37800.0
        # 10,000,000 Rials = 1,000,000 Tomans
        assert BaseStoreAdapter.rials_to_tomans(10000000) == 1000000.0

    def test_string_inputs(self):
        assert BaseStoreAdapter.rials_to_tomans("1580000") == 158000.0
        assert BaseStoreAdapter.rials_to_tomans("378000.0") == 37800.0

    def test_rounding_precision(self):
        # 123,456 Rials -> 12,345.6 Tomans
        assert BaseStoreAdapter.rials_to_tomans(123456) == 12345.6

    def test_none_and_invalid_fallback(self):
        assert BaseStoreAdapter.rials_to_tomans(None) == 0.0
        assert BaseStoreAdapter.rials_to_tomans(None, fallback=25000.0) == 25000.0
        assert BaseStoreAdapter.rials_to_tomans("invalid_string", fallback=29000.0) == 29000.0
        assert BaseStoreAdapter.rials_to_tomans(0, fallback=25000.0) == 25000.0
        assert BaseStoreAdapter.rials_to_tomans(-100, fallback=10.0) == 10.0


class TestPricingNormalization:
    """Verifies that staple products across all 3 stores are aligned in Tomans."""

    @pytest.mark.asyncio
    async def test_staple_products_pricing_alignment(self):
        """
        Staple goods (milk, cheese, dishwashing liquid) must be parsed in Tomans
        without 10x discrepancies between SnappMarket, Digikala Jet, and Okala.
        """
        # 1. SnappMarket payload (native Tomans)
        snapp_payload = {
            "data": {
                "vendor_product_variations": {
                    "items": [
                        {
                            "id": 101,
                            "products": [
                                {
                                    "id": 1,
                                    "title": "شیر کم چرب روزانه 1 لیتری",
                                    "brand": "روزانه",
                                    "price": 158000,
                                    "discount": 0,
                                    "stock": 10,
                                },
                                {
                                    "id": 2,
                                    "title": "پنیر فتا دوشه هراز 400 گرمی",
                                    "brand": "هراز",
                                    "price": 229000,
                                    "discount": 29770,
                                    "stock": 5,
                                },
                                {
                                    "id": 3,
                                    "title": "مایع ظرفشویی پریل 1 لیتری",
                                    "brand": "پریل",
                                    "price": 85000,
                                    "discount": 10000,
                                    "stock": 8,
                                },
                            ],
                        }
                    ]
                }
            }
        }

        # 2. Digikala Jet payload (native Rials)
        jet_payload = {
            "data": {
                "result": [
                    {
                        "id": 201,
                        "title": "شیر کم چرب روزانه حجم 1 لیتر",
                        "brand": {"title": "روزانه"},
                        "price": {"price": 1580000, "discount": 0, "discount_percentage": 0},
                        "stock": {"has_stock": True},
                    },
                    {
                        "id": 202,
                        "title": "پنیر فتا دوشه هراز - 400 گرم",
                        "brand": {"title": "هراز"},
                        "price": {"price": 2290000, "discount": 297700, "discount_percentage": 13},
                        "stock": {"has_stock": True},
                    },
                    {
                        "id": 203,
                        "title": "مایع ظرفشویی پریل 1 لیتری",
                        "brand": {"title": "پریل"},
                        "price": {"price": 850000, "discount": 100000, "discount_percentage": 12},
                        "stock": {"has_stock": True},
                    },
                ]
            }
        }

        # 3. Okala payload (native Rials, okPrice present)
        okala_payload = {
            "entities": [
                {
                    "id": 301,
                    "name": "شیر کم چرب روزانه 1 لیتری",
                    "price": 1580000.0,
                    "discountPercent": 0,
                    "okPrice": 1580000.0,
                    "quantity": 10,
                },
                {
                    "id": 302,
                    "name": "پنیر فتا دوشه هراز 400 گرمی",
                    "price": 2290000.0,
                    "discountPercent": 13.0,
                    "okPrice": 1992300.0,
                    "quantity": 5,
                },
                {
                    "id": 303,
                    "name": "مایع ظرفشویی پریل 1 لیتری",
                    "price": 850000.0,
                    "discountPercent": 11.8,
                    "okPrice": 750000.0,
                    "quantity": 8,
                },
            ]
        }

        # Query each adapter
        snapp_adapter = SnappMarketAdapter()
        with patch.object(snapp_adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=snapp_payload))):
            snapp_items = await snapp_adapter.search("شیر", 35.7, 51.4)

        jet_adapter = DigikalaJetAdapter()
        with patch.object(jet_adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=jet_payload))):
            jet_items = await jet_adapter.search("شیر", 35.7, 51.4)

        okala_adapter = OkalaAdapter()
        with patch.object(okala_adapter, "_ensure_store_id", new=AsyncMock(return_value="2319")), \
             patch.object(okala_adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=okala_payload))):
            okala_items = await okala_adapter.search("شیر", 35.7, 51.4)

        assert len(snapp_items) == 3
        assert len(jet_items) == 3
        assert len(okala_items) == 3

        # Assert staple prices are all in Tomans (10,000 - 300,000 Tomans)
        all_items = snapp_items + jet_items + okala_items
        for item in all_items:
            assert 10000 <= item.base_price <= 300000, f"Item {item.title} base price {item.base_price} out of range"
            assert 10000 <= item.discount_price <= 300000, f"Item {item.title} discount price {item.discount_price} out of range"

        # Compare milk across stores: Snapp = 158000 T, Jet = 158000 T, Okala = 158000 T
        milk_prices = [
            snapp_items[0].discount_price,
            jet_items[0].discount_price,
            okala_items[0].discount_price,
        ]
        assert max(milk_prices) / min(milk_prices) <= 1.05, "Milk prices have 10x discrepancy between stores!"
        for p in milk_prices:
            assert 150000 <= p <= 165000

        # Compare cheese across stores: Snapp = ~199,230 T, Jet = ~199,230 T, Okala = 199,230 T
        cheese_prices = [
            snapp_items[1].discount_price,
            jet_items[1].discount_price,
            okala_items[1].discount_price,
        ]
        assert max(cheese_prices) / min(cheese_prices) <= 1.05, "Cheese prices have 10x discrepancy between stores!"
        for p in cheese_prices:
            assert 190000 <= p <= 210000


class TestStoreInfoNormalization:
    """Verifies that delivery fees and MOV across all 3 stores are within realistic Toman ranges."""

    @pytest.mark.asyncio
    async def test_delivery_fees_and_mov_standard_ranges(self):
        # SnappMarket store info response (native Tomans)
        snapp_info_payload = {
            "data": {
                "finalResult": [
                    {
                        "data": {
                            "id": 999,
                            "title": "هایپراستار ارم",
                            "isOpen": True,
                            "status": "ACTIVE",
                            "minimumOrderValue": 140000,
                            "deliveryFee": 31400,
                            "couponMinBasket": 300000,
                        }
                    }
                ]
            }
        }

        # Digikala Jet store info response (native Rials)
        jet_info_payload = {
            "data": {
                "result": [
                    {
                        "id": 888,
                        "title": "سوپرمارکت جت میرداماد",
                        "working_status": {"is_open": True},
                        "delivery": {
                            "cost": 378000,  # 37,800 Tomans
                            "free_shipping_price": 10000000,  # 1,000,000 Tomans
                        },
                    }
                ]
            }
        }

        # Okala store details response (native Rials)
        okala_nearby_payload = {
            "data": {
                "stores": [
                    {
                        "storeId": 777,
                        "storeName": "افق کوروش سهروردی",
                        "storeCategoryName": "افق کوروش",
                    }
                ]
            }
        }
        okala_details_payload = {
            "data": {
                "isActive": True,
                "isExist": True,
                "minimumOrder": 2000000,  # 200,000 Tomans
                "cost": 250000,  # 25,000 Tomans
            }
        }

        snapp_adapter = SnappMarketAdapter()
        with patch.object(snapp_adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=snapp_info_payload))):
            snapp_info = await snapp_adapter.get_store_info(35.7, 51.4)

        jet_adapter = DigikalaJetAdapter()
        with patch.object(jet_adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=jet_info_payload))):
            jet_info = await jet_adapter.get_store_info(35.7, 51.4)

        okala_adapter = OkalaAdapter()
        with patch.object(
            okala_adapter.client,
            "get",
            new=AsyncMock(side_effect=[
                httpx.Response(200, json=okala_nearby_payload),
                httpx.Response(200, json=okala_details_payload),
            ])
        ):
            okala_info = await okala_adapter.get_store_info(35.7, 51.4)

        assert snapp_info is not None
        assert jet_info is not None
        assert okala_info is not None

        # Verify Minimum Order Value (MOV) across all stores: 50,000 - 300,000 Tomans
        assert 50000 <= snapp_info.minimum_order_value <= 300000
        assert snapp_info.minimum_order_value == 140000.0

        assert 50000 <= jet_info.minimum_order_value <= 300000
        assert jet_info.minimum_order_value == 120000.0

        assert 50000 <= okala_info.minimum_order_value <= 300000
        assert okala_info.minimum_order_value == 200000.0

        # Verify Delivery Fees across all stores: 15,000 - 60,000 Tomans
        snapp_fee = snapp_info.delivery_tiers[0].fee
        jet_fee = jet_info.delivery_tiers[0].fee
        okala_fee = okala_info.delivery_tiers[0].fee

        assert 15000 <= snapp_fee <= 60000
        assert snapp_fee == 31400.0

        assert 15000 <= jet_fee <= 60000
        assert jet_fee == 37800.0

        assert 15000 <= okala_fee <= 60000
        assert okala_fee == 25000.0

        # Verify free shipping thresholds: >= 300,000 Tomans
        assert snapp_info.delivery_tiers[0].max_subtotal == 300000.0
        assert jet_info.delivery_tiers[0].max_subtotal == 1000000.0
        assert okala_info.delivery_tiers[0].max_subtotal == 400000.0


class TestOutOfStockAndEdgeCases:
    """Verifies edge cases: out-of-stock items, None discountPercent, missing prices."""

    @pytest.mark.asyncio
    async def test_digikala_jet_out_of_stock_never_produces_1_toman_item(self):
        """
        Critical defect regression test: Out-of-stock items in Digikala Jet
        where price is None must NEVER produce 1-Toman products.
        """
        jet_payload = {
            "data": {
                "result": [
                    {
                        "id": 501,
                        "title": "شیر کم چرب پروتئینه 945 سی سی",
                        "price": None,
                        "stock": {"has_stock": False, "is_running_low": False},
                    },
                    {
                        "id": 502,
                        "title": "پنیر خامه‌ای ویلی 200 گرمی",
                        "price": {"price": 0, "discount": 0},
                        "stock": {"has_stock": False},
                    },
                    {
                        "id": 503,
                        "title": "کره پاستوریزه 100 گرمی کاله",
                        "price": {"price": 450000, "discount": 0},  # Price is 45,000 Tomans
                        "stock": {"has_stock": False},  # Out of stock
                    },
                ]
            }
        }

        jet_adapter = DigikalaJetAdapter()
        with patch.object(jet_adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=jet_payload))):
            items = await jet_adapter.search("لبنیات", 35.7, 51.4)

        assert len(items) == 3
        for item in items:
            # Crucial assertion: none of these items are in stock
            assert item.is_in_stock is False
            # Crucial assertion: discount_price is NEVER 1 Toman!
            assert item.discount_price != 1.0, f"Item {item.title} produced 1-Toman price!"

        # Missing price item has 0.0 price
        assert items[0].base_price == 0.0
        assert items[0].discount_price == 0.0

        # Zero price item has 0.0 price
        assert items[1].base_price == 0.0
        assert items[1].discount_price == 0.0

        # Item 3 had a shelf price (45,000 T) but is marked not in stock
        assert items[2].base_price == 45000.0
        assert items[2].discount_price == 45000.0
        assert items[2].is_in_stock is False

    @pytest.mark.asyncio
    async def test_okala_handles_none_discount_percent_safely(self):
        """
        Regression test: When Okala returns discountPercent as null/None,
        float(None) must not raise TypeError.
        """
        okala_payload = {
            "entities": [
                {
                    "id": 601,
                    "name": "رب گوجه فرنگی روژین 800 گرمی",
                    "price": 850000.0,  # 85,000 Tomans
                    "discountPercent": None,  # Native API returns None for undiscounted items
                    "okPrice": None,
                    "quantity": 12,
                },
                {
                    "id": 602,
                    "name": "روغن آفتابگردان لادن 1.5 لیتری",
                    "price": 1450000.0,
                    "discountPercent": 10.0,
                    "okPrice": 1305000.0,  # 130,500 Tomans
                    "quantity": 4,
                },
            ]
        }

        okala_adapter = OkalaAdapter()
        with patch.object(okala_adapter, "_ensure_store_id", new=AsyncMock(return_value="2319")), \
             patch.object(okala_adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=okala_payload))):
            items = await okala_adapter.search("رب", 35.7, 51.4)

        assert len(items) == 2
        item1 = items[0]
        assert item1.title == "رب گوجه فرنگی روژین 800 گرمی"
        assert item1.base_price == 85000.0
        assert item1.discount_price == 85000.0
        assert item1.discount_percent == 0.0
        assert item1.is_in_stock is True

        item2 = items[1]
        assert item2.base_price == 145000.0
        assert item2.discount_price == 130500.0
        assert item2.discount_percent == 10.0

    @pytest.mark.asyncio
    async def test_snappmarket_guards_zero_and_missing_prices(self):
        """
        Verify SnappMarket marks items with price <= 0 or missing prices as out of stock.
        """
        snapp_payload = {
            "data": {
                "vendor_product_variations": {
                    "items": [
                        {
                            "id": 101,
                            "products": [
                                {
                                    "id": 1,
                                    "title": "کالای ناموجود بدون قیمت",
                                    "price": 0,
                                    "discount": 0,
                                    "stock": 5,
                                },
                                {
                                    "id": 2,
                                    "title": "کالای با قیمت None",
                                    "price": None,
                                    "discount": None,
                                    "stock": 5,
                                },
                            ],
                        }
                    ]
                }
            }
        }

        snapp_adapter = SnappMarketAdapter()
        with patch.object(snapp_adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=snapp_payload))):
            items = await snapp_adapter.search("کالا", 35.7, 51.4)

        assert len(items) == 2
        for item in items:
            assert item.is_in_stock is False
            assert item.discount_price == 0.0
