"""
SnappMarket Live Platform Adapter.
Connects directly to live svc.snapp.market endpoints.
"""

from typing import List, Optional, Dict, Any
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
        """Queries live vendors list to resolve the serving supermarket branch, delivery fee, and MOV."""
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
                    
                    # SnappMarket MOV is returned in Tomans
                    raw_mov = vdata.get("minimumOrderValue", 0)
                    mov_tomans = float(raw_mov) if raw_mov and float(raw_mov) > 0 else DEFAULT_MOV_TOMANS["snapp_market"]

                    # Live delivery fee from API (in Tomans)
                    raw_fee = vdata.get("deliveryFee")
                    fee_tomans = float(raw_fee) if raw_fee is not None else 29400.0
                    free_threshold = float(vdata.get("couponMinBasket", 450000.0))
                    
                    tiers = [
                        DeliveryTier(min_subtotal=0, max_subtotal=free_threshold, fee=fee_tomans),
                        DeliveryTier(min_subtotal=free_threshold, max_subtotal=None, fee=0),
                    ]
                    return StoreInfo(
                        platform=self.platform_name,
                        store_id=vendor_id,
                        title=title,
                        is_open=vdata.get("isOpen", True) and vdata.get("status", "ACTIVE") == "ACTIVE",
                        minimum_order_value=mov_tomans,
                        delivery_tiers=tiers
                    )
        except Exception as e:
            self.note_store_error("store_info", e)

        return StoreInfo(
            platform=self.platform_name,
            store_id="snapp_express",
            title="هایپراستار / اسنپ‌مارکت",
            is_open=True,
            minimum_order_value=DEFAULT_MOV_TOMANS["snapp_market"],
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=500000, fee=30000),
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
                        # Snapp API gives price & discount in Tomans
                        raw_price = p.get("price")
                        try:
                            base_price_tomans = float(raw_price) if raw_price is not None else 0.0
                        except (ValueError, TypeError):
                            base_price_tomans = 0.0

                        raw_discount = p.get("discount")
                        try:
                            discount_tomans = float(raw_discount) if raw_discount is not None else 0.0
                        except (ValueError, TypeError):
                            discount_tomans = 0.0

                        selling_price_tomans = max(1.0, base_price_tomans - discount_tomans) if base_price_tomans > 0 else 0.0
                        
                        pct = (discount_tomans / base_price_tomans * 100.0) if base_price_tomans > 0 else 0.0
                        is_flash = pct >= 25.0

                        thumb = self.first_url(p.get("images") or p.get("image") or p.get("imageUrl"))

                        # Stock availability from real API field; guard against price <= 0 or missing prices
                        stock_val = p.get("stock")
                        try:
                            is_in_stock = int(stock_val) > 0 if stock_val is not None else True
                        except (ValueError, TypeError):
                            is_in_stock = True

                        if base_price_tomans <= 0 or raw_price is None:
                            is_in_stock = False

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
                            is_in_stock=is_in_stock,
                            image_url=thumb,
                            product_url=self.first_url(p.get("url") or p.get("productUrl") or p.get("product_url") or p.get("webUrl") or p.get("link")),
                        ))
        except Exception as e:
            self.note_store_error("search", e, reraise_timeout=True)

        return items

    async def get_flash_deals(self, lat: float, lng: float) -> List[StoreItem]:
        """Fetches top discounted promotion items."""
        deals = await self.search("شگفت انگیز", lat, lng)
        if not deals:
            deals = await self.search("کالابرگ", lat, lng)
        return [d for d in deals if d.discount_percent >= 15.0]

    def _get_udid(self) -> str:
        """Retrieves or creates a persistent device UDID for SnappMarket API."""
        import uuid
        session = SessionManager.load_session(self.platform_name)
        udid = session.get("udid")
        if not udid:
            udid = str(uuid.uuid4())
            session["udid"] = udid
            SessionManager.save_session(self.platform_name, session)
        return udid

    async def send_otp(self, phone: str) -> Dict[str, Any]:
        """Sends OTP challenge to the user's phone via SnappMarket login endpoint."""
        from sabad.normalizer.persian_digits import to_english_digits
        clean_phone = to_english_digits(phone.strip())
        url = f"{self.base_url}/mobile/v4/user/loginMobileWithNoPass"
        params = {
            "client": "PWA",
            "deviceType": "PWA",
            "appVersion": "10.10.10",
            "UDID": self._get_udid(),
        }
        payload = {"cellphone": clean_phone, "optionalLoginToken": True}
        try:
            resp = await self.client.post(url, params=params, json=payload)
            body = resp.json() if resp.status_code in [200, 400] else {}
            if resp.status_code == 200 and body.get("status"):
                return {"success": True, "message": "کد تأیید با موفقیت پیامک شد."}
            err_msg = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else body.get("error")
            return {"success": False, "message": err_msg or body.get("message") or "ارسال کد ناموفق بود."}
        except Exception as e:
            return {"success": False, "message": f"خطا در ارسال کد اسنپ‌مارکت: {e}"}

    async def verify_otp(self, phone: str, otp_code: str, challenge_token: Optional[str] = None) -> Dict[str, Any]:
        """Exchanges SnappMarket OTP code for access token."""
        from sabad.normalizer.persian_digits import to_english_digits
        clean_phone = to_english_digits(phone.strip())
        clean_code = to_english_digits(otp_code.strip())
        url = f"{self.base_url}/mobile/v2/user/loginMobileWithToken"
        params = {
            "client": "PWA",
            "deviceType": "PWA",
            "appVersion": "10.10.10",
            "UDID": self._get_udid(),
        }
        payload = {"cellphone": clean_phone, "code": clean_code}
        headers = {**SNAPP_HEADERS, "Content-Type": "application/x-www-form-urlencoded"}
        try:
            # First try form-urlencoded as specified by SnappMarket web client
            resp = await self.client.post(url, params=params, data=payload, headers=headers)
            body = resp.json() if resp.status_code in [200, 400] else {}

            # If not successful, fallback to json payload
            if resp.status_code != 200 and not body.get("status"):
                fallback_resp = await self.client.post(url, params=params, json=payload)
                if fallback_resp.status_code == 200 or fallback_resp.json().get("status"):
                    resp = fallback_resp
                    body = fallback_resp.json()

            if resp.status_code == 200 and body.get("status"):
                data = body.get("data", {})
                oauth = data.get("oauth2Token") or data.get("oauth2_token") or {}
                access_token = (
                    oauth.get("accessToken")
                    or oauth.get("access_token")
                    or data.get("token")
                    or data.get("accessToken")
                    or data.get("access_token")
                )
                refresh_token = (
                    oauth.get("refreshToken")
                    or oauth.get("refresh_token")
                    or data.get("refreshToken")
                    or data.get("refresh_token")
                )
                if access_token:
                    SessionManager.save_tokens(
                        self.platform_name,
                        token=access_token,
                        refresh_token=refresh_token,
                        phone=clean_phone,
                        metadata=data
                    )
                    return {"success": True, "message": "ورود به اسنپ‌مارکت با موفقیت انجام شد."}
            
            err_obj = body.get("error", {})
            err_msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
            return {"success": False, "message": err_msg or body.get("message") or "کد تأیید نامعتبر یا منقضی شده است."}
        except Exception as e:
            return {"success": False, "message": f"خطا در تأیید کد اسنپ‌مارکت: {e}"}

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
            verified_with_optimizer=items_added == len(mutations)
        )

    def get_checkout_url(self, store_id: Optional[str] = None) -> str:
        return "https://snapp.market/cart"
