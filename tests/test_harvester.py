"""
Unit tests for CatalogHarvester.
"""

import asyncio
from unittest.mock import AsyncMock
from sabad.harvester import CatalogHarvester
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier


def test_harvester_concurrent_gather():
    mock_adapter1 = AsyncMock()
    mock_adapter1.platform_title_fa = "فروشگاه ۱"
    mock_adapter1.get_store_info.return_value = StoreInfo(
        platform="s1", store_id="1", title="S1", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=20000)]
    )
    mock_adapter1.search.return_value = [
        StoreItem(platform="s1", store_id="1", product_id="p1", title="شیر کاله 1 لیتری", base_price=40000, discount_price=40000)
    ]
    mock_adapter1.get_flash_deals.return_value = [
        StoreItem(platform="s1", store_id="1", product_id="d1", title="پنیر تخفیف‌دار", base_price=50000, discount_price=35000, is_flash_deal=True)
    ]

    mock_adapter2 = AsyncMock()
    mock_adapter2.platform_title_fa = "فروشگاه ۲"
    mock_adapter2.get_store_info.return_value = StoreInfo(
        platform="s2", store_id="2", title="S2", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=25000)]
    )
    mock_adapter2.search.return_value = [
        StoreItem(platform="s2", store_id="2", product_id="p2", title="شیر کاله 1 لیتری", base_price=39000, discount_price=39000)
    ]
    mock_adapter2.get_flash_deals.return_value = []

    harvester = CatalogHarvester(adapters={"s1": mock_adapter1, "s2": mock_adapter2})

    # Test flash deals harvesting
    deals = asyncio.run(harvester.harvest_flash_deals(35.7, 51.4))
    assert len(deals["s1"]) == 1
    assert len(deals["s2"]) == 0

    # Test catalog harvesting
    item = ParsedGroceryItem(raw_text="شیر کاله", name="شیر", brand="کاله", quantity=1)
    store_infos, matches = asyncio.run(harvester.harvest_catalog_matches([item], 35.7, 51.4))

    assert "s1" in store_infos
    assert "s2" in store_infos
    assert matches["شیر کاله"]["s1"] is not None
    assert matches["شیر کاله"]["s2"] is not None
    assert matches["شیر کاله"]["s2"].discount_price == 39000
