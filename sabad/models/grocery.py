"""
Domain models for normalized Persian grocery items and baskets.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ParsedGroceryItem(BaseModel):
    """Structured representation of an extracted grocery item."""
    raw_text: str = Field(description="Original Persian phrase for this item")
    name: str = Field(description="Canonical item name e.g. شیر, پنیر, روغن")
    brand: Optional[str] = Field(default=None, description="Extracted brand e.g. کاله, میهن, پریل")
    quantity: int = Field(default=1, ge=1, description="Requested units")
    volume_weight: Optional[float] = Field(default=None, description="Numeric volume/weight e.g. 1.0, 350, 4.0")
    unit: Optional[str] = Field(default=None, description="Measurement unit e.g. لیتر, گرم, کیلوگرم, میلی‌لیتر")
    fat_percentage: Optional[float] = Field(default=None, description="Fat content percentage e.g. 1.5, 3.2")
    category: Optional[str] = Field(default=None, description="Estimated category e.g. لبنیات, شوینده")

    @property
    def display_title(self) -> str:
        parts = [f"{self.quantity} عدد {self.name}"]
        if self.brand:
            parts.append(self.brand)
        if self.volume_weight and self.unit:
            parts.append(f"{self.volume_weight:g} {self.unit}")
        if self.fat_percentage is not None:
            parts.append(f"{self.fat_percentage:g}٪ چربی")
        return " ".join(parts)


class ParsedGroceryBasket(BaseModel):
    """A collection of normalized grocery items ready for catalog search."""
    raw_input: str
    items: List[ParsedGroceryItem] = Field(default_factory=list)
