import asyncio
from unittest.mock import AsyncMock

from sabad.harvester import CatalogHarvester
from sabad.models.catalog import DeliveryTier, StoreInfo, StoreItem
from sabad.models.grocery import ParsedGroceryItem
from sabad.normalizer.parser import parse_grocery_input_rule_based
from sabad.normalizer.matcher import is_product_type_compatible, match_sku


def _store_item(product_id: str, title: str, platform: str = "store") -> StoreItem:
    return StoreItem(
        platform=platform,
        store_id="branch",
        product_id=product_id,
        title=title,
        base_price=100000,
        discount_price=90000,
        is_in_stock=True,
    )


def _adapter(name: str, results):
    adapter = AsyncMock()
    adapter.platform_title_fa = name
    adapter.get_store_info.return_value = StoreInfo(
        platform=name,
        store_id="branch",
        title=name,
        delivery_tiers=[DeliveryTier(min_subtotal=0, fee=0)],
    )
    adapter.search.side_effect = results
    return adapter


def test_dictated_list_search_queries_keep_specific_names():
    from sabad.harvester import CatalogHarvester

    basket = parse_grocery_input_rule_based(
        "پتی‌بور میخوام پنیر ماسکارپونه میخوام پودر کاکائو میخوام"
    )
    by_name = {item.name: CatalogHarvester._query_variants(item) for item in basket.items}
    assert "پتیبور" in by_name["پتی بور"]
    assert "ماسکارپونه" in by_name["پنیر ماسکارپونه"]
    assert "پودر کاکائو" in by_name["پودر کاکائو"]


def test_plain_conjunction_input_becomes_three_search_items():
    basket = parse_grocery_input_rule_based("شامپو و تخم مرغ و ماکارونی")
    assert [item.name for item in basket.items] == ["شامپو", "تخم مرغ", "ماکارونی"]
    assert all(item.volume_weight is None for item in basket.items)


def test_conjunction_with_unknown_everyday_item_is_split_before_search():
    basket = parse_grocery_input_rule_based("شامپو و واکس و شامپو")
    assert [item.name for item in basket.items] == ["شامپو", "واکس", "شامپو"]


def test_no_requested_volume_does_not_reject_store_specific_skus():
    adapter = _adapter("اکالا", [])
    adapter.search.side_effect = None
    adapter.search.return_value = [
        _store_item("egg", "تخم مرغ ۶ عددی"),
        _store_item("pasta", "ماکارونی ۷۰۰ گرمی"),
        _store_item("shampoo", "شامپو ۴۰۰ میلی‌لیتری"),
    ]
    harvester = CatalogHarvester({"okala": adapter})
    basket = [
        ParsedGroceryItem(raw_text="تخم مرغ", name="تخم مرغ"),
        ParsedGroceryItem(raw_text="ماکارونی", name="ماکارونی"),
        ParsedGroceryItem(raw_text="شامپو", name="شامپو"),
    ]
    _, matches = asyncio.run(harvester.harvest_catalog_matches(basket, 35.7, 51.4))
    assert all(matches[item.raw_text]["okala"] for item in basket)


def test_search_evidence_records_query_fallback_and_failure_reason():
    adapter = _adapter(
        "دیجی‌کالا جت",
        [[], [_store_item("pasta", "ماکارونی ۷۰۰ گرمی", platform="digikala_jet")]],
    )
    harvester = CatalogHarvester({"digikala_jet": adapter})
    item = ParsedGroceryItem(raw_text="ماکارونی", name="ماکارونی")
    _, matches = asyncio.run(harvester.harvest_catalog_matches([item], 35.7, 51.4))
    evidence = harvester.last_search_evidence["ماکارونی"]["digikala_jet"]
    assert matches["ماکارونی"]["digikala_jet"] is not None
    assert [attempt["result_count"] for attempt in evidence["queries"]] == [0, 1]
    assert evidence["selected"] == "ماکارونی ۷۰۰ گرمی"
    assert evidence["final_reason"] == "کالای منطبق و موجود پیدا شد."


def test_generic_item_prefers_cheapest_compatible_sku():
    query = ParsedGroceryItem(raw_text="شامپو", name="شامپو")
    candidates = [
        _store_item("large", "شامپو ۴ لیتری", platform="snapp_market"),
        _store_item("small", "شامپو ۴۰۰ میلی‌لیتری", platform="snapp_market"),
    ]
    candidates[0].discount_price = 1_476_340
    candidates[1].discount_price = 220_000

    selected = match_sku(query, candidates)

    assert selected is not None
    assert selected.product_id == "small"


def test_generic_items_harmonize_size_family_before_price_comparison():
    snapp = _adapter("اسنپ‌مارکت", [])
    snapp.search.side_effect = None
    snapp.search.return_value = [
        _store_item("snapp_large", "شامپو ۴ لیتری", platform="snapp_market"),
        _store_item("snapp_small", "شامپو ۴۰۰ میلی‌لیتری", platform="snapp_market"),
    ]
    okala = _adapter("اکالا", [])
    okala.search.side_effect = None
    okala.search.return_value = [
        _store_item("okala_large", "شامپو ۴ لیتری", platform="okala"),
        _store_item("okala_small", "شامپو ۴۰۰ میلی‌لیتری", platform="okala"),
    ]
    snapp.search.return_value[0].discount_price = 1_400_000
    snapp.search.return_value[1].discount_price = 220_000
    okala.search.return_value[0].discount_price = 1_200_000
    okala.search.return_value[1].discount_price = 260_000

    harvester = CatalogHarvester({"snapp_market": snapp, "okala": okala})
    item = ParsedGroceryItem(raw_text="شامپو", name="شامپو")
    _, matches = asyncio.run(harvester.harvest_catalog_matches([item], 35.7, 51.4))

    assert matches["شامپو"]["snapp_market"].product_id == "snapp_small"
    assert matches["شامپو"]["okala"].product_id == "okala_small"


def test_short_generic_words_get_everyday_product_intent_defaults():
    assert is_product_type_compatible("شامپو", "شامپو مو ۴۰۰ میلی‌لیتری") is True
    assert is_product_type_compatible("شامپو", "شامپو بدن گیاهی") is False
    assert is_product_type_compatible("حوله", "حوله دستی کوچک") is True
    assert is_product_type_compatible("حوله", "حوله‌ای بزرگ کابان باف") is False
    assert is_product_type_compatible("حوله", "تی حوله‌ای میکروفایبر") is False
    assert is_product_type_compatible("شامپو", "شامپو بدن گیاهی", "شامپو بدن") is True
    assert is_product_type_compatible("حوله", "حوله حمام بزرگ", "حوله حمام") is True


def test_generic_shampoo_and_towel_choose_small_everyday_skus():
    shampoo = ParsedGroceryItem(raw_text="شامپو", name="شامپو")
    shampoo_candidates = [
        _store_item("body", "شامپو بدن گیاهی صحت"),
        _store_item("hair", "شامپو مو کوچک ۴۰۰ میلی‌لیتری"),
    ]
    shampoo_candidates[0].discount_price = 100_000
    shampoo_candidates[1].discount_price = 220_000
    assert match_sku(shampoo, shampoo_candidates).product_id == "hair"

    towel = ParsedGroceryItem(raw_text="حوله", name="حوله")
    towel_candidates = [
        _store_item("mop", "حوله‌ای بزرگ کابان باف"),
        _store_item("hand", "حوله دستی کوچک"),
    ]
    towel_candidates[0].discount_price = 100_000
    towel_candidates[1].discount_price = 150_000
    assert match_sku(towel, towel_candidates).product_id == "hand"


def test_generic_wax_rejects_vehicle_polish():
    wax = ParsedGroceryItem(raw_text="واکس", name="واکس")
    candidates = [
        _store_item("car", "واکس و شامپو خودرو"),
        _store_item("shoe", "واکس کفش ساده"),
    ]
    candidates[0].discount_price = 30_000
    candidates[1].discount_price = 45_000
    assert match_sku(wax, candidates).product_id == "shoe"
