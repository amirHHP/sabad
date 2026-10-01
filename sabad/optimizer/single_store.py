"""
Single-Store Fulfillment Evaluator.
Calculates 100% basket costs per platform with tiered shipping fees and MOV constraints.
"""

from typing import Dict, List, Optional
from sabad.models.catalog import StoreItem, StoreInfo
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.optimization import StoreOrder, BasketItemAssignment


def calculate_delivery_fee(subtotal: float, store_info: StoreInfo) -> float:
    """Calculates shipping fee based on store delivery tiers."""
    for tier in store_info.delivery_tiers:
        if tier.max_subtotal is None:
            if subtotal >= tier.min_subtotal:
                return tier.fee
        elif tier.min_subtotal <= subtotal < tier.max_subtotal:
            return tier.fee
    return 30000.0  # Default fallback shipping fee in Tomans


def evaluate_single_store(
    platform: str,
    basket_items: List[ParsedGroceryItem],
    catalog_matches: Dict[str, Dict[str, Optional[StoreItem]]],
    store_info: StoreInfo,
) -> Optional[StoreOrder]:
    """
    Evaluates fulfilling the basket entirely from a single platform.
    Returns StoreOrder or None if store has 0 matched items.
    """
    assignments: List[BasketItemAssignment] = []
    subtotal = 0.0
    total_savings = 0.0
    missing_count = 0

    for item in basket_items:
        key = item.raw_text
        match = catalog_matches.get(key, {}).get(platform)
        if match and match.is_in_stock:
            line_cost = match.discount_price * item.quantity
            line_saving = match.saving_amount * item.quantity
            subtotal += line_cost
            total_savings += line_saving
            assignments.append(BasketItemAssignment(
                item=match,
                quantity=item.quantity,
                line_total=line_cost,
                nominal_saving=line_saving
            ))
        else:
            missing_count += 1

    if not assignments:
        return None

    delivery_fee = calculate_delivery_fee(subtotal, store_info)
    total_cost = subtotal + delivery_fee
    meets_mov = subtotal >= store_info.minimum_order_value

    return StoreOrder(
        platform=platform,
        store_id=store_info.store_id,
        items=assignments,
        items_subtotal=subtotal,
        delivery_fee=delivery_fee,
        total_cost=total_cost,
        total_savings=total_savings,
        minimum_order_value=store_info.minimum_order_value,
        meets_mov=meets_mov,
        missing_items_count=missing_count
    )
