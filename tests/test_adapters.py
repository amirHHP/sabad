"""
Unit tests for platform adapters: BaseStoreAdapter, SnappMarket, Digikala Jet, and Okala.
"""

import httpx
import pytest
from unittest.mock import AsyncMock, patch
from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
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
    async def test_add_to_cart_without_auth(self, adapter):
        with patch("sabad.adapters.session_manager.SessionManager.get_token", return_value=None):
            mutation = CartItemMutation(product_id="item_1", quantity=1, store_id="v_test")
            result = await adapter.add_to_cart([mutation])
            assert result.success is False
            assert "نشست کاربری" in result.error_message
