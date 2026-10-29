"""Recorded search payloads for the five everyday queries.

Each file is the JSON shape that store's search endpoint returns. The test
parses it with the real adapter so a renamed field fails here instead of
silently emptying the basket.
"""

import json
from pathlib import Path

import httpx
import pytest

from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.tapsi_market import TapsiMarketAdapter
from sabad.models.grocery import ParsedGroceryItem
from sabad.normalizer.matcher import explain_sku_candidates, match_sku
from sabad.search_explanations import explain_missing_item

ROOT = Path(__file__).parent / "fixtures"
PLATFORMS = {
    "snapp_market": SnappMarketAdapter,
    "digikala_jet": DigikalaJetAdapter,
    "okala": OkalaAdapter,
    "tapsi_market": TapsiMarketAdapter,
}
QUERIES = {
    "shampoo": ParsedGroceryItem(raw_text="شامپو", name="شامپو"),
    "towel": ParsedGroceryItem(raw_text="حوله", name="حوله"),
    "wax": ParsedGroceryItem(raw_text="واکس", name="واکس"),
    "pasta": ParsedGroceryItem(raw_text="ماکارونی", name="ماکارونی"),
    "eggs": ParsedGroceryItem(raw_text="تخم مرغ", name="تخم مرغ"),
}
EXPECTED = {
    "shampoo": "s1000",
    "towel": "hand",
    "wax": "shoe",
    "pasta": "p700",
    "eggs": "e20",
}


def _load(platform: str, product: str) -> dict:
    return json.loads((ROOT / platform / f"{product}.json").read_text(encoding="utf-8"))


def _client(payload: dict) -> httpx.AsyncClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", list(PLATFORMS))
@pytest.mark.parametrize("product", list(QUERIES))
async def test_fixture_parses_to_the_expected_product(platform, product):
    adapter = PLATFORMS[platform]()
    adapter.client = _client(_load(platform, product))
    if platform == "okala":
        adapter._cached_store_id = "2319"

    items = await adapter.search(QUERIES[product].name, 35.72, 51.40)
    await adapter.client.aclose()

    assert items, f"{platform} {product} fixture produced no items"
    assert all(item.discount_price > 0 for item in items)
    selected = match_sku(QUERIES[product], items)
    assert selected is not None
    assert selected.product_id == EXPECTED[product]
    if product == "towel":
        assert selected.is_in_stock is False
        evidence = explain_sku_candidates(QUERIES[product], items)
        evidence["selected"] = selected.title
        evidence["selected_in_stock"] = False
        text = explain_missing_item(evidence, requested_title=selected.title, product_name="حوله")
        assert text == "حوله پیدا شد، اما حوله دستی کوچک در این شعبه موجود نبود؛ ۳ نتیجهٔ نامرتبط حذف شد."
