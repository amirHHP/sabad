"""
Abstract Base Class for Live Store Platform Adapters.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from sabad.models.catalog import StoreItem, StoreInfo
from sabad.models.dispatch import CartItemMutation, CartMutationResult


class BaseStoreAdapter(ABC):
    """Unified interface for SnappMarket, Digikala Jet, and Okala."""
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Machine identifier (e.g. 'snapp_market', 'digikala_jet', 'okala')."""
        pass

    @property
    @abstractmethod
    def platform_title_fa(self) -> str:
        """Persian display title (e.g. 'اسنپ‌مارکت', 'دیجی‌کالا جت', 'افق کوروش / اکالا')."""
        pass

    @abstractmethod
    async def search(self, query: str, lat: float, lng: float) -> List[StoreItem]:
        """Queries live catalog for the given search term and location."""
        pass

    @abstractmethod
    async def get_flash_deals(self, lat: float, lng: float) -> List[StoreItem]:
        """Fetches live daily promotional items / flash deals."""
        pass

    @abstractmethod
    async def get_store_info(self, lat: float, lng: float) -> Optional[StoreInfo]:
        """Resolves nearest serving branch, delivery tiers, and MOV for coordinates."""
        pass

    @abstractmethod
    async def add_to_cart(self, mutations: List[CartItemMutation]) -> CartMutationResult:
        """Executes remote add-to-cart mutations for the user."""
        pass

    @abstractmethod
    def get_checkout_url(self, store_id: Optional[str] = None) -> str:
        """Returns direct web URL for checkout / payment handoff."""
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Checks if valid user session credentials are stored locally."""
        pass
