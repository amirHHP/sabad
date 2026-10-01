"""
Domain models for cart mutations, post-mutation verification, and checkout handoff.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class CartItemMutation(BaseModel):
    """Payload to add an individual item to a store's cart."""
    product_id: str
    quantity: int = Field(ge=1)
    store_id: str
    variant_id: Optional[str] = None


class CartMutationResult(BaseModel):
    """Result of an authenticated remote basket mutation."""
    platform: str
    store_id: str
    success: bool
    items_added: int = 0
    remote_subtotal: Optional[float] = None
    remote_delivery_fee: Optional[float] = None
    error_message: Optional[str] = None
    verified_with_optimizer: bool = False


class CheckoutHandoff(BaseModel):
    """Direct handoff links for the user to finalize payment on bank gateway."""
    platform: str
    platform_fa: str
    web_checkout_url: str
    deep_link_url: Optional[str] = None
    items_count: int
    total_amount_tomans: float
    summary_fa: str
    mutation_result: Optional[CartMutationResult] = None
