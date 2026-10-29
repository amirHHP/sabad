"""
Domain models for store catalog products, search results, and delivery tiers.
All monetary values are normalized to TOMANS.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from sabad.models.grocery import ParsedGroceryItem


class DeliveryTier(BaseModel):
    """Shipping cost rule based on order subtotal in Tomans."""
    min_subtotal: float = Field(ge=0, description="Lower threshold of subtotal")
    max_subtotal: Optional[float] = Field(default=None, description="Upper threshold (None if infinity)")
    fee: float = Field(ge=0, description="Delivery fee for this tier")


class StoreInfo(BaseModel):
    """Metadata regarding a local branch/dark store."""
    platform: str  # snapp_market, digikala_jet, okala
    store_id: str
    title: str
    is_open: bool = True
    minimum_order_value: float = Field(default=0.0, description="MOV in Tomans")
    delivery_tiers: List[DeliveryTier] = Field(default_factory=list)


class StoreItem(BaseModel):
    """Canonical representation of a live store SKU."""
    platform: str  # snapp_market, digikala_jet, okala
    store_id: str
    product_id: str
    title: str
    brand: Optional[str] = None
    base_price: float = Field(description="Original price in Tomans")
    discount_price: float = Field(description="Selling price after discounts in Tomans")
    discount_percent: float = Field(default=0.0, ge=0, le=100)
    is_flash_deal: bool = False
    is_in_stock: bool = True
    max_per_order: Optional[int] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    match_score: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def saving_amount(self) -> float:
        return max(0.0, self.base_price - self.discount_price)


class CatalogSearchResult(BaseModel):
    """Search matches across stores for a requested user item."""
    query_item: ParsedGroceryItem
    store_matches: Dict[str, Optional[StoreItem]] = Field(
        default_factory=dict,
        description="Key is platform name, value is best matching StoreItem or None"
    )
