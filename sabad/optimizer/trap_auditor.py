"""
Flash Deal Trap Auditor ("تله‌ی شگفت‌انگیز").
Audits whether promotional loss-leader discounts are mathematically advantageous
or if markups on remaining basket items and added delivery fees negate the savings.
"""

from typing import Dict, List, Optional
from sabad.models.catalog import StoreItem, StoreInfo
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.optimization import TrapAuditItem, TrapAuditReport


class TrapAuditor:
    """Calculates net economic advantage of promotional items against basket context."""

    @staticmethod
    def audit_deals(
        basket_items: List[ParsedGroceryItem],
        catalog_matches: Dict[str, Dict[str, Optional[StoreItem]]],
        store_infos: Dict[str, StoreInfo],
    ) -> TrapAuditReport:
        """
        Audits all flash-deal items in catalog matches.
        catalog_matches structure: {item_name: {platform: StoreItem}}
        """
        audited_items: List[TrapAuditItem] = []
        has_critical_traps = False

        for query_item in basket_items:
            key = query_item.raw_text
            matches = catalog_matches.get(key, {})

            # Find stores that have this item as a flash deal
            deal_stores = [
                s for s, item in matches.items()
                if item and item.is_flash_deal and item.is_in_stock
            ]

            for s_deal in deal_stores:
                deal_item = matches[s_deal]
                if not deal_item:
                    continue

                # 1. Gross saving on the flash deal item vs cheapest competitor
                competitor_prices = [
                    m.discount_price for s, m in matches.items()
                    if s != s_deal and m and m.is_in_stock
                ]
                if not competitor_prices:
                    # No competitors offer this item; cannot be a relative trap
                    continue

                cheapest_comp_price = min(competitor_prices)
                deal_price = deal_item.discount_price
                nominal_deal_saving = max(0.0, (cheapest_comp_price - deal_price) * query_item.quantity)

                # 2. Collateral markup on other items in the user's basket
                collateral_markup = 0.0
                for other_item in basket_items:
                    if other_item.raw_text == query_item.raw_text:
                        continue
                    other_matches = catalog_matches.get(other_item.raw_text, {})
                    other_deal_store_item = other_matches.get(s_deal)
                    
                    other_comp_prices = [
                        m.discount_price for s, m in other_matches.items()
                        if s != s_deal and m and m.is_in_stock
                    ]
                    if other_deal_store_item and other_comp_prices:
                        cheapest_other_comp = min(other_comp_prices)
                        markup = max(0.0, (other_deal_store_item.discount_price - cheapest_other_comp) * other_item.quantity)
                        collateral_markup += markup

                # 3. Delivery fee differential
                deal_store_info = store_infos.get(s_deal)
                deal_shipping = (
                    deal_store_info.delivery_tiers[0].fee
                    if deal_store_info and deal_store_info.delivery_tiers
                    else 30000.0
                )
                comp_shippings = [
                    si.delivery_tiers[0].fee
                    for s, si in store_infos.items()
                    if s != s_deal and si.delivery_tiers
                ]
                min_comp_shipping = min(comp_shippings) if comp_shippings else 25000.0
                extra_shipping = max(0.0, deal_shipping - min_comp_shipping)

                # 4. Net Economic Equation
                net_advantage = nominal_deal_saving - (collateral_markup + extra_shipping)

                if net_advantage < -5000:
                    verdict = "CRITICAL_TRAP"
                    has_critical_traps = True
                    explanation = (
                        f"⚠️ تله‌ی تخفیف! اگرچه «{deal_item.title}» در این فروشگاه {deal_item.discount_percent:.0f}٪ تخفیف دارد، "
                        f"اما خرید کل سبد در اینجا {abs(net_advantage):,.0f} تومان گران‌تر تمام می‌شود "
                        f"(به دلیل {collateral_markup:,.0f} تومان گرانی سایر کالاها و هزینه ارسال بالاتر)."
                    )
                elif net_advantage < 10000:
                    verdict = "NEUTRAL_DEAL"
                    explanation = (
                        f"تخفیف خنثی: تخفیف ظاهری {nominal_deal_saving:,.0f} تومانی «{deal_item.title}» "
                        f"تقریباً با هزینه‌های جانبی سبد سر‌به‌سر می‌شود (سود خالص: فقط {max(0.0, net_advantage):,.0f} تومان)."
                    )
                else:
                    verdict = "GENUINE_DEAL"
                    explanation = (
                        f"✅ تخفیف واقعی و به‌صرفه! خرید «{deal_item.title}» با تخفیف {deal_item.discount_percent:.0f}٪ "
                        f"سود خالص {net_advantage:,.0f} تومانی برای کل سفارش ایجاد می‌کند."
                    )

                audited_items.append(TrapAuditItem(
                    product_title=deal_item.title,
                    deal_store=s_deal,
                    apparent_deal_saving=nominal_deal_saving,
                    collateral_item_markup=collateral_markup,
                    extra_shipping_fee=extra_shipping,
                    net_advantage=net_advantage,
                    verdict=verdict,
                    explanation_fa=explanation
                ))

        summary = (
            "🚨 توجه: در سبد شما تله‌ی شگفت‌انگیز بازاریابی شناسایی شد! تخفیف برخی اقلام با گرانی سایر اقلام جبران می‌شود."
            if has_critical_traps
            else "تمامی تخفیف‌های اعمال شده در سبد، سودآوری اقتصادی مثبتی دارند."
        )

        return TrapAuditReport(
            audited_deals=audited_items,
            has_traps=has_critical_traps,
            summary_fa=summary
        )
