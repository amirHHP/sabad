"""JSON view of a comparison, shared by the public API and the Next.js app."""

from __future__ import annotations

from typing import Optional

from sabad.models.grocery import ParsedGroceryItem
from sabad.price_history import PriceChange, PriceHistoryStore
from sabad.pricing import comparable_price_text
from sabad.search_explanations import explain_missing_item


def build_compare_view(
    basket_items: list[ParsedGroceryItem],
    catalog_matches: dict,
    search_evidence: dict,
    opt_result,
    price_changes: dict[str, PriceChange],
    platform_titles: dict[str, str],
) -> dict:
    stores = []
    platforms = list(platform_titles) or sorted({
        platform
        for matches in (catalog_matches or {}).values()
        for platform in (matches or {})
    })
    for platform in platforms:
        lines = [
            _line(item, platform, catalog_matches, search_evidence, price_changes)
            for item in basket_items
        ]
        stores.append({
            "platform": platform,
            "title": platform_titles.get(platform, platform),
            "lines": lines,
        })

    optimal_lines = []
    for order in getattr(opt_result, "optimal_orders", []) or []:
        for assignment in order.items or []:
            optimal_lines.append({
                "platform": order.platform,
                "store_title": platform_titles.get(order.platform, order.platform),
                "title": assignment.item.title,
                "product_id": assignment.item.product_id,
                "pack_price": assignment.item.discount_price,
                "unit_price_text": comparable_price_text(assignment.item),
                "quantity": assignment.quantity,
                "line_total": assignment.line_total,
                "price_label": _label(price_changes, assignment.item),
            })

    return {
        "items": [
            {"name": item.name, "raw_text": item.raw_text, "title": item.display_title, "quantity": item.quantity}
            for item in basket_items
        ],
        "stores": stores,
        "optimal_total": getattr(opt_result, "grand_total_cost", None),
        "optimal_lines": optimal_lines,
    }


def _label(price_changes: dict[str, PriceChange], item) -> Optional[str]:
    change = price_changes.get(PriceHistoryStore.item_key(item))
    return change.label if change else None


def _line(item, platform, catalog_matches, search_evidence, price_changes) -> dict:
    match = (catalog_matches or {}).get(item.raw_text, {}).get(platform)
    if match is None:
        match = (catalog_matches or {}).get(item.name, {}).get(platform)
    evidence = (search_evidence or {}).get(item.raw_text, {}).get(platform, {})
    options = evidence.get("unit_options") or []
    if not match or not match.is_in_stock:
        if match and not evidence.get("selected"):
            evidence = {
                **evidence,
                "selected": match.title,
                "selected_in_stock": False,
                "candidate_count": evidence.get("candidate_count") or 1,
            }
        return {
            "requested": item.display_title,
            "requested_name": item.name,
            "found": bool(match),
            "in_stock": False,
            "title": match.title if match else None,
            "product_id": match.product_id if match else None,
            "platform": platform,
            "explanation": explain_missing_item(
                evidence,
                requested_title=item.display_title,
                product_name=item.name,
            ),
            "unit_options": options,
            "unit_price_text": comparable_price_text(match) if match else None,
            "pack_price": match.discount_price if match else None,
            "price_label": _label(price_changes, match) if match else None,
        }
    return {
        "requested": item.display_title,
        "requested_name": item.name,
        "found": True,
        "in_stock": True,
        "title": match.title,
        "product_id": match.product_id,
        "platform": platform,
        "pack_price": match.discount_price,
        "base_price": match.base_price,
        "unit_price_text": comparable_price_text(match),
        "unit_options": options,
        "price_label": _label(price_changes, match),
        "price_verdict": (price_changes.get(PriceHistoryStore.item_key(match)).verdict if price_changes.get(PriceHistoryStore.item_key(match)) else None),
        "product_url": match.product_url,
        "explanation": None,
    }
