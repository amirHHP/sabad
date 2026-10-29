"""
Unit tests for platform adapters: BaseStoreAdapter, SnappMarket, Digikala Jet, and Okala.
"""

import httpx
import pytest
from unittest.mock import AsyncMock, patch
from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter, best_category_slug
from sabad.adapters.tapsi_market import TapsiMarketAdapter
from sabad.models.dispatch import CartItemMutation


class TestBaseStoreAdapter:
    def test_rials_to_tomans_static(self):
        assert BaseStoreAdapter.rials_to_tomans(1000) == 100.0
        assert BaseStoreAdapter.rials_to_tomans(None, 50.0) == 50.0


class TestSnappMarketAdapterUnit:
    @pytest.fixture
    def adapter(self):
        return SnappMarketAdapter()

    def test_metadata(self, adapter):
        assert adapter.platform_name == "snapp_market"
        assert adapter.platform_title_fa == "اسنپ‌مارکت"
        assert adapter.get_checkout_url() == "https://snapp.market/cart"

    @pytest.mark.asyncio
    async def test_get_store_info_fallback_on_network_error(self, adapter):
        with patch.object(adapter.client, "get", side_effect=Exception("Connection refused")):
            info = await adapter.get_store_info(35.7, 51.4)
            assert info is not None
            assert info.platform == "snapp_market"
            assert info.minimum_order_value > 0
            assert len(info.delivery_tiers) >= 1

    @pytest.mark.asyncio
    async def test_flash_deals_filters_low_discount(self, adapter):
        with patch.object(adapter, "search", new=AsyncMock()) as mock_search:
            from sabad.models.catalog import StoreItem
            mock_search.return_value = [
                StoreItem(
                    platform="snapp_market",
                    store_id="1",
                    product_id="p1",
                    title="کالای با تخفیف بالا",
                    base_price=100000,
                    discount_price=70000,
                    discount_percent=30.0,
                    is_in_stock=True,
                ),
                StoreItem(
                    platform="snapp_market",
                    store_id="1",
                    product_id="p2",
                    title="کالای با تخفیف کم",
                    base_price=100000,
                    discount_price=95000,
                    discount_percent=5.0,
                    is_in_stock=True,
                ),
            ]
            deals = await adapter.get_flash_deals(35.7, 51.4)
            assert len(deals) == 1
            assert deals[0].product_id == "p1"

    @pytest.mark.asyncio
    async def test_add_to_cart_without_auth(self, adapter):
        with patch("sabad.adapters.session_manager.SessionManager.get_token", return_value=None):
            mutation = CartItemMutation(product_id="123", quantity=2, store_id="1")
            result = await adapter.add_to_cart([mutation])
            assert result.success is False
            assert "نشست کاربری" in result.error_message


class TestDigikalaJetAdapterUnit:
    @pytest.fixture
    def adapter(self):
        return DigikalaJetAdapter()

    def test_metadata(self, adapter):
        assert adapter.platform_name == "digikala_jet"
        assert adapter.platform_title_fa == "دیجی‌کالا جت"
        assert adapter.get_checkout_url() == "https://www.digikalajet.com/cart"

    @pytest.mark.asyncio
    async def test_get_store_info_fallback_on_network_error(self, adapter):
        with patch.object(adapter.client, "get", side_effect=Exception("Connection error")):
            info = await adapter.get_store_info(35.7, 51.4)
            assert info is not None
            assert info.platform == "digikala_jet"
            assert info.minimum_order_value > 0
            assert len(info.delivery_tiers) >= 1

    @pytest.mark.asyncio
    async def test_get_flash_deals_parsing(self, adapter):
        main_page_payload = {
            "data": {
                "components": [
                    {
                        "component_type": "amazing-widget-on-other-lines",
                        "data": {
                            "api": {"url": "/v1/amazing-products/"}
                        }
                    }
                ]
            }
        }
        products_payload = {
            "data": {
                "products": [
                    {
                        "id": 901,
                        "title": "شیر کهکشانی جت",
                        "price": {"price": 1600000, "discount": 400000, "discount_percentage": 25},
                        "stock": {"has_stock": True},
                    }
                ]
            }
        }

        with patch.object(
            adapter.client,
            "get",
            new=AsyncMock(side_effect=[
                httpx.Response(200, json=main_page_payload),
                httpx.Response(200, json=products_payload),
            ])
        ):
            deals = await adapter.get_flash_deals(35.7, 51.4)

            assert len(deals) == 1
            deal = deals[0]
            assert deal.title == "شیر کهکشانی جت"
            assert deal.base_price == 160000.0
            assert deal.discount_price == 120000.0
            assert deal.discount_percent == 25.0
            assert deal.is_flash_deal is True
            assert deal.is_in_stock is True

    @pytest.mark.asyncio
    async def test_search_normalizes_gallery_media_without_dropping_products(self, adapter):
        payload = {
            "data": {
                "result": [
                    {
                        "id": 901,
                        "title": "شامپو مو ۴۰۰ میلی‌لیتری",
                        "shop": {"id": "193117851239"},
                        "price": {"price": 1200000, "discount": 100000, "discount_percentage": 8.3},
                        "stock": {"has_stock": True},
                        "media": [{"main": "https://cdn.example/shampoo.jpg"}],
                        "url": {"url": "https://www.digikalajet.com/product/901"},
                    },
                    {
                        "id": 902,
                        "title": "حوله دستی کوچک",
                        "price": {"price": 800000, "discount": 0},
                        "stock": {"has_stock": True},
                        "media": [{"thumb": "https://cdn.example/towel.jpg"}],
                    },
                ]
            }
        }
        with patch.object(adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=payload))):
            items = await adapter.search("شامپو", 35.7, 51.4)

        assert [item.product_id for item in items] == ["901", "902"]
        assert items[0].image_url == "https://cdn.example/shampoo.jpg"
        assert items[0].product_url == "https://www.digikalajet.com/shop/product/193117851239/901/"
        assert items[1].image_url == "https://cdn.example/towel.jpg"

    @pytest.mark.asyncio
    async def test_add_to_cart_without_auth(self, adapter):
        with patch("sabad.adapters.session_manager.SessionManager.get_token", return_value=None):
            mutation = CartItemMutation(product_id="123", quantity=2, store_id="jet")
            result = await adapter.add_to_cart([mutation])
            assert result.success is False
            assert "نشست کاربری" in result.error_message


class TestOkalaAdapterUnit:
    @pytest.fixture
    def adapter(self):
        return OkalaAdapter()

    def test_metadata(self, adapter):
        assert adapter.platform_name == "okala"
        assert adapter.platform_title_fa == "افق کوروش / اکالا"
        assert adapter.get_checkout_url() == "https://okala.com/cart"

    @pytest.mark.asyncio
    async def test_get_store_info_fallback_on_network_error(self, adapter):
        with patch.object(adapter.client, "get", side_effect=Exception("Connection error")):
            info = await adapter.get_store_info(35.7, 51.4)
            assert info is not None
            assert info.platform == "okala"
            assert info.minimum_order_value > 0
            assert len(info.delivery_tiers) >= 1

    @pytest.mark.asyncio
    async def test_get_flash_deals_parsing(self, adapter):
        payload = {
            "entities": [
                {
                    "id": 991,
                    "name": "روغن ذرت تخفیف ویژه",
                    "price": 2500000.0,
                    "discountPercent": 20.0,
                    "okPrice": 2000000.0,
                    "quantity": 10,
                }
            ]
        }
        with patch.object(adapter, "_ensure_store_id", new=AsyncMock(return_value="2319")), \
             patch.object(adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=payload))):
            deals = await adapter.get_flash_deals(35.7, 51.4)

            assert len(deals) == 1
            deal = deals[0]
            assert deal.title == "روغن ذرت تخفیف ویژه"
            assert deal.base_price == 250000.0
            assert deal.discount_price == 200000.0
            assert deal.discount_percent == 20.0
            assert deal.is_flash_deal is True

    @pytest.mark.asyncio
    async def test_add_to_cart_without_auth(self, adapter):
        with patch("sabad.adapters.session_manager.SessionManager.get_token", return_value=None):
            mutation = CartItemMutation(product_id="123", quantity=2, store_id="okala")
            result = await adapter.add_to_cart([mutation])
            assert result.success is False
            assert "نشست کاربری" in result.error_message

    def test_category_slug_prefers_exact_name_over_prefix(self):
        categories = [
            {"name": "شیرینی", "latinName": "sweets"},
            {"name": "شیر", "latinName": "milk"},
            {"name": "شیر کم چرب", "latinName": "low-fat-milk"},
        ]
        assert best_category_slug(categories, "شیر") == "milk"
        assert best_category_slug(categories, "شیر کم چرب") == "low-fat-milk"

    @pytest.mark.asyncio
    async def test_search_reads_public_category_shelf(self, adapter):
        categories = {
            "data": {"categories": [
                {"name": "شیرینی", "latinName": "sweets", "children": []},
                {"name": "شیر", "latinName": "milk", "children": []},
            ]}
        }
        shelf = {
            "data": [{
                "id": 716,
                "name": "شیر کم چرب میهن ۱ لیتری",
                "price": 1590000,
                "okPrice": 1431000,
                "discountPercent": 10,
                "quantity": 4,
                "storeId": 2223,
            }]
        }

        async def fake_get(url, *args, **kwargs):
            if "categories/nearby" in str(url):
                return httpx.Response(200, json=categories)
            return httpx.Response(200, json=shelf)

        adapter._cached_store_id = "2223"
        with patch.object(adapter.client, "get", new=AsyncMock(side_effect=fake_get)):
            items = await adapter.search("شیر", 35.7, 51.4)

        assert len(items) == 1
        assert items[0].product_id == "716"
        assert items[0].store_id == "2223"
        assert items[0].base_price == 159000.0
        assert items[0].discount_price == 143100.0


class TestTapsiMarketAdapterUnit:
    @pytest.fixture
    def adapter(self):
        return TapsiMarketAdapter()

    def test_metadata(self, adapter):
        assert adapter.platform_name == "tapsi_market"
        assert adapter.platform_title_fa == "تپسی مارکت"
        assert adapter.get_checkout_url() == "https://tapsi.food/basket/list"
        assert adapter.get_checkout_url("v123") == "https://tapsi.food/vendor/v123"

    @pytest.mark.asyncio
    async def test_get_store_info_fallback_on_network_error(self, adapter):
        with patch.object(adapter.client, "get", side_effect=Exception("Network error")):
            info = await adapter.get_store_info(35.7, 51.4)
            assert info is not None
            assert info.platform == "tapsi_market"
            assert info.minimum_order_value > 0
            assert len(info.delivery_tiers) >= 1

    @pytest.mark.asyncio
    async def test_search_parsing(self, adapter):
        payload = {
            "statusCode": 200,
            "data": [
                {
                    "id": "item_1",
                    "productInfo": {
                        "name": "شیر کم چرب کاله ۱ لیتری",
                        "price": 38000.0,
                        "priceAfterDiscount": 34200.0,
                        "discountRatio": 10.0,
                        "images": ["https://cdn.tapsi.food/img.jpg"]
                    },
                    "vendorInfo": {
                        "vendorCode": "v_test",
                        "title": "هایپرمارکت تپسی",
                        "vendorStatus": "Open",
                        "deliveryPrice": 30000.0
                    }
                },
                {
                    "id": "restaurant_item",
                    "productInfo": {
                        "name": "ماکارونی پخته ویژه",
                        "price": 250000.0,
                        "priceAfterDiscount": 250000.0,
                    },
                    "vendorInfo": {
                        "vendorCode": "restaurant_vendor",
                        "title": "رستوران ایتالیایی",
                        "vendorStatus": "Open",
                    }
                }
            ]
        }
        with patch.object(adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=payload))):
            items = await adapter.search("شیر", 35.7, 51.4)
            assert len(items) == 1
            item = items[0]
            assert item.platform == "tapsi_market"
            assert item.store_id == "v_test"
            assert item.product_id == "item_1"
            assert item.title == "شیر کم چرب کاله ۱ لیتری"
            assert item.base_price == 38000.0
            assert item.discount_price == 34200.0
            assert item.discount_percent == 10.0
            assert item.is_in_stock is True

    @pytest.mark.asyncio
    async def test_search_keeps_market_results_when_discovery_codes_differ(self, adapter):
        adapter._cached_store_id = "nearby_branch"
        payload = {
            "data": [
                {
                    "id": "market_item",
                    "productInfo": {
                        "name": "حوله دستی کوچک",
                        "price": 100000.0,
                        "priceAfterDiscount": 90000.0,
                    },
                    "vendorInfo": {
                        "vendorCode": "another_market_branch",
                        "title": "سوپرمارکت محلی",
                        "vendorType": "market",
                        "vendorStatus": "Open",
                    },
                },
                {
                    "id": "restaurant_item",
                    "productInfo": {
                        "name": "واکس و شامپو خودرو",
                        "price": 100000.0,
                        "priceAfterDiscount": 100000.0,
                    },
                    "vendorInfo": {
                        "vendorCode": "food_branch",
                        "title": "رستوران نمونه",
                        "vendorType": "restaurant",
                        "vendorStatus": "Open",
                    },
                },
            ]
        }
        with patch.object(adapter.client, "get", new=AsyncMock(return_value=httpx.Response(200, json=payload))):
            items = await adapter.search("حوله", 35.7, 51.4)

        assert [item.product_id for item in items] == ["market_item"]

    @pytest.mark.asyncio
    async def test_add_to_cart_without_auth(self, adapter):
        with patch("sabad.adapters.session_manager.SessionManager.get_token", return_value=None):
            mutation = CartItemMutation(product_id="item_1", quantity=1, store_id="v_test")
            result = await adapter.add_to_cart([mutation])
            assert result.success is False
            assert "نشست کاربری" in result.error_message

    @pytest.mark.asyncio
    async def test_search_skips_restaurants_and_reads_grocery_vertical(self, adapter):
        facets = {
            "data": {"businessTypes": [
                {"id": "1", "faName": "رستوران", "count": 20},
                {"id": "2", "faName": "کافه", "count": 8},
                {"id": "5", "faName": "پروتئین", "count": 4},
            ]}
        }
        grocery = {
            "data": [{
                "id": "milk-1",
                "productInfo": {
                    "id": "milk-1",
                    "name": "شیر پرچرب ماهشام",
                    "price": 48000,
                    "priceAfterDiscount": 48000,
                },
                "vendorInfo": {
                    "vendorCode": "protein-1",
                    "title": "سام پروتئین",
                    "vendorStatus": "Open",
                },
            }]
        }

        async def fake_get(url, *args, **kwargs):
            address = str(url)
            if "facets" in address:
                return httpx.Response(200, json=facets)
            if "businessTypeIds=5" in address:
                return httpx.Response(200, json=grocery)
            return httpx.Response(200, json={"data": []})

        with patch.object(adapter.client, "get", new=AsyncMock(side_effect=fake_get)):
            items = await adapter.search("شیر", 35.7, 51.4)

        assert [item.product_id for item in items] == ["milk-1"]
        assert items[0].title == "شیر پرچرب ماهشام"
        assert items[0].store_id == "protein-1"
