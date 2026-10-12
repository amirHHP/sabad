"""
Mathematical Basket Optimizer using Combinatorial Optimization & Mixed-Integer Formulation.
Minimizes: Item Costs + Tiered Delivery Fees + Split Coordination Friction.
"""

from typing import Dict, List, Optional, Tuple
import itertools
from sabad.models.catalog import StoreItem, StoreInfo
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.optimization import (
    OptimizationResult,
    StoreOrder,
    BasketItemAssignment,
    FlashDealOpportunity,
)
from sabad.optimizer.single_store import evaluate_single_store, calculate_delivery_fee
from sabad.optimizer.trap_auditor import TrapAuditor
from sabad.optimizer.deal_advisor import FlashDealAdvisor



class MILPBasketOptimizer:
    """Solves the multi-store grocery allocation optimization problem."""

    def __init__(self, split_penalty_tomans: float = 25000.0):
        self.split_penalty = split_penalty_tomans

    def optimize(
        self,
        basket_items: List[ParsedGroceryItem],
        catalog_matches: Dict[str, Dict[str, Optional[StoreItem]]],
        store_infos: Dict[str, StoreInfo],
        allow_multi_store: bool = True,
        flash_deals_by_store: Optional[Dict[str, List[StoreItem]]] = None,
    ) -> OptimizationResult:
        """
        Runs the complete optimization pipeline:
        1. Single-Store evaluations for SnappMarket, Digikala Jet, and Okala.
        2. Flash Deal Trap Audit.
        3. Combinatorial / MILP Optimization for multi-store split.
        4. Flash Deal Opportunity Advisor (40% to 70% daily deals).
        """
        # Step 1: Single-Store Evaluations
        single_store_orders: Dict[str, Optional[StoreOrder]] = {}
        for s_name, s_info in store_infos.items():
            order = evaluate_single_store(s_name, basket_items, catalog_matches, s_info)
            single_store_orders[s_name] = order

        # Step 2: Trap Audit
        trap_report = TrapAuditor.audit_deals(basket_items, catalog_matches, store_infos)

        feasible_singles = [
            o for o in single_store_orders.values()
            if o and o.missing_items_count == 0 and o.meets_mov
        ]
        
        if not allow_multi_store or not basket_items or not feasible_singles:
            best_single = min(
                (o for o in single_store_orders.values() if o),
                key=lambda o: (o.missing_items_count, o.total_cost),
                default=None
            )
            orders = [best_single] if best_single else []
            deal_opps = FlashDealAdvisor.find_opportunities(
                basket_items=basket_items,
                catalog_matches=catalog_matches,
                store_infos=store_infos,
                single_store_orders=single_store_orders,
                optimal_orders=orders,
                flash_deals_by_store=flash_deals_by_store,
            )
            return self._build_result(orders, single_store_orders, trap_report, is_multi=False, deal_opportunities=deal_opps)

        # Step 3: Solve Combinatorial Optimization
        optimal_orders, is_multi = self._solve_combinatorial(
            basket_items,
            catalog_matches,
            store_infos,
            single_store_orders
        )

        # Step 4: Flash Deal Opportunity Advisor
        deal_opps = FlashDealAdvisor.find_opportunities(
            basket_items=basket_items,
            catalog_matches=catalog_matches,
            store_infos=store_infos,
            single_store_orders=single_store_orders,
            optimal_orders=optimal_orders,
            flash_deals_by_store=flash_deals_by_store,
        )

        return self._build_result(optimal_orders, single_store_orders, trap_report, is_multi=is_multi, deal_opportunities=deal_opps)


    def _solve_combinatorial(
        self,
        basket_items: List[ParsedGroceryItem],
        catalog_matches: Dict[str, Dict[str, Optional[StoreItem]]],
        store_infos: Dict[str, StoreInfo],
        single_orders: Dict[str, Optional[StoreOrder]],
    ) -> Tuple[List[StoreOrder], bool]:
        """
        Exact combinatorial evaluation across store assignments.
        Guarantees finding global minimum across single-store and multi-store splits.
        """
        stores = list(store_infos.keys())
        n_items = len(basket_items)

        # Build candidate options per item
        item_store_options: List[List[str]] = []
        for item in basket_items:
            options = [
                s for s in stores
                if catalog_matches.get(item.raw_text, {}).get(s) and
                catalog_matches[item.raw_text][s].is_in_stock
            ]
            if not options:
                # Item cannot be fulfilled by any store
                item_store_options.append([])
            else:
                item_store_options.append(options)

        # If any item has no available store
        if any(len(opts) == 0 for opts in item_store_options):
            best_single = min(
                (o for o in single_orders.values() if o),
                key=lambda o: (o.missing_items_count, o.total_cost),
                default=None
            )
            return [best_single] if best_single else [], False

        best_cost = float("inf")
        best_assignment: Optional[Tuple[str, ...]] = None

        # Explore all combinations
        for assignment in itertools.product(*item_store_options):
            # assignment is a tuple of store names, one per item
            active_stores = set(assignment)
            
            # Check MOV and compute subtotals
            store_subtotals: Dict[str, float] = {s: 0.0 for s in active_stores}
            for i, s in enumerate(assignment):
                item = basket_items[i]
                cand = catalog_matches[item.raw_text][s]
                store_subtotals[s] += cand.discount_price * item.quantity

            # Check if all active stores meet minimum order value
            if any(store_subtotals[s] < store_infos[s].minimum_order_value for s in active_stores):
                continue

            # Compute delivery fees
            total_delivery = sum(calculate_delivery_fee(store_subtotals[s], store_infos[s]) for s in active_stores)
            total_items = sum(store_subtotals.values())
            
            # Apply coordination friction penalty for receiving multiple deliveries
            split_friction = self.split_penalty * (len(active_stores) - 1)
            candidate_total = total_items + total_delivery + split_friction

            if candidate_total < best_cost:
                best_cost = candidate_total
                best_assignment = assignment

        if not best_assignment:
            best_single = min(
                (o for o in single_orders.values() if o and o.missing_items_count == 0 and o.meets_mov),
                key=lambda o: o.total_cost,
                default=None
            )
            return [best_single] if best_single else [], False

        # Build StoreOrder objects for best assignment
        active_stores = sorted(list(set(best_assignment)))
        result_orders: List[StoreOrder] = []
        for s in active_stores:
            store_items: List[BasketItemAssignment] = []
            subtotal = 0.0
            savings = 0.0
            for i, store_name in enumerate(best_assignment):
                if store_name == s:
                    item = basket_items[i]
                    cand = catalog_matches[item.raw_text][s]
                    line_cost = cand.discount_price * item.quantity
                    line_saving = cand.saving_amount * item.quantity
                    subtotal += line_cost
                    savings += line_saving
                    store_items.append(BasketItemAssignment(
                        item=cand,
                        quantity=item.quantity,
                        line_total=line_cost,
                        nominal_saving=line_saving
                    ))
            
            deliv = calculate_delivery_fee(subtotal, store_infos[s])
            result_orders.append(StoreOrder(
                platform=s,
                store_id=store_infos[s].store_id,
                items=store_items,
                items_subtotal=subtotal,
                delivery_fee=deliv,
                total_cost=subtotal + deliv,
                total_savings=savings,
                minimum_order_value=store_infos[s].minimum_order_value,
                meets_mov=subtotal >= store_infos[s].minimum_order_value
            ))

        best_single = min(
            (o for o in single_orders.values() if o and o.missing_items_count == 0 and o.meets_mov),
            key=lambda o: o.total_cost,
            default=None
        )

        multi_total = sum(o.total_cost for o in result_orders) + (
            self.split_penalty * (len(result_orders) - 1) if len(result_orders) > 1 else 0
        )

        if best_single and (not result_orders or multi_total >= best_single.total_cost):
            return [best_single], False

        return result_orders, len(result_orders) > 1

    def _build_result(
        self,
        optimal_orders: List[StoreOrder],
        single_orders: Dict[str, Optional[StoreOrder]],
        trap_report: TrapAuditor,
        is_multi: bool,
        deal_opportunities: Optional[List[FlashDealOpportunity]] = None,
    ) -> OptimizationResult:
        """Assembles the final metrics and OptimizationResult object."""
        items_cost = sum(o.items_subtotal for o in optimal_orders)
        deliv_fees = sum(o.delivery_fee for o in optimal_orders)
        grand_total = items_cost + deliv_fees
        discounts = sum(o.total_savings for o in optimal_orders)

        feasible_singles = [
            o for o in single_orders.values()
            if o and o.missing_items_count == 0
        ]
        
        worst_single_cost = max((o.total_cost for o in feasible_singles), default=grand_total)
        best_single_cost = min((o.total_cost for o in feasible_singles), default=grand_total)

        savings_vs_worst = max(0.0, worst_single_cost - grand_total)
        savings_vs_best = max(0.0, best_single_cost - grand_total)

        return OptimizationResult(
            single_store_orders=single_orders,
            optimal_orders=optimal_orders,
            is_multi_store=is_multi,
            total_items_cost=items_cost,
            total_delivery_fees=deliv_fees,
            grand_total_cost=grand_total,
            total_discounts_saved=discounts,
            net_savings_versus_worst=savings_vs_worst,
            net_savings_versus_best_single=savings_vs_best,
            trap_audit=trap_report,
            deal_opportunities=deal_opportunities or [],
        )

