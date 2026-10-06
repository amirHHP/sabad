"""
Digikala Jet Live Platform Adapter.
Connects directly to live api.digikalajet.ir endpoints.
"""

from typing import List, Optional, Dict, Any
import urllib.parse
import httpx
from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.session_manager import SessionManager
from sabad.config import (
    DIGIKALA_JET_BASE_URL,
    JET_HEADERS,
    HTTP_TIMEOUT,
    DEFAULT_MOV_TOMANS,
)
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier
from sabad.models.dispatch import CartItemMutation, CartMutationResult


class DigikalaJetAdapter(BaseStoreAdapter):
    """Live API client for Digikala Jet quick-commerce."""

    def __init__(self, base_url: str = DIGIKALA_JET_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(headers=JET_HEADERS, timeout=HTTP_TIMEOUT)

    @property
    def platform_name(self) -> str:
        return "digikala_jet"

    @property
    def platform_title_fa(self) -> str:
        return "دیجی‌کالا جت"

    def is_authenticated(self) -> bool:
        return SessionManager.is_authenticated(self.platform_name)

    async def get_store_info(self, lat: float, lng: float) -> Optional[StoreInfo]:
        """Resolves serving dark store or supermarket branch, live delivery fee, and MOV."""
        url = f"{self.base_url}/search/shop/?latitude={lat}&longitude={lng}&onlyShops=true"
        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                payload = resp.json().get("data", {})
                results = payload.get("result", [])
                if results:
                    # Select nearest supermarket / grocery darkstore
                    supermarket_shop = None
                    for s in results:
                        s_title = s.get("title", "")
                        if any(k in s_title for k in ["سوپر", "مارکت", "پروتئین", "هایپر"]):
                            supermarket_shop = s
                            break
                    shop = supermarket_shop or results[0]
                    shop_id = str(shop.get("id", "jet_darkstore"))
                    title = shop.get("title", "جت مارت")
                    
                    # Extract live delivery fees from Jet shop data
                    delivery_info = shop.get("delivery", {})
                    raw_cost_rials = delivery_info.get("cost")
                    cost_tomans = float(raw_cost_rials) / 10.0 if raw_cost_rials is not None else 29000.0
                    free_price_rials = delivery_info.get("free_shipping_price")
                    free_thresh_tomans = float(free_price_rials) / 10.0 if free_price_rials else 450000.0

                    tiers = [
                        DeliveryTier(min_subtotal=0, max_subtotal=free_thresh_tomans, fee=cost_tomans),
                        DeliveryTier(min_subtotal=free_thresh_tomans, max_subtotal=None, fee=0),
                    ]
                    return StoreInfo(
                        platform=self.platform_name,
                        store_id=shop_id,
                        title=title,
                        is_open=shop.get("working_status", {}).get("is_open", True),
                        minimum_order_value=DEFAULT_MOV_TOMANS["digikala_jet"],
                        delivery_tiers=tiers
                    )
        except Exception as e:
            print(f"Error fetching Jet store info: {e}")

        return StoreInfo(
            platform=self.platform_name,
            store_id="jet_supermarket",
            title="سوپرمارکت دیجی‌کالا جت",
            is_open=True,
            minimum_order_value=DEFAULT_MOV_TOMANS["digikala_jet"],
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=450000, fee=29000),
                DeliveryTier(min_subtotal=450000, max_subtotal=None, fee=0),
            ]
        )

    async def search(self, query: str, lat: float, lng: float) -> List[StoreItem]:
        """Live search across dark stores and partner supermarkets."""
        encoded_q = urllib.parse.quote(query)
        url = f"{self.base_url}/products/search/all/?q={encoded_q}&latitude={lat}&longitude={lng}"
        items: List[StoreItem] = []

        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                payload = resp.json()
                results = payload.get("data", {}).get("result", [])
                
                for r in results:
                    price_info = r.get("price") or {}
                    price_rials = float(price_info.get("price", 0))
                    discount_rials = float(price_info.get("discount", 0))
                    pct = float(price_info.get("discount_percentage", 0))
                    
                    base_price_tomans = price_rials / 10.0
                    discount_tomans = discount_rials / 10.0
                    selling_price_tomans = max(1.0, base_price_tomans - discount_tomans)

                    shop_id = str(r.get("shop_id") or r.get("shop", {}).get("id") or "jet_default")
                    product_id = str(r.get("id") or r.get("product_id"))
                    
                    media = r.get("media") or ""
                    is_flash = pct >= 20.0 or bool(r.get("is_dynamic_amazing"))

                    items.append(StoreItem(
                        platform=self.platform_name,
                        store_id=shop_id,
                        product_id=product_id,
                        title=r.get("title", ""),
                        brand=r.get("brand", {}).get("title") if isinstance(r.get("brand"), dict) else None,
                        base_price=base_price_tomans,
                        discount_price=selling_price_tomans,
                        discount_percent=round(pct, 1),
                        is_flash_deal=is_flash,
                        is_in_stock=r.get("status") == "active" or r.get("is_in_stock", True),
                        image_url=media
                    ))
        except Exception as e:
            print(f"Error searching Digikala Jet: {e}")

        return items

    async def get_flash_deals(self, lat: float, lng: float) -> List[StoreItem]:
        """Scrapes live 'شگفت‌انگیز جت' (کهکشانی‌ها) carousel."""
        main_page_url = f"{self.base_url}/v3/main-page/?latitude={lat}&longitude={lng}"
        deals: List[StoreItem] = []

        try:
            resp = await self.client.get(main_page_url)
            if resp.status_code == 200:
                components = resp.json().get("data", {}).get("components", [])
                for c in components:
                    if c.get("component_type") == "amazing-widget-on-other-lines":
                        api_info = c.get("data", {}).get("api", {})
                        post_path = api_info.get("url")
                        if post_path:
                            post_url = f"{self.base_url}{post_path}"
                            post_resp = await self.client.get(post_url)
                            if post_resp.status_code == 200:
                                prods = post_resp.json().get("data", {}).get("products", [])
                                for p in prods:
                                    price_info = p.get("price") or {}
                                    price_rials = float(price_info.get("price", 0))
                                    discount_rials = float(price_info.get("discount", 0))
                                    pct = float(price_info.get("discount_percentage", 0))
                                    
                                    base_t = price_rials / 10.0
                                    disc_t = discount_rials / 10.0
                                    sell_t = max(1.0, base_t - disc_t)

                                    deals.append(StoreItem(
                                        platform=self.platform_name,
                                        store_id="jet_amazing",
                                        product_id=str(p.get("id")),
                                        title=p.get("title", ""),
                                        brand=None,
                                        base_price=base_t,
                                        discount_price=sell_t,
                                        discount_percent=round(pct, 1),
                                        is_flash_deal=True,
                                        is_in_stock=True,
                                        image_url=p.get("media") or ""
                                    ))
                                break
        except Exception as e:
            print(f"Error fetching Digikala Jet flash deals: {e}")

        return deals

    async def send_otp(self, phone: str) -> Dict[str, Any]:
        """Requests OTP SMS challenge from Digikala Jet auth endpoint."""
        url = f"{self.base_url}/user/login-register/"
        payload = {"phone": phone}
        try:
            resp = await self.client.post(url, json=payload)
            if resp.status_code == 200:
                body = resp.json()
                data = body.get("data", {})
                challenge_token = data.get("token")
                sms_ttl = data.get("sms_ttl", 120)
                if challenge_token:
                    return {
                        "success": True,
                        "challenge_token": challenge_token,
                        "sms_ttl": sms_ttl,
                        "message": f"کد تأیید به شماره {phone} ارسال شد."
                    }
                return {"success": False, "message": body.get("message") or "خطا در صدور کد تأیید جت"}
            return {"success": False, "message": f"خطای سرور جت: {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"خطا در ارتباط با دیجی‌کالا جت: {e}"}

    async def verify_otp(self, phone: str, otp_code: str, challenge_token: Optional[str] = None) -> Dict[str, Any]:
        """Verifies Digikala Jet OTP code using challenge token."""
        url = f"{self.base_url}/user/confirm-phone/"
        payload = {
            "phone": phone,
            "code": otp_code,
            "token": challenge_token,
            "isLoginRedesign": True
        }
        try:
            resp = await self.client.post(url, json=payload)
            if resp.status_code == 200:
                body = resp.json()
                data = body.get("data", {})
                user_token = data.get("token")
                if user_token:
                    SessionManager.save_tokens(
                        self.platform_name,
                        token=user_token,
                        phone=phone,
                        metadata=data
                    )
                    return {"success": True, "message": "ورود به دیجی‌کالا جت با موفقیت انجام شد."}
            return {"success": False, "message": "کد تأیید وارد شده نامعتبر یا منقضی است."}
        except Exception as e:
            return {"success": False, "message": f"خطا در تأیید کد دیجی‌کالا جت: {e}"}

    async def add_to_cart(self, mutations: List[CartItemMutation]) -> CartMutationResult:
        """Executes authenticated add-to-cart against Digikala Jet."""
        token = SessionManager.get_token(self.platform_name)
        if not token:
            return CartMutationResult(
                platform=self.platform_name,
                store_id="jet",
                success=False,
                error_message="نشست کاربری دیجی‌کالا جت یافت نشد. لطفاً لاگین نمایید."
            )

        headers = {**JET_HEADERS, "Authorization": f"Bearer {token}"}
        items_added = 0

        for m in mutations:
            url = f"{self.base_url}/cart/add/"
            payload = {
                "shop_product_id": int(m.product_id) if m.product_id.isdigit() else m.product_id,
                "quantity": m.quantity,
                "source": "web",
            }
            try:
                resp = await self.client.post(url, json=payload, headers=headers)
                if resp.status_code in [200, 201]:
                    items_added += 1
            except Exception:
                pass

        return CartMutationResult(
            platform=self.platform_name,
            store_id="jet",
            success=items_added > 0,
            items_added=items_added,
            verified_with_optimizer=items_added == len(mutations)
        )

    def get_checkout_url(self, store_id: Optional[str] = None) -> str:
        return "https://www.digikalajet.com/cart"
