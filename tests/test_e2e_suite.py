"""
4-Tier Opaque-Box Comprehensive End-to-End Test Suite for Sabad.
Tier 1: Feature Coverage (End-to-End Pipeline)
Tier 2: Boundary & Corner Cases
Tier 3: Combinatorial Pairwise
Tier 4: Real-World Scenarios (Flash Deal Trap & Multi-Store Split)
"""

import pytest
import asyncio
from sabad.normalizer.parser import parse_grocery_input
from sabad.normalizer.matcher import match_sku
from sabad.optimizer.milp_solver import MILPBasketOptimizer
from sabad.dispatcher.dispatcher import CartDispatcher
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier


# -------------------------------------------------------------
# Tier 1: Feature Coverage
# -------------------------------------------------------------
def test_tier1_feature_coverage():
    """Validates complete pipeline from Persian raw text to checkout handoff."""
    raw_text = "دو تا شیر پرچرب کاله یک لیتری، یه پنیر ویلی ۳۵۰ گرمی"
    basket = parse_grocery_input(raw_text)
    assert len(basket.items) == 2

    # Simulated candidate pools
    milk_candidates = [
        StoreItem(platform="snapp_market", store_id="s1", product_id="101", title="شیر پرچرب کاله 1 لیتری", base_price=45000, discount_price=45000),
        StoreItem(platform="digikala_jet", store_id="j1", product_id="201", title="شیر پرچرب کاله 1 لیتری", base_price=44000, discount_price=44000),
    ]
    cheese_candidates = [
        StoreItem(platform="snapp_market", store_id="s1", product_id="102", title="پنیر ویلی 350 گرمی", base_price=60000, discount_price=55000),
        StoreItem(platform="digikala_jet", store_id="j1", product_id="202", title="پنیر ویلی 350 گرمی", base_price=62000, discount_price=60000),
    ]

    catalog_matches = {
        basket.items[0].raw_text: {
            "snapp_market": match_sku(basket.items[0], milk_candidates),
            "digikala_jet": match_sku(basket.items[0], [c for c in milk_candidates if c.platform == "digikala_jet"]),
        },
        basket.items[1].raw_text: {
            "snapp_market": match_sku(basket.items[1], cheese_candidates),
            "digikala_jet": match_sku(basket.items[1], [c for c in cheese_candidates if c.platform == "digikala_jet"]),
        }
    }

    store_infos = {
        "snapp_market": StoreInfo(platform="snapp_market", store_id="s1", title="اسنپ", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=25000)]),
        "digikala_jet": StoreInfo(platform="digikala_jet", store_id="j1", title="جت", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=25000)]),
    }

    optimizer = MILPBasketOptimizer(split_penalty_tomans=20000)
    result = optimizer.optimize(basket.items, catalog_matches, store_infos)

    assert result.grand_total_cost > 0
    assert len(result.optimal_orders) >= 1

    dispatcher = CartDispatcher()
    handoffs = asyncio.run(dispatcher.dispatch_orders(result.optimal_orders))
    assert len(handoffs) == len(result.optimal_orders)


# -------------------------------------------------------------
# Tier 2: Boundary & Corner Cases
# -------------------------------------------------------------
def test_tier2_boundary_single_item_basket():
    """Single item with quantity 1."""
    basket = parse_grocery_input("یه شیر")
    assert len(basket.items) == 1
    assert basket.items[0].quantity == 1

    catalog_matches = {
        "یه شیر": {
            "s1": StoreItem(platform="s1", store_id="s1", product_id="1", title="شیر", base_price=30000, discount_price=30000)
        }
    }
    store_infos = {"s1": StoreInfo(platform="s1", store_id="s1", title="فروشگاه", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=20000)])}
    optimizer = MILPBasketOptimizer()
    result = optimizer.optimize(basket.items, catalog_matches, store_infos)
    assert result.grand_total_cost == 50000


def test_tier2_corner_case_missing_item_in_store():
    """Store B has item 1 but is missing item 2."""
    basket = parse_grocery_input("شیر، پنیر")
    catalog_matches = {
        "شیر": {
            "store_a": StoreItem(platform="store_a", store_id="a", product_id="1", title="شیر", base_price=30000, discount_price=30000),
            "store_b": StoreItem(platform="store_b", store_id="b", product_id="2", title="شیر", base_price=28000, discount_price=28000),
        },
        "پنیر": {
            "store_a": StoreItem(platform="store_a", store_id="a", product_id="3", title="پنیر", base_price=50000, discount_price=50000),
            "store_b": None,  # Out of stock
        }
    }
    store_infos = {
        "store_a": StoreInfo(platform="store_a", store_id="a", title="A", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=20000)]),
        "store_b": StoreInfo(platform="store_b", store_id="b", title="B", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=20000)]),
    }
    optimizer = MILPBasketOptimizer()
    result = optimizer.optimize(basket.items, catalog_matches, store_infos)
    # Store B cannot fulfill 100% of basket
    assert result.single_store_orders["store_b"].missing_items_count == 1
    # Store A fulfills 100%
    assert result.single_store_orders["store_a"].missing_items_count == 0


# -------------------------------------------------------------
# Tier 3: Combinatorial Pairwise
# -------------------------------------------------------------
@pytest.mark.parametrize("store_a_fee,store_b_fee,expected_winning_store", [
    (10000, 30000, "store_a"),
    (40000, 15000, "store_b"),
])
def test_tier3_combinatorial_shipping_impact(store_a_fee, store_b_fee, expected_winning_store):
    """Verifies that delivery fee differences correctly swing single-store optimality."""
    basket = parse_grocery_input("شیر")
    catalog_matches = {
        "شیر": {
            "store_a": StoreItem(platform="store_a", store_id="a", product_id="1", title="شیر", base_price=40000, discount_price=40000),
            "store_b": StoreItem(platform="store_b", store_id="b", product_id="2", title="شیر", base_price=40000, discount_price=40000),
        }
    }
    store_infos = {
        "store_a": StoreInfo(platform="store_a", store_id="a", title="A", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=store_a_fee)]),
        "store_b": StoreInfo(platform="store_b", store_id="b", title="B", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=store_b_fee)]),
    }
    optimizer = MILPBasketOptimizer()
    result = optimizer.optimize(basket.items, catalog_matches, store_infos)
    assert result.optimal_orders[0].platform == expected_winning_store


# -------------------------------------------------------------
# Tier 4: Real-World Scenarios
# -------------------------------------------------------------
def test_tier4_severe_marketing_trap_scenario():
    """
    Real-world marketing trap: Store X cuts Tuna by 40% (saves 30,000 T).
    Remaining 4 items are marked up by 50,000 T total.
    The Flash Deal Trap Auditor must flag CRITICAL_TRAP and recommend consolidated Store Y.
    """
    basket = parse_grocery_input("تن ماهی، برنج، روغن، قند")
    catalog_matches = {
        "تن ماهی": {
            "store_x": StoreItem(platform="store_x", store_id="x", product_id="1", title="تن ماهی شگفت‌انگیز", base_price=80000, discount_price=48000, is_flash_deal=True, discount_percent=40),
            "store_y": StoreItem(platform="store_y", store_id="y", product_id="2", title="تن ماهی عادی", base_price=78000, discount_price=78000),
        },
        "برنج": {
            "store_x": StoreItem(platform="store_x", store_id="x", product_id="3", title="برنج", base_price=220000, discount_price=220000),
            "store_y": StoreItem(platform="store_y", store_id="y", product_id="4", title="برنج", base_price=190000, discount_price=190000),
        },
        "روغن": {
            "store_x": StoreItem(platform="store_x", store_id="x", product_id="5", title="روغن", base_price=95000, discount_price=95000),
            "store_y": StoreItem(platform="store_y", store_id="y", product_id="6", title="روغن", base_price=85000, discount_price=85000),
        },
        "قند": {
            "store_x": StoreItem(platform="store_x", store_id="x", product_id="7", title="قند", base_price=55000, discount_price=55000),
            "store_y": StoreItem(platform="store_y", store_id="y", product_id="8", title="قند", base_price=45000, discount_price=45000),
        }
    }
    store_infos = {
        "store_x": StoreInfo(platform="store_x", store_id="x", title="Store X", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=30000)]),
        "store_y": StoreInfo(platform="store_y", store_id="y", title="Store Y", delivery_tiers=[DeliveryTier(min_subtotal=0, fee=25000)]),
    }

    optimizer = MILPBasketOptimizer()
    result = optimizer.optimize(basket.items, catalog_matches, store_infos)

    # Trap Auditor must detect the trap
    assert result.trap_audit.has_traps is True
    assert result.trap_audit.audited_deals[0].verdict == "CRITICAL_TRAP"

    # Single store Y is cheaper overall than single store X
    assert result.single_store_orders["store_y"].total_cost < result.single_store_orders["store_x"].total_cost
