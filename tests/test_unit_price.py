"""Comparable pack prices and size-aware ranking."""

import asyncio
from unittest.mock import AsyncMock

from sabad.harvester import CatalogHarvester
from sabad.models.catalog import DeliveryTier, StoreInfo, StoreItem
from sabad.models.grocery import ParsedGroceryItem
from sabad.normalizer.matcher import match_sku
from sabad.pricing import comparable_price, unit_price_options


def _item(product_id: str, title: str, price: float) -> StoreItem:
    return StoreItem(
        platform="snapp_market",
        store_id="branch",
        product_id=product_id,
        title=title,
        base_price=price,
        discount_price=price,
        is_in_stock=True,
    )


def test_shampoo_sizes_expose_price_per_100ml():
    small = _item("s200", "شامپو سر ۲۰۰ میلی‌لیتری", 90_000)
    medium = _item("s400", "شامپو سر ۴۰۰ میلی‌لیتری", 140_000)
    large = _item("s1000", "شامپو سر ۱۰۰۰ میلی‌لیتری", 240_000)

    assert comparable_price(small).value == 45_000
    assert comparable_price(medium).value == 35_000
    assert comparable_price(large).value == 24_000
    assert comparable_price(small).label == "هر ۱۰۰ میلی‌لیتر"

    options = unit_price_options([small, medium, large])
    assert options[0]["product_id"] == "s1000"
    assert options[0]["is_cheapest"] is True
    assert options[-1]["is_cheapest"] is False


def test_unspecified_shampoo_picks_lowest_unit_price_not_bulk_jug():
    query = ParsedGroceryItem(raw_text="شامپو", name="شامپو")
    candidates = [
        _item("jug", "شامپو سر ۴ لیتری", 1_200_000),
        _item("s200", "شامپو سر ۲۰۰ میلی‌لیتری", 90_000),
        _item("s400", "شامپو سر ۴۰۰ میلی‌لیتری", 140_000),
        _item("s1000", "شامپو سر ۱۰۰۰ میلی‌لیتری", 240_000),
        _item("body", "شامپو بدن گیاهی", 50_000),
    ]

    selected = match_sku(query, candidates)

    assert selected is not None
    assert selected.product_id == "s1000"


def test_explicit_volume_still_uses_the_requested_pack():
    query = ParsedGroceryItem(raw_text="شامپو ۴۰۰ میلی‌لیتری", name="شامپو", volume_weight=400, unit="میلی‌لیتر")
    candidates = [
        _item("s200", "شامپو سر ۲۰۰ میلی‌لیتری", 40_000),
        _item("s400", "شامپو سر ۴۰۰ میلی‌لیتری", 140_000),
        _item("s1000", "شامپو سر ۱۰۰۰ میلی‌لیتری", 180_000),
    ]

    assert match_sku(query, candidates).product_id == "s400"


def test_harvester_compares_200_400_and_1000ml_by_unit_price():
    def adapter(platform):
        mock = AsyncMock()
        mock.platform_title_fa = platform
        mock.get_store_info.return_value = StoreInfo(
            platform=platform,
            store_id="branch",
            title=platform,
            delivery_tiers=[DeliveryTier(min_subtotal=0, fee=0)],
        )
        mock.search.return_value = [
            _item("s200", "شامپو سر ۲۰۰ میلی‌لیتری", 90_000),
            _item("s400", "شامپو سر ۴۰۰ میلی‌لیتری", 140_000),
            _item("s1000", "شامپو سر ۱۰۰۰ میلی‌لیتری", 240_000),
        ]
        for item in mock.search.return_value:
            item.platform = platform
        return mock

    harvester = CatalogHarvester({"snapp_market": adapter("snapp_market"), "okala": adapter("okala")})
    item = ParsedGroceryItem(raw_text="شامپو", name="شامپو")
    _infos, matches = asyncio.run(harvester.harvest_catalog_matches([item], 35.7, 51.4))

    assert matches["شامپو"]["snapp_market"].product_id == "s1000"
    assert matches["شامپو"]["okala"].product_id == "s1000"
    options = harvester.last_search_evidence["شامپو"]["snapp_market"]["unit_options"]
    assert options[0]["product_id"] == "s1000"
    assert options[0]["is_cheapest"] is True
