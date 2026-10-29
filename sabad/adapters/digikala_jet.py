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
from sabad.product_links import digikala_jet_product_page


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

    def _product_page(self, row: Dict[str, Any], shop_id: str, product_id: str) -> Optional[str]:
        """Link to the public product page, not a title search that 404s."""
        page = digikala_jet_product_page(shop_id, product_id)
        if page:
            return page
        found = self.first_url(row.get("url") or row.get("product_url") or row.get("web_url") or row.get("link"))
        return found or None

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
                    cost_tomans = self.rials_to_tomans(raw_cost_rials, fallback=29000.0)
                    free_price_rials = delivery_info.get("free_shipping_price")
                    free_thresh_tomans = self.rials_to_tomans(free_price_rials, fallback=450000.0)

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
            self.note_store_error("store_info", e)

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
                data = payload.get("data", {})
                results = data.get("result", []) if isinstance(data, dict) else []
                if isinstance(results, dict):
                    results = results.get("products") or results.get("items") or results.get("results") or []
                if not results and isinstance(data, dict):
                    results = data.get("products") or data.get("items") or []
                if not isinstance(results, list):
                    results = []
                
                for r in results:
                    stock_obj = r.get("stock")
                    if isinstance(stock_obj, dict):
                        has_stock = bool(stock_obj.get("has_stock", False))
                    else:
                        has_stock = bool(r.get("has_stock", r.get("is_in_stock", False)))

                    price_info = r.get("price")
                    if isinstance(price_info, dict):
                        raw_price = price_info.get("price")
                        raw_discount = price_info.get("discount")
                        base_price_tomans = self.rials_to_tomans(raw_price, fallback=0.0)
                        discount_tomans = self.rials_to_tomans(raw_discount, fallback=0.0)
                        raw_pct = price_info.get("discount_percentage")
                        try:
                            pct = float(raw_pct) if raw_pct is not None else 0.0
                        except (ValueError, TypeError):
                            pct = 0.0
                        if pct == 0.0 and base_price_tomans > 0 and discount_tomans > 0:
                            pct = (discount_tomans / base_price_tomans) * 100.0
                    else:
                        price_info = None
                        base_price_tomans = 0.0
                        discount_tomans = 0.0
                        pct = 0.0

                    if base_price_tomans > 0:
                        selling_price_tomans = max(1.0, base_price_tomans - discount_tomans)
                    else:
                        selling_price_tomans = 0.0

                    if (not has_stock) or (price_info is None) or (base_price_tomans <= 0):
                        is_in_stock = False
                    else:
                        is_in_stock = True

                    shop = r.get("shop") if isinstance(r.get("shop"), dict) else {}
                    shop_id = str(r.get("shop_id") or shop.get("id") or "jet_default")
                    # Page URLs use `id` (shop product). `product_id` is a different barcode.
                    product_id = str(r.get("id") or "")
                    
                    media = self.first_url(r.get("media") or r.get("images") or r.get("image"))
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
                        is_in_stock=is_in_stock,
                        image_url=media,
                        product_url=self._product_page(r, shop_id, product_id),
                    ))
        except Exception as e:
            self.note_store_error("search", e, reraise_timeout=True)

        # Prioritize in-stock items first while maintaining relevance order
        items.sort(key=lambda x: not x.is_in_stock)
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
                                    stock_obj = p.get("stock")
                                    if isinstance(stock_obj, dict):
                                        has_stock = bool(stock_obj.get("has_stock", True))
                                    else:
                                        has_stock = bool(p.get("has_stock", p.get("is_in_stock", True)))

                                    price_info = p.get("price")
                                    if isinstance(price_info, dict):
                                        raw_price = price_info.get("price")
                                        raw_discount = price_info.get("discount")
                                        base_t = self.rials_to_tomans(raw_price, fallback=0.0)
                                        disc_t = self.rials_to_tomans(raw_discount, fallback=0.0)
                                        raw_pct = price_info.get("discount_percentage")
                                        try:
                                            pct = float(raw_pct) if raw_pct is not None else 0.0
                                        except (ValueError, TypeError):
                                            pct = 0.0
                                    else:
                                        price_info = None
                                        base_t = 0.0
                                        disc_t = 0.0
                                        pct = 0.0

                                    sell_t = max(1.0, base_t - disc_t) if base_t > 0 else 0.0
                                    in_stock = has_stock and (price_info is not None) and (base_t > 0)

                                    shop = p.get("shop") if isinstance(p.get("shop"), dict) else {}
                                    shop_id = str(p.get("shop_id") or shop.get("id") or "")
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
                                        is_in_stock=in_stock,
                                        image_url=self.first_url(p.get("media") or p.get("images") or p.get("image")),
                                        product_url=self._product_page(p, shop_id, str(p.get("id") or "")),
                                    ))
                                break
        except Exception as e:
            self.note_store_error("flash_deals", e)

        return deals

    async def send_otp(self, phone: str) -> Dict[str, Any]:
        """Requests OTP SMS challenge from Digikala Jet auth endpoint."""
        from sabad.normalizer.persian_digits import to_english_digits
        clean_phone = to_english_digits(phone.strip())
        url = f"{self.base_url}/user/login-register/"
        payload = {"phone": clean_phone}
        try:
            resp = await self.client.post(url, json=payload)
            body = resp.json() if resp.status_code in [200, 400] else {}
            if resp.status_code == 200:
                data = body.get("data", {})
                challenge_token = data.get("token")
                sms_ttl = data.get("sms_ttl", 120)
                if challenge_token:
                    return {
                        "success": True,
                        "challenge_token": challenge_token,
                        "sms_ttl": sms_ttl,
                        "message": f"کد تأیید به شماره {clean_phone} ارسال شد."
                    }
                return {"success": False, "message": body.get("message") or "خطا در صدور کد تأیید جت"}
            return {"success": False, "message": body.get("message") or f"خطای سرور جت: {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"خطا در ارتباط با دیجی‌کالا جت: {e}"}

    async def verify_otp(self, phone: str, otp_code: str, challenge_token: Optional[str] = None) -> Dict[str, Any]:
        """Verifies Digikala Jet OTP code using challenge token."""
        from sabad.normalizer.persian_digits import to_english_digits
        clean_phone = to_english_digits(phone.strip())
        clean_code = to_english_digits(otp_code.strip())
        url = f"{self.base_url}/user/confirm-phone/"
        payload = {
            "phone": clean_phone,
            "code": clean_code,
            "token": challenge_token,
            "isLoginRedesign": True
        }
        try:
            resp = await self.client.post(url, json=payload)
            body = resp.json() if resp.status_code in [200, 400] else {}
            if resp.status_code == 200:
                data = body.get("data", {})
                user_token = data.get("token")
                if user_token:
                    SessionManager.save_tokens(
                        self.platform_name,
                        token=user_token,
                        phone=clean_phone,
                        metadata=data
                    )
                    return {"success": True, "message": "ورود به دیجی‌کالا جت با موفقیت انجام شد."}
            return {"success": False, "message": body.get("message") or "کد تأیید وارد شده نامعتبر یا منقضی است."}
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
