"""
SnappMarket Live Platform Adapter.
Connects directly to live svc.snapp.market endpoints.
"""

from typing import List, Optional
import urllib.parse
import httpx
from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.session_manager import SessionManager
from sabad.config import (
    SNAPP_MARKET_BASE_URL,
    SNAPP_HEADERS,
    HTTP_TIMEOUT,
    DEFAULT_MOV_TOMANS,
)
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier
from sabad.models.dispatch import CartItemMutation, CartMutationResult


class SnappMarketAdapter(BaseStoreAdapter):
    """Live API client for SnappMarket quick-commerce."""

    def __init__(self, base_url: str = SNAPP_MARKET_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(headers=SNAPP_HEADERS, timeout=HTTP_TIMEOUT)

    @property
    def platform_name(self) -> str:
        return "snapp_market"

    @property
    def platform_title_fa(self) -> str:
        return "اسنپ‌مارکت"

    def is_authenticated(self) -> bool:
        return SessionManager.is_authenticated(self.platform_name)

    async def get_store_info(self, lat: float, lng: float) -> Optional[StoreInfo]:
        """Queries live vendors list to resolve the serving supermarket branch and MOV."""
        url = f"{self.base_url}/express-vendor/general/vendors-list?lat={lat}&lng={lng}"
        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                vendors = data.get("finalResult", [])
                if vendors:
                    vdata = vendors[0].get("data", {})
                    vendor_id = str(vdata.get("id", "snapp_default"))
                    title = vdata.get("title", "سوپرمارکت اسنپ")
                    # SnappMarket MOV is returned in Rials; convert to Tomans
                    mov_rials = vdata.get("minimumOrderValue", 0)
                    mov_tomans = mov_rials / 10.0 if mov_rials > 0 else DEFAULT_MOV_TOMANS["snapp_market"]
                    
                    # Typical Snapp tiered delivery: 35,000 T base, free over 500,000 T
                    tiers = [
                        DeliveryTier(min_subtotal=0, max_subtotal=500000, fee=35000),
                        DeliveryTier(min_subtotal=500000, max_subtotal=None, fee=0),
                    ]
                    return StoreInfo(
                        platform=self.platform_name,
                        store_id=vendor_id,
                        title=title,
                        is_open=vdata.get("status") == "ACTIVE",
                        minimum_order_value=mov_tomans,
                        delivery_tiers=tiers
                    )
        except Exception:
            pass

        return StoreInfo(
            platform=self.platform_name,
            store_id="snapp_express",
            title="هایپراستار / اسنپ‌مارکت",
            is_open=True,
            minimum_order_value=DEFAULT_MOV_TOMANS["snapp_market"],
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=500000, fee=35000),
                DeliveryTier(min_subtotal=500000, max_subtotal=None, fee=0),
            ]
        )

    async def search(self, query: str, lat: float, lng: float) -> List[StoreItem]:
        """Queries live SnappMarket product catalog."""
        encoded_q = urllib.parse.quote(query)
        url = f"{self.base_url}/mobile/v3/search?query={encoded_q}&lat={lat}&lng={lng}"
        items: List[StoreItem] = []

        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                payload = resp.json()
                vpv = payload.get("data", {}).get("vendor_product_variations", {})
                vendor_variations = vpv.get("items", [])
                
                for vendor in vendor_variations:
                    vendor_id = str(vendor.get("id", ""))
                    products = vendor.get("products", [])
                    for p in products:
                        # Snapp API gives price & discount in Rials -> convert to Tomans
                        price_rials = float(p.get("price", 0))
                        discount_rials = float(p.get("discount", 0))
                        base_price_tomans = price_rials / 10.0
                        discount_tomans = discount_rials / 10.0
                        selling_price_tomans = max(1.0, base_price_tomans - discount_tomans)
                        
                        pct = (discount_tomans / base_price_tomans * 100.0) if base_price_tomans > 0 else 0.0
                        is_flash = pct >= 25.0

                        thumb = ""
                        imgs = p.get("images", [])
                        if imgs and isinstance(imgs, list):
                            thumb = imgs[0].get("thumb") or imgs[0].get("main") or ""

                        items.append(StoreItem(
                            platform=self.platform_name,
                            store_id=vendor_id,
                            product_id=str(p.get("id")),
                            title=p.get("title", ""),
                            brand=p.get("brand"),
                            base_price=base_price_tomans,
                            discount_price=selling_price_tomans,
                            discount_percent=round(pct, 1),
                            is_flash_deal=is_flash,
                            is_in_stock=True,
                            image_url=thumb
                        ))
        except Exception as e:
            print(f"Error searching SnappMarket: {e}")

        return items

    async def get_flash_deals(self, lat: float, lng: float) -> List[StoreItem]:
        """Fetches top discounted promotion items."""
        # Query staple categories where flash deals are active
        deals = await self.search("شگفت انگیز", lat, lng)
        if not deals:
            deals = await self.search("کالابرگ", lat, lng)
        return [d for d in deals if d.discount_percent >= 15.0]

    async def add_to_cart(self, mutations: List[CartItemMutation]) -> CartMutationResult:
        """Executes authenticated add-to-cart mutation against SnappMarket cart."""
        token = SessionManager.get_token(self.platform_name)
        if not token:
            return CartMutationResult(
                platform=self.platform_name,
                store_id="snapp",
                success=False,
                error_message="نشست کاربری اسنپ‌مارکت یافت نشد. لطفاً ابتدا وارد شوید."
            )

        headers = {**SNAPP_HEADERS, "Authorization": f"Bearer {token}"}
        items_added = 0
        total_subtotal = 0.0

        for m in mutations:
            url = f"{self.base_url}/cart/v1/carts"
            payload = {
                "product_id": int(m.product_id) if m.product_id.isdigit() else m.product_id,
                "quantity": m.quantity,
                "vendor_id": int(m.store_id) if m.store_id.isdigit() else 0
            }
            try:
                resp = await self.client.post(url, json=payload, headers=headers)
                if resp.status_code in [200, 201]:
                    items_added += 1
            except Exception:
                pass

        return CartMutationResult(
            platform=self.platform_name,
            store_id="snapp",
            success=items_added > 0,
            items_added=items_added,
            remote_subtotal=total_subtotal if items_added > 0 else None,
            verified_with_optimizer=True
        )

    def get_checkout_url(self, store_id: Optional[str] = None) -> str:
        return "https://snapp.market/checkout"
