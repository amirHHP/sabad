"""
Domain models for optimization inputs, store baskets, and trap audit reporting.
All prices are in Tomans.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from sabad.models.catalog import StoreItem


class BasketItemAssignment(BaseModel):
    """An item assigned to a specific store with quantity."""
    item: StoreItem
    quantity: int = Field(ge=1)
    line_total: float = Field(description="Total price for this line (discount_price * quantity)")
    nominal_saving: float = Field(default=0.0, description="Gross saving from discounts")


class StoreOrder(BaseModel):
    """Order destined for a single store platform."""
    platform: str
    store_id: str
    items: List[BasketItemAssignment] = Field(default_factory=list)
    items_subtotal: float = Field(ge=0, description="Sum of line_totals in Tomans")
    delivery_fee: float = Field(default=0.0, ge=0, description="Calculated shipping fee in Tomans")
    total_cost: float = Field(ge=0, description="subtotal + delivery_fee in Tomans")
    total_savings: float = Field(default=0.0, description="Discounts saved")
    minimum_order_value: float = Field(default=0.0)
    meets_mov: bool = True
    missing_items_count: int = Field(default=0, description="Items from request not available here")


class TrapAuditItem(BaseModel):
    """Evaluation of an individual promotional flash-deal item."""
    product_title: str
    deal_store: str
    apparent_deal_saving: float = Field(description="Nominal discount on the deal item in Tomans")
    collateral_item_markup: float = Field(description="Markup on other items in basket vs competitor in Tomans")
    extra_shipping_fee: float = Field(description="Additional delivery fee incurred in Tomans")
    net_advantage: float = Field(description="Deal savings - (Markups + Extra shipping) in Tomans")
    verdict: str = Field(description="'CRITICAL_TRAP', 'NEUTRAL_DEAL', or 'GENUINE_DEAL'")
    explanation_fa: str


class TrapAuditReport(BaseModel):
    """Comprehensive audit report for flash-deals in the user's basket."""
    audited_deals: List[TrapAuditItem] = Field(default_factory=list)
    has_traps: bool = False
    summary_fa: str = ""


class OptimizationResult(BaseModel):
    """Final solution produced by the mathematical optimizer."""
    # Single-store evaluations (100% basket from Store A, B, or C)
    single_store_orders: Dict[str, Optional[StoreOrder]] = Field(default_factory=dict)
    
    # Recommended optimal assignment (single or multi-store)
    optimal_orders: List[StoreOrder] = Field(default_factory=list)
    is_multi_store: bool = False
    
    # Aggregated metrics
    total_items_cost: float = Field(ge=0)
    total_delivery_fees: float = Field(default=0.0, ge=0)
    grand_total_cost: float = Field(ge=0)
    total_discounts_saved: float = Field(default=0.0, ge=0)
    net_savings_versus_worst: float = Field(default=0.0)
    net_savings_versus_best_single: float = Field(default=0.0)
    
    # Flash deal trap analysis
    trap_audit: TrapAuditReport = Field(default_factory=TrapAuditReport)
