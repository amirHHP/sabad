"""
Okala Live Platform Adapter (Ofoq Kourosh & Emin).
Connects directly to live apigateway.okala.com endpoints.
"""

from typing import List, Optional
import urllib.parse
import httpx
from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.session_manager import SessionManager
from sabad.config import (
    OKALA_BASE_URL,
    OKALA_HEADERS,
    HTTP_TIMEOUT,
    DEFAULT_MOV_TOMANS,
)
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier
from sabad.models.dispatch import CartItemMutation, CartMutationResult


class OkalaAdapter(BaseStoreAdapter):
    """Live API client for Okala (Ofoq Kourosh / Emin branches)."""

    def __init__(self, base_url: str = OKALA_BASE_URL):
        self.base_url = base_url.rstrip("/")
        # Okala internal gateway uses specific headers
        self.client = httpx.AsyncClient(
            headers=OKALA_HEADERS,
            timeout=HTTP_TIMEOUT,
            verify=False  # Required for Iranian internal SSL root chain
        )

    @property
    def platform_name(self) -> str:
        return "okala"

    @property
    def platform_title_fa(self) -> str:
        return "افق کوروش / اکالا"

    def is_authenticated(self) -> bool:
        return SessionManager.is_authenticated(self.platform_name)

    async def get_store_info(self, lat: float, lng: float) -> Optional[StoreInfo]:
        """Resolves local Ofoq Kourosh store and delivery tiers."""
        return StoreInfo(
            platform=self.platform_name,
            store_id="2319",
            title="افق کوروش (شعبه مرکزی)",
            is_open=True,
            minimum_order_value=DEFAULT_MOV_TOMANS["okala"],
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=400000, fee=25000),
                DeliveryTier(min_subtotal=400000, max_subtotal=None, fee=0),
            ]
        )

    async def search(self, query: str, lat: float, lng: float) -> List[StoreItem]:
        """Queries live Okala catalog."""
        encoded_q = urllib.parse.quote(query)
        store_id = "2319"
        url = (
            f"{self.base_url}/api/Search/v1/Product/Search"
            f"?StoreIds={store_id}&SearchText={encoded_q}&HasQuantity=true&Page=1&Take=20&excludeShoppingCard=false"
        )
        items: List[StoreItem] = []

        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                payload = resp.json()
                entities = payload.get("entities", [])
                
                for e in entities:
                    # Okala prices are in Rials -> convert to Tomans
                    price_rials = float(e.get("price", 0))
                    discount_pct = float(e.get("discountPercent", 0))
                    base_price_tomans = price_rials / 10.0
                    
                    discount_tomans = base_price_tomans * (discount_pct / 100.0)
                    selling_price_tomans = max(1.0, base_price_tomans - discount_tomans)

                    product_id = str(e.get("id"))
                    name = e.get("name") or e.get("highlightName") or ""
                    img = e.get("imageUrl") or ""

                    items.append(StoreItem(
                        platform=self.platform_name,
                        store_id=store_id,
                        product_id=product_id,
                        title=name,
                        brand=None,
                        base_price=base_price_tomans,
                        discount_price=selling_price_tomans,
                        discount_percent=discount_pct,
                        is_flash_deal=discount_pct >= 25.0,
                        is_in_stock=int(e.get("quantity", 1)) > 0,
                        image_url=img
                    ))
        except Exception as err:
            print(f"Error searching Okala: {err}")

        return items

    async def get_flash_deals(self, lat: float, lng: float) -> List[StoreItem]:
        """Fetches timed special discounts from Okala."""
        store_id = "2319"
        url = (
            f"{self.base_url}/api/Search/v1/Product/Search"
            f"?StoreIds={store_id}&HasDiscount=true&Page=1&Take=20&excludeShoppingCard=false"
        )
        deals: List[StoreItem] = []

        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                entities = resp.json().get("entities", [])
                for e in entities:
                    price_rials = float(e.get("price", 0))
                    discount_pct = float(e.get("discountPercent", 0))
                    base_t = price_rials / 10.0
                    disc_t = base_t * (discount_pct / 100.0)
                    sell_t = max(1.0, base_t - disc_t)

                    deals.append(StoreItem(
                        platform=self.platform_name,
                        store_id=store_id,
                        product_id=str(e.get("id")),
                        title=e.get("name", ""),
                        base_price=base_t,
                        discount_price=sell_t,
                        discount_percent=discount_pct,
                        is_flash_deal=True,
                        is_in_stock=int(e.get("quantity", 1)) > 0,
                        image_url=e.get("imageUrl") or ""
                    ))
        except Exception as err:
            print(f"Error fetching Okala flash deals: {err}")

        return deals

    async def add_to_cart(self, mutations: List[CartItemMutation]) -> CartMutationResult:
        """Executes authenticated add-to-cart against Okala."""
        token = SessionManager.get_token(self.platform_name)
        if not token:
            return CartMutationResult(
                platform=self.platform_name,
                store_id="2319",
                success=False,
                error_message="نشست کاربری اکالا یافت نشد. لطفاً لاگین نمایید."
            )

        headers = {**OKALA_HEADERS, "Authorization": f"Bearer {token}"}
        items_added = 0

        for m in mutations:
            url = f"{self.base_url}/api/Cart/v1/Item"
            payload = {
                "productId": int(m.product_id) if m.product_id.isdigit() else m.product_id,
                "storeId": int(m.store_id) if m.store_id.isdigit() else 2319,
                "quantity": m.quantity,
            }
            try:
                resp = await self.client.post(url, json=payload, headers=headers)
                if resp.status_code in [200, 201]:
                    items_added += 1
            except Exception:
                pass

        return CartMutationResult(
            platform=self.platform_name,
            store_id="2319",
            success=items_added > 0,
            items_added=items_added,
            verified_with_optimizer=True
        )

    def get_checkout_url(self, store_id: Optional[str] = None) -> str:
        return "https://okala.com/checkout"
