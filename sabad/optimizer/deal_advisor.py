"""
Flash Deal Opportunity Advisor ("مشاور هوشمند تخفیف‌های شگفت‌انگیز").
Analyzes daily 40%-70% promotional flash deals across online supermarkets and identifies
high-value economic opportunities for the shopper:
1. Same-Store Addon: Add high-discount flash deal items from the current winning store at a low price
   without incurring extra delivery fees (or even reducing fees by unlocking free delivery tiers).
2. Store Switch Deal: Switch the entire basket to an alternative store where adding a 70% super-deal
   makes the overall basket substantially more profitable and economical than before.
"""

import re
from typing import Dict, List, Optional, Tuple
from sabad.models.catalog import StoreItem, StoreInfo
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.optimization import (
    StoreOrder,
    FlashDealOpportunity,
    BasketItemAssignment,
    OptimizationResult,
)
from sabad.optimizer.single_store import calculate_delivery_fee
from sabad.ui_assets import get_default_flash_deals


class FlashDealAdvisor:
    """
    Intelligent Opportunity Engine for daily 40%-70% Flash Deals ("پیشنهادهای شگفت‌انگیز").
    """

    @classmethod
    def find_opportunities(
        cls,
        basket_items: List[ParsedGroceryItem],
        catalog_matches: Dict[str, Dict[str, Optional[StoreItem]]],
        store_infos: Dict[str, StoreInfo],
        single_store_orders: Dict[str, Optional[StoreOrder]],
        optimal_orders: List[StoreOrder],
        flash_deals_by_store: Optional[Dict[str, List[StoreItem]]] = None,
        min_discount_percent: float = 40.0,
    ) -> List[FlashDealOpportunity]:
        """
        Scans all available flash deals and evaluates actionable economic opportunities
        relative to the user's current basket and store selection.
        """
        opportunities: List[FlashDealOpportunity] = []

        if not store_infos:
            return opportunities

        # 1. Collect and harmonise all candidate deals per store platform
        candidate_deals = cls._collect_candidate_deals(
            store_infos=store_infos,
            catalog_matches=catalog_matches,
            flash_deals_by_store=flash_deals_by_store,
            min_discount_percent=min_discount_percent,
        )

        # 2. Determine current basket financial baseline
        current_grand_total = sum(o.total_cost for o in optimal_orders) if optimal_orders else 0.0
        current_savings = sum(o.total_savings for o in optimal_orders) if optimal_orders else 0.0

        primary_store: Optional[str] = None
        if optimal_orders:
            # Pick the store carrying the largest subtotal as primary
            primary_order = max(optimal_orders, key=lambda o: o.items_subtotal, default=optimal_orders[0])
            primary_store = primary_order.platform
        elif single_store_orders:
            feasible = [o for o in single_store_orders.values() if o and o.missing_items_count == 0]
            if feasible:
                primary_store = min(feasible, key=lambda o: o.total_cost).platform

        # 3. Scenario A: Same-Store High-Discount Addon
        same_store_opps = cls._find_same_store_addons(
            optimal_orders=optimal_orders,
            candidate_deals=candidate_deals,
            store_infos=store_infos,
            basket_items=basket_items,
            current_grand_total=current_grand_total,
            current_savings=current_savings,
        )
        opportunities.extend(same_store_opps)

        # 4. Scenario B: Store Switch + Super Deal Opportunity (40% - 70% discounts)
        if primary_store and single_store_orders:
            switch_opps = cls._find_store_switch_opportunities(
                primary_store=primary_store,
                optimal_orders=optimal_orders,
                single_store_orders=single_store_orders,
                candidate_deals=candidate_deals,
                store_infos=store_infos,
                basket_items=basket_items,
                current_grand_total=current_grand_total,
                current_savings=current_savings,
            )
            opportunities.extend(switch_opps)

        return opportunities

    @classmethod
    def _collect_candidate_deals(
        cls,
        store_infos: Dict[str, StoreInfo],
        catalog_matches: Dict[str, Dict[str, Optional[StoreItem]]],
        flash_deals_by_store: Optional[Dict[str, List[StoreItem]]],
        min_discount_percent: float,
    ) -> Dict[str, List[StoreItem]]:
        """Aggregates and deduplicates candidate flash deals from live feeds, catalog matches, and curated deals."""
        curated_deals = get_default_flash_deals()
        collected: Dict[str, List[StoreItem]] = {s: [] for s in store_infos.keys()}

        for s_name in store_infos.keys():
            seen_ids = set()

            # Source 1: Live harvested deals
            if flash_deals_by_store and s_name in flash_deals_by_store:
                for item in flash_deals_by_store[s_name]:
                    if item.is_in_stock and item.discount_percent >= min_discount_percent and item.product_id not in seen_ids:
                        seen_ids.add(item.product_id)
                        collected[s_name].append(item)

            # Source 2: Items in catalog matches marked as flash deals or high discounts
            if catalog_matches:
                for matches in catalog_matches.values():
                    if not matches:
                        continue
                    store_cand = matches.get(s_name)
                    if store_cand and store_cand.is_in_stock and store_cand.discount_percent >= min_discount_percent:
                        if store_cand.product_id not in seen_ids:
                            seen_ids.add(store_cand.product_id)
                            collected[s_name].append(store_cand)

            # Source 3: Curated fallback deals (ensures 40%-70% wonder deals are always available)
            if s_name in curated_deals:
                for c_item in curated_deals[s_name]:
                    if c_item.product_id not in seen_ids and c_item.discount_percent >= min_discount_percent:
                        seen_ids.add(c_item.product_id)
                        collected[s_name].append(c_item)

        return collected

    @classmethod
    def _is_already_in_basket(
        cls,
        deal: StoreItem,
        basket_items: List[ParsedGroceryItem],
        optimal_orders: List[StoreOrder],
    ) -> bool:
        """Checks whether a flash deal item is already requested or assigned in the cart."""
        deal_id = (deal.product_id or "").strip()
        deal_title = (deal.title or "").strip().lower()

        # Check existing orders
        for order in optimal_orders:
            for asgn in order.items:
                if asgn.item.product_id == deal_id:
                    return True
                if asgn.item.title.strip().lower() == deal_title:
                    return True

        deal_words = set(re.findall(r'[\w]+', deal_title))

        # Check requested basket items with exact token boundary matching
        for b_item in basket_items:
            b_name = (b_item.name or "").strip().lower()
            b_brand = (b_item.brand or "").strip().lower()
            raw_text = (b_item.raw_text or "").strip().lower()

            if not b_name and not raw_text:
                continue

            if raw_text and raw_text == deal_title:
                return True

            name_words = re.findall(r'[\w]+', b_name)
            if name_words and all(w in deal_words for w in name_words):
                if not b_brand or (b_brand in deal_words):
                    return True

        return False

    @classmethod
    def _find_same_store_addons(
        cls,
        optimal_orders: List[StoreOrder],
        candidate_deals: Dict[str, List[StoreItem]],
        store_infos: Dict[str, StoreInfo],
        basket_items: List[ParsedGroceryItem],
        current_grand_total: float,
        current_savings: float,
    ) -> List[FlashDealOpportunity]:
        """Finds high-discount add-on opportunities within the currently assigned stores."""
        opps: List[FlashDealOpportunity] = []

        for order in optimal_orders:
            s_name = order.platform
            s_info = store_infos.get(s_name)
            store_title = s_info.title if s_info else s_name
            deals = candidate_deals.get(s_name, [])

            for deal in deals:
                if cls._is_already_in_basket(deal, basket_items, optimal_orders):
                    continue

                old_subtotal = order.items_subtotal
                old_deliv = order.delivery_fee
                new_subtotal = old_subtotal + deal.discount_price
                new_deliv = calculate_delivery_fee(new_subtotal, s_info) if s_info else old_deliv

                deliv_delta = new_deliv - old_deliv
                additional_cost = deal.discount_price + deliv_delta
                nominal_saving = deal.saving_amount

                projected_cost = current_grand_total + additional_cost
                projected_savings = current_savings + nominal_saving - deliv_delta
                net_profit_inc = nominal_saving - deliv_delta

                is_cheaper = projected_cost <= current_grand_total

                benefit_text = (
                    f"بدون هزینه ارسال اضافه ({new_deliv:,.0f} تومان) "
                    f"و ذخیره {nominal_saving:,.0f} تومان سود تخفیف"
                )
                if deliv_delta < 0:
                    benefit_text = (
                        f"🎉 با رسیدن به سقف سفارش، هزینه ارسال {abs(deliv_delta):,.0f} تومان کاهش یافت!"
                    )

                message = (
                    f"🎉 تخفیف شگفت‌انگیز {deal.discount_percent:.0f}٪ از همین فروشگاه ({store_title})! "
                    f"کالای «{deal.title}» با قیمت استثنایی {deal.discount_price:,.0f} تومان "
                    f"(به‌جای {deal.base_price:,.0f} تومان) بدون هزینه ارسال مازاد در دسترس است."
                )

                opps.append(
                    FlashDealOpportunity(
                        opportunity_type="same_store_addon",
                        deal_item=deal,
                        target_store=s_name,
                        target_store_title=store_title,
                        current_store=s_name,
                        current_store_title=store_title,
                        deal_discount_percent=deal.discount_percent,
                        deal_base_price=deal.base_price,
                        deal_discount_price=deal.discount_price,
                        deal_nominal_saving=nominal_saving,
                        current_basket_cost=current_grand_total,
                        projected_basket_cost=projected_cost,
                        current_basket_savings=current_savings,
                        projected_basket_savings=projected_savings,
                        net_profit_increase=net_profit_inc,
                        is_cheaper_total=is_cheaper,
                        title_fa="پیشنهاد شگفت‌انگیز از همین فروشگاه",
                        message_fa=message,
                        badge_fa=f"%{deal.discount_percent:.0f} تخفیف از همین فروشگاه",
                        action_label_fa=f"➕ افزودن به سبد ({deal.discount_price:,.0f} ت)",
                    )
                )

        # Sort by discount percent descending, then net profit increase descending
        opps.sort(key=lambda o: (o.deal_discount_percent, o.net_profit_increase), reverse=True)
        return opps[:3]

    @classmethod
    def _find_store_switch_opportunities(
        cls,
        primary_store: str,
        optimal_orders: List[StoreOrder],
        single_store_orders: Dict[str, Optional[StoreOrder]],
        candidate_deals: Dict[str, List[StoreItem]],
        store_infos: Dict[str, StoreInfo],
        basket_items: List[ParsedGroceryItem],
        current_grand_total: float,
        current_savings: float,
    ) -> List[FlashDealOpportunity]:
        """
        Evaluates switching to an alternative store where adding a 40%-70% deal
        renders the total basket significantly more profitable or cheaper than before.
        """
        opps: List[FlashDealOpportunity] = []
        curr_info = store_infos.get(primary_store)
        curr_title = curr_info.title if curr_info else primary_store

        for alt_store, alt_order in single_store_orders.items():
            # If current solution is single-store at alt_store, skip. If multi-store, allow consolidating into alt_store.
            if len(optimal_orders) == 1 and alt_store == optimal_orders[0].platform:
                continue

            if not alt_order:
                continue

            # Must be capable of fulfilling 100% of the user's requested basket items
            if alt_order.missing_items_count > 0:
                continue

            alt_info = store_infos.get(alt_store)
            alt_title = alt_info.title if alt_info else alt_store
            alt_deals = candidate_deals.get(alt_store, [])

            for deal in alt_deals:
                if cls._is_already_in_basket(deal, basket_items, optimal_orders):
                    continue

                # Target high discount range (40% to 70%+)
                if deal.discount_percent < 40.0:
                    continue

                alt_subtotal = alt_order.items_subtotal + deal.discount_price
                alt_deliv = calculate_delivery_fee(alt_subtotal, alt_info) if alt_info else alt_order.delivery_fee
                projected_cost = alt_subtotal + alt_deliv

                nominal_saving = deal.saving_amount
                projected_savings = alt_order.total_savings + nominal_saving

                cost_delta = projected_cost - current_grand_total
                savings_delta = projected_savings - current_savings
                net_profit_inc = savings_delta - max(0.0, cost_delta)
                is_cheaper = projected_cost <= current_grand_total

                # Economic Advantage Criteria (protects against marketing markup traps):
                # 1. Cheaper total payment even with the deal item included!
                # 2. Or competitor's baseline basket is cheaper/comparable (not ripping off the user on baseline items),
                #    and the super-deal (40%-70%) provides substantial net value.
                basket_cost_diff = alt_order.total_cost - current_grand_total
                is_advantageous = False
                if is_cheaper:
                    is_advantageous = True
                elif basket_cost_diff <= 10000 and (deal.saving_amount - max(0.0, cost_delta)) >= 15000 and deal.discount_percent >= 40.0:
                    is_advantageous = True

                if not is_advantageous:
                    continue

                if is_cheaper:
                    profit_desc = f"حتی با احتساب این کالا، مبلغ کل سبد {abs(cost_delta):,.0f} تومان ارزان‌تر می‌شود!"
                else:
                    profit_desc = f"سود تخفیف‌های سبد شما {savings_delta:,.0f} تومان افزایش می‌یابد ({net_profit_inc:,.0f} تومان ارزش خالص مازاد)."

                message = (
                    f"🔄 فرصت طلایی تغییر فروشگاه: اگر خرید خود را به «{alt_title}» منتقل کرده و کالای "
                    f"شگفت‌انگیز «{deal.title}» با تخفیف {deal.discount_percent:.0f}٪ را نیز به سبد اضافه کنید، "
                    f"جمع سبد شما بسیار سودآورتر خواهد شد! {profit_desc}"
                )

                opps.append(
                    FlashDealOpportunity(
                        opportunity_type="store_switch_deal",
                        deal_item=deal,
                        target_store=alt_store,
                        target_store_title=alt_title,
                        current_store=primary_store,
                        current_store_title=curr_title,
                        deal_discount_percent=deal.discount_percent,
                        deal_base_price=deal.base_price,
                        deal_discount_price=deal.discount_price,
                        deal_nominal_saving=nominal_saving,
                        current_basket_cost=current_grand_total,
                        projected_basket_cost=projected_cost,
                        current_basket_savings=current_savings,
                        projected_basket_savings=projected_savings,
                        net_profit_increase=net_profit_inc,
                        is_cheaper_total=is_cheaper,
                        title_fa="فرصت طلایی تغییر فروشگاه به همراه تخفیف شگفت‌انگیز",
                        message_fa=message,
                        badge_fa=f"🔥 تغییر به {alt_title} با %{deal.discount_percent:.0f} تخفیف",
                        action_label_fa=f"🔄 تغییر به {alt_title} و افزودن کالا",
                    )
                )

        # Sort store switch opportunities: cheaper total first, then highest net profit increase
        opps.sort(key=lambda o: (o.is_cheaper_total, o.net_profit_increase, o.deal_discount_percent), reverse=True)
        return opps[:2]

    @classmethod
    def apply_opportunity(
        cls,
        opt_result: OptimizationResult,
        opportunity: FlashDealOpportunity,
        store_infos: Dict[str, StoreInfo],
        basket_items: List[ParsedGroceryItem],
        catalog_matches: Dict[str, Dict[str, Optional[StoreItem]]],
    ) -> Tuple[OptimizationResult, List[ParsedGroceryItem], Dict[str, Dict[str, Optional[StoreItem]]]]:
        """
        Applies a flash deal opportunity directly to the active optimization result:
        - For 'same_store_addon': appends item to winning store order, updates delivery fee & totals.
        - For 'store_switch_deal': transfers the basket to the target store, adds deal item, updates totals.
        Returns the updated (opt_result, basket_items, catalog_matches).
        """
        deal_grocery_item = ParsedGroceryItem(
            raw_text=opportunity.deal_item.title,
            name=opportunity.deal_item.title,
            brand=opportunity.deal_item.brand,
            quantity=1,
            display_title=opportunity.deal_item.title,
        )
        updated_basket_items = list(basket_items or []) + [deal_grocery_item]

        updated_catalog_matches = dict(catalog_matches or {})
        updated_catalog_matches[deal_grocery_item.raw_text] = {
            opportunity.target_store: opportunity.deal_item
        }

        asgn = BasketItemAssignment(
            item=opportunity.deal_item,
            quantity=1,
            line_total=opportunity.deal_discount_price,
            nominal_saving=opportunity.deal_nominal_saving,
        )

        s_info = store_infos.get(opportunity.target_store)

        if opportunity.opportunity_type == "same_store_addon":
            # Add to matching order in optimal_orders
            target_order = None
            for ord_item in opt_result.optimal_orders:
                if ord_item.platform == opportunity.target_store:
                    target_order = ord_item
                    break

            if target_order:
                target_order.items.append(asgn)
                target_order.items_subtotal += opportunity.deal_discount_price
                if s_info:
                    target_order.delivery_fee = calculate_delivery_fee(target_order.items_subtotal, s_info)
                    target_order.meets_mov = target_order.items_subtotal >= s_info.minimum_order_value
                target_order.total_cost = target_order.items_subtotal + target_order.delivery_fee
                target_order.total_savings += opportunity.deal_nominal_saving

            # Also update single store orders cache if present (and distinct from target_order)
            single_ord = opt_result.single_store_orders.get(opportunity.target_store)
            if single_ord and single_ord is not target_order:
                single_ord.items.append(asgn)
                single_ord.items_subtotal += opportunity.deal_discount_price
                if s_info:
                    single_ord.delivery_fee = calculate_delivery_fee(single_ord.items_subtotal, s_info)
                    single_ord.meets_mov = single_ord.items_subtotal >= s_info.minimum_order_value
                single_ord.total_cost = single_ord.items_subtotal + single_ord.delivery_fee
                single_ord.total_savings += opportunity.deal_nominal_saving

            opt_result.total_items_cost = sum(o.items_subtotal for o in opt_result.optimal_orders)
            opt_result.total_delivery_fees = sum(o.delivery_fee for o in opt_result.optimal_orders)
            opt_result.grand_total_cost = sum(o.total_cost for o in opt_result.optimal_orders)
            opt_result.total_discounts_saved = sum(o.total_savings for o in opt_result.optimal_orders)

        elif opportunity.opportunity_type == "store_switch_deal":
            target_store = opportunity.target_store
            single_ord = opt_result.single_store_orders.get(target_store)
            if single_ord:
                new_items = list(single_ord.items) + [asgn]
                new_subtotal = single_ord.items_subtotal + opportunity.deal_discount_price
                new_deliv = calculate_delivery_fee(new_subtotal, s_info) if s_info else single_ord.delivery_fee
                new_total = new_subtotal + new_deliv
                new_savings = single_ord.total_savings + opportunity.deal_nominal_saving
                meets_mov = (new_subtotal >= s_info.minimum_order_value) if s_info else True

                switched_order = StoreOrder(
                    platform=target_store,
                    store_id=single_ord.store_id,
                    items=new_items,
                    items_subtotal=new_subtotal,
                    delivery_fee=new_deliv,
                    total_cost=new_total,
                    total_savings=new_savings,
                    minimum_order_value=single_ord.minimum_order_value,
                    meets_mov=meets_mov,
                    missing_items_count=0,
                )
                opt_result.optimal_orders = [switched_order]
                opt_result.is_multi_store = False
                opt_result.total_items_cost = new_subtotal
                opt_result.total_delivery_fees = new_deliv
                opt_result.grand_total_cost = new_total
                opt_result.total_discounts_saved = new_savings
                opt_result.single_store_orders[target_store] = switched_order

        # Filter out the applied deal from future recommendations
        opt_result.deal_opportunities = [
            o for o in opt_result.deal_opportunities
            if o.deal_item.product_id != opportunity.deal_item.product_id
        ]

        return opt_result, updated_basket_items, updated_catalog_matches
