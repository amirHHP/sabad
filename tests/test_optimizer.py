"""
Unit tests for MILP Basket Optimizer & Flash Deal Trap Auditor.
"""

import pytest
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier
from sabad.optimizer.trap_auditor import TrapAuditor
from sabad.optimizer.milp_solver import MILPBasketOptimizer


def test_flash_deal_trap_auditor():
    """
    Scenario: Store A offers Tuna at 50% discount (saving 30,000 T).
    However, Store A marks up Milk and Cheese by 40,000 T, plus 10,000 T extra shipping.
    Net Advantage = 30,000 - 50,000 = -20,000 T -> CRITICAL_TRAP!
    """
    items = [
        ParsedGroceryItem(raw_text="تن ماهی", name="تن ماهی", quantity=1),
        ParsedGroceryItem(raw_text="شیر", name="شیر", quantity=2),
        ParsedGroceryItem(raw_text="پنیر", name="پنیر", quantity=1),
    ]

    catalog_matches = {
        "تن ماهی": {
            "store_a": StoreItem(
                platform="store_a", store_id="a", product_id="t1",
                title="تن ماهی شگفت‌انگیز", base_price=80000, discount_price=40000,
                discount_percent=50, is_flash_deal=True
            ),
            "store_b": StoreItem(
                platform="store_b", store_id="b", product_id="t2",
                title="تن ماهی عادی", base_price=70000, discount_price=70000,
                discount_percent=0, is_flash_deal=False
            )
        },
        "شیر": {
            "store_a": StoreItem(
                platform="store_a", store_id="a", product_id="m1",
                title="شیر", base_price=55000, discount_price=55000
            ),
            "store_b": StoreItem(
                platform="store_b", store_id="b", product_id="m2",
                title="شیر", base_price=40000, discount_price=40000
            )
        },
        "پنیر": {
            "store_a": StoreItem(
                platform="store_a", store_id="a", product_id="c1",
                title="پنیر", base_price=60000, discount_price=60000
            ),
            "store_b": StoreItem(
                platform="store_b", store_id="b", product_id="c2",
                title="پنیر", base_price=50000, discount_price=50000
            )
        }
    }

    store_infos = {
        "store_a": StoreInfo(
            platform="store_a", store_id="a", title="فروشگاه الف",
            delivery_tiers=[DeliveryTier(min_subtotal=0, max_subtotal=None, fee=35000)]
        ),
        "store_b": StoreInfo(
            platform="store_b", store_id="b", title="فروشگاه ب",
            delivery_tiers=[DeliveryTier(min_subtotal=0, max_subtotal=None, fee=25000)]
        )
    }

    report = TrapAuditor.audit_deals(items, catalog_matches, store_infos)
    assert report.has_traps is True
    assert len(report.audited_deals) == 1
    audit_deal = report.audited_deals[0]
    assert audit_deal.verdict == "CRITICAL_TRAP"
    assert audit_deal.net_advantage < 0


def test_milp_optimizer_split_decision():
    """
    Scenario: Store A has cheap Milk. Store B has cheap Detergent.
    The savings of buying both from their cheapest vendor exceed the coordination penalty.
    """
    items = [
        ParsedGroceryItem(raw_text="شیر", name="شیر", quantity=2),
        ParsedGroceryItem(raw_text="مایع ظرفشویی", name="مایع ظرفشویی", quantity=1),
    ]

    catalog_matches = {
        "شیر": {
            "snapp": StoreItem(
                platform="snapp", store_id="s1", product_id="m1",
                title="شیر", base_price=30000, discount_price=30000
            ),
            "jet": StoreItem(
                platform="jet", store_id="j1", product_id="m2",
                title="شیر", base_price=80000, discount_price=80000
            )
        },
        "مایع ظرفشویی": {
            "snapp": StoreItem(
                platform="snapp", store_id="s1", product_id="d1",
                title="مایع ظرفشویی", base_price=160000, discount_price=160000
            ),
            "jet": StoreItem(
                platform="jet", store_id="j1", product_id="d2",
                title="مایع ظرفشویی", base_price=60000, discount_price=60000
            )
        }
    }

    store_infos = {
        "snapp": StoreInfo(
            platform="snapp", store_id="s1", title="اسنپ",
            delivery_tiers=[DeliveryTier(min_subtotal=0, fee=20000)]
        ),
        "jet": StoreInfo(
            platform="jet", store_id="j1", title="جت",
            delivery_tiers=[DeliveryTier(min_subtotal=0, fee=20000)]
        )
    }

    optimizer = MILPBasketOptimizer(split_penalty_tomans=10000)
    result = optimizer.optimize(items, catalog_matches, store_infos, allow_multi_store=True)

    assert result.is_multi_store is True
    assert len(result.optimal_orders) == 2
    # Check that Snapp gets Milk and Jet gets Detergent
    snapp_order = next(o for o in result.optimal_orders if o.platform == "snapp")
    jet_order = next(o for o in result.optimal_orders if o.platform == "jet")
    assert snapp_order.items[0].item.title == "شیر"
    assert jet_order.items[0].item.title == "مایع ظرفشویی"
