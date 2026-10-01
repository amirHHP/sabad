"""
Multi-Store Cart Dispatcher & Payment Gateway Handoff.
Dispatches mutations to target store carts and generates direct checkout links.
"""

import asyncio
from typing import Dict, List, Optional
from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
from sabad.models.optimization import StoreOrder
from sabad.models.dispatch import (
    CartItemMutation,
    CartMutationResult,
    CheckoutHandoff,
)


class CartDispatcher:
    """Orchestrates concurrent cart mutations and payment gateway handoff."""

    def __init__(self, adapters: Optional[Dict[str, BaseStoreAdapter]] = None):
        self.adapters = adapters or {
            "snapp_market": SnappMarketAdapter(),
            "digikala_jet": DigikalaJetAdapter(),
            "okala": OkalaAdapter(),
        }

    async def dispatch_orders(self, orders: List[StoreOrder]) -> List[CheckoutHandoff]:
        """
        Executes mutations concurrently across all winning stores.
        Returns checkout handoff payloads for the user to complete payment.
        """
        tasks = [self._dispatch_single_order(order) for order in orders]
        handoffs = await asyncio.gather(*tasks)
        return handoffs

    async def _dispatch_single_order(self, order: StoreOrder) -> CheckoutHandoff:
        adapter = self.adapters.get(order.platform)
        if not adapter:
            raise ValueError(f"Unknown platform: {order.platform}")

        # Build mutations list
        mutations = [
            CartItemMutation(
                product_id=assignment.item.product_id,
                quantity=assignment.quantity,
                store_id=order.store_id
            )
            for assignment in order.items
        ]

        mutation_result: Optional[CartMutationResult] = None
        if adapter.is_authenticated():
            try:
                mutation_result = await adapter.add_to_cart(mutations)
            except Exception as e:
                mutation_result = CartMutationResult(
                    platform=order.platform,
                    store_id=order.store_id,
                    success=False,
                    error_message=f"خطا در ارسال به سبد: {e}"
                )
        else:
            mutation_result = CartMutationResult(
                platform=order.platform,
                store_id=order.store_id,
                success=False,
                error_message="کاربر لاگین نکرده است (نیاز به شماره تلفن و کد تایید)."
            )

        web_url = adapter.get_checkout_url(order.store_id)
        
        deep_links = {
            "snapp_market": "snappmarket://cart",
            "digikala_jet": "digikalajet://cart",
            "okala": "okala://cart",
        }

        summary = (
            f"سفارش {adapter.platform_title_fa}: شامل {len(order.items)} قلم کالا "
            f"به مبلغ کل {order.total_cost:,.0f} تومان (شامل {order.delivery_fee:,.0f} تومان ارسال)."
        )

        return CheckoutHandoff(
            platform=order.platform,
            platform_fa=adapter.platform_title_fa,
            web_checkout_url=web_url,
            deep_link_url=deep_links.get(order.platform),
            items_count=len(order.items),
            total_amount_tomans=order.total_cost,
            summary_fa=summary,
            mutation_result=mutation_result
        )
