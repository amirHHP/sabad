"""
Unit tests for Cart Dispatcher & Payment Handoff.
"""

import asyncio
from sabad.models.catalog import StoreItem
from sabad.models.optimization import StoreOrder, BasketItemAssignment
from sabad.dispatcher.dispatcher import CartDispatcher


def test_cart_dispatcher_handoff():
    order = StoreOrder(
        platform="snapp_market",
        store_id="76576",
        items=[
            BasketItemAssignment(
                item=StoreItem(
                    platform="snapp_market",
                    store_id="76576",
                    product_id="12345",
                    title="شیر کاله",
                    base_price=45000,
                    discount_price=45000
                ),
                quantity=2,
                line_total=90000
            )
        ],
        items_subtotal=90000,
        delivery_fee=25000,
        total_cost=115000
    )

    dispatcher = CartDispatcher()
    handoffs = asyncio.run(dispatcher.dispatch_orders([order]))

    assert len(handoffs) == 1
    h = handoffs[0]
    assert h.platform == "snapp_market"
    assert h.items_count == 1
    assert h.total_amount_tomans == 115000
    assert "https://snapp.market/checkout" in h.web_checkout_url
    assert h.deep_link_url == "snappmarket://cart"
