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


def test_harvester_variant_harmonization():
    """Verifies that cross-store harmonization aligns disparate store candidates onto the same package size."""
    mock_s1 = AsyncMock()
    mock_s1.platform_title_fa = "اسنپ"
    mock_s1.get_store_info.return_value = StoreInfo(platform="s1", store_id="1", title="S1", delivery_tiers=[])
    # s1 has 8-pack first, then 2-pack
    mock_s1.search.return_value = [
        StoreItem(platform="s1", store_id="1", product_id="s1_8", title="دستمال توالت پاپیا 8 عددی", base_price=560000, discount_price=560000),
        StoreItem(platform="s1", store_id="1", product_id="s1_2", title="دستمال توالت پاپیا 2 عددی", base_price=140000, discount_price=140000),
    ]

    mock_s2 = AsyncMock()
    mock_s2.platform_title_fa = "جت"
    mock_s2.get_store_info.return_value = StoreInfo(platform="s2", store_id="2", title="S2", delivery_tiers=[])
    # s2 has 2-pack first, then 8-pack
    mock_s2.search.return_value = [
        StoreItem(platform="s2", store_id="2", product_id="s2_2", title="دستمال توالت پاپیا بسته 2 عددی", base_price=150000, discount_price=150000),
        StoreItem(platform="s2", store_id="2", product_id="s2_8", title="دستمال توالت پاپیا بسته 8 عددی", base_price=580000, discount_price=580000),
    ]

    mock_s3 = AsyncMock()
    mock_s3.platform_title_fa = "اکالا"
    mock_s3.get_store_info.return_value = StoreInfo(platform="s3", store_id="3", title="S3", delivery_tiers=[])
    # s3 ONLY has 2-pack
    mock_s3.search.return_value = [
        StoreItem(platform="s3", store_id="3", product_id="s3_2", title="دستمال توالت پاپیا 2 رول", base_price=130000, discount_price=130000),
    ]

    harvester = CatalogHarvester(adapters={"s1": mock_s1, "s2": mock_s2, "s3": mock_s3})
    item = ParsedGroceryItem(raw_text="دستمال توالت پاپیا", name="دستمال توالت", brand="پاپیا", quantity=1)
    _, matches = asyncio.run(harvester.harvest_catalog_matches([item], 35.7, 51.4))

    # All three stores must be harmonized onto the 2-pack (max cross-store availability)
    m1 = matches["دستمال توالت پاپیا"]["s1"]
    m2 = matches["دستمال توالت پاپیا"]["s2"]
    m3 = matches["دستمال توالت پاپیا"]["s3"]

    assert m1 is not None and m1.product_id == "s1_2"
    assert m2 is not None and m2.product_id == "s2_2"
    assert m3 is not None and m3.product_id == "s3_2"


def test_harvester_generic_query_consumer_size_preference():
    """Generic queries (no brand, no volume) prefer consumer standard sizes (e.g. 500g pump) over 3.7L bulk gallons."""
    mock_s1 = AsyncMock()
    mock_s1.platform_title_fa = "اسنپ"
    mock_s1.get_store_info.return_value = StoreInfo(platform="s1", store_id="1", title="S1", delivery_tiers=[])
    mock_s1.search.return_value = [
        StoreItem(platform="s1", store_id="1", product_id="s1_bulk", title="مایع دستشویی اکتیو 3750 گرمی", base_price=700000, discount_price=700000),
        StoreItem(platform="s1", store_id="1", product_id="s1_small", title="مایع دستشویی اوه 450 گرمی", base_price=200000, discount_price=200000),
    ]

    mock_s2 = AsyncMock()
    mock_s2.platform_title_fa = "جت"
    mock_s2.get_store_info.return_value = StoreInfo(platform="s2", store_id="2", title="S2", delivery_tiers=[])
    mock_s2.search.return_value = [
        StoreItem(platform="s2", store_id="2", product_id="s2_bulk", title="مایع دستشویی درماکلین 3750 میلی‌لیتر", base_price=750000, discount_price=750000),
        StoreItem(platform="s2", store_id="2", product_id="s2_small", title="مایع دستشویی درماکلین 300 میلی‌لیتر", base_price=220000, discount_price=220000),
    ]

    harvester = CatalogHarvester(adapters={"s1": mock_s1, "s2": mock_s2})
    item = ParsedGroceryItem(raw_text="یه مایع دستشویی", name="مایع دستشویی", quantity=1)
    _, matches = asyncio.run(harvester.harvest_catalog_matches([item], 35.7, 51.4))

    m1 = matches["یه مایع دستشویی"]["s1"]
    m2 = matches["یه مایع دستشویی"]["s2"]

    # Both stores must select the small consumer pump bottle (~300-450g), NOT 3.75kg gallon
    assert m1 is not None and m1.product_id == "s1_small"
    assert m2 is not None and m2.product_id == "s2_small"


