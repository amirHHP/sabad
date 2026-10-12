"""
Tapsi Market Live Platform Adapter.
Connects directly to live api.tapsi.food endpoints for quick-commerce and grocery catalog.
"""

from typing import List, Optional, Dict, Any
import urllib.parse
import httpx

from sabad.adapters.base import BaseStoreAdapter
from sabad.adapters.session_manager import SessionManager
from sabad.config import (
    TAPSI_MARKET_BASE_URL,
    TAPSI_HEADERS,
    HTTP_TIMEOUT,
    DEFAULT_MOV_TOMANS,
)
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier
from sabad.models.dispatch import CartItemMutation, CartMutationResult


class TapsiMarketAdapter(BaseStoreAdapter):
    """Live API client for Tapsi Market / Food quick-commerce catalog."""

    def __init__(self, base_url: str = TAPSI_MARKET_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            headers=TAPSI_HEADERS,
            timeout=HTTP_TIMEOUT,
            verify=False
        )
        self._cached_store_id: Optional[str] = None
        self._cached_store_title: Optional[str] = None

    @property
    def platform_name(self) -> str:
        return "tapsi_market"

    @property
    def platform_title_fa(self) -> str:
        return "تپسی مارکت"

    def is_authenticated(self) -> bool:
        return SessionManager.is_authenticated(self.platform_name)

    async def get_store_info(self, lat: float, lng: float) -> Optional[StoreInfo]:
        """Resolves serving grocery or market vendor, live delivery fee, and MOV."""
        search_vendor_url = (
            f"{self.base_url}/v1/api/search-discovery/Search/vendor-search"
            f"?latitude={lat}&longitude={lng}&query=سوپرمارکت&pageSize=5"
        )
        try:
            resp = await self.client.get(search_vendor_url)
            if resp.status_code == 200:
                payload = resp.json()
                vendors = payload.get("data", [])
                if vendors:
                    # Select nearest supermarket / market vendor
                    selected_vendor = None
                    for v in vendors:
                        v_info = v.get("vendorInfo", {})
                        title = v_info.get("title", "")
                        if any(k in title for k in ["مارکت", "هایپر", "سوپر", "پروتئین", "میوه"]):
                            selected_vendor = v
                            break
                    target_vendor = selected_vendor or vendors[0]
                    v_code = str(target_vendor.get("vendorCode") or "tapsi_market")
                    v_info = target_vendor.get("vendorInfo", {})
                    v_title = v_info.get("title", "تپسی مارکت")
                    self._cached_store_id = v_code
                    self._cached_store_title = v_title

                    # Query detailed vendor endpoint for live delivery tiers & MOV
                    detail_url = f"{self.base_url}/v2/api/Vendor/{v_code}/vendor?latitude={lat}&longitude={lng}"
                    detail_resp = await self.client.get(detail_url)
                    mov_tomans = DEFAULT_MOV_TOMANS["tapsi_market"]
                    delivery_fee = 30000.0
                    is_open = True

                    if detail_resp.status_code == 200:
                        ddata = detail_resp.json().get("data", {}).get("vendor", {})
                        raw_mov = ddata.get("minimumBasket")
                        if raw_mov is not None and float(raw_mov) > 0:
                            mov_tomans = float(raw_mov)
                        is_open = ddata.get("vendorStatus") == "Open"

                        # Extract delivery fee from deliveryTypes
                        d_types = ddata.get("deliveryTypes", [])
                        if d_types and isinstance(d_types, list):
                            first_dt = d_types[0]
                            if isinstance(first_dt, dict) and first_dt.get("deliveryPrice") is not None:
                                delivery_fee = float(first_dt.get("deliveryPrice"))
                        elif v_info.get("deliveryPrice") is not None:
                            delivery_fee = float(v_info.get("deliveryPrice"))

                    tiers = [
                        DeliveryTier(min_subtotal=0, max_subtotal=None, fee=delivery_fee),
                    ]

                    return StoreInfo(
                        platform=self.platform_name,
                        store_id=v_code,
                        title=f"تپسی مارکت ({v_title})",
                        is_open=is_open,
                        minimum_order_value=mov_tomans,
                        delivery_tiers=tiers,
                    )
        except Exception as e:
            print(f"Error fetching Tapsi Market store info: {e}")

        # Graceful fallback
        return StoreInfo(
            platform=self.platform_name,
            store_id="tapsi_market_default",
            title="سوپرمارکت تپسی مارکت",
            is_open=True,
            minimum_order_value=DEFAULT_MOV_TOMANS["tapsi_market"],
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=None, fee=30000.0),
            ]
        )

    async def search(self, query: str, lat: float, lng: float) -> List[StoreItem]:
        """Queries live catalog for the given search term and location."""
        encoded_q = urllib.parse.quote(query)
        url = (
            f"{self.base_url}/v1/api/search-discovery/Search/product-search"
            f"?latitude={lat}&longitude={lng}&query={encoded_q}&pageNumber=1&pageSize=24"
        )
        items: List[StoreItem] = []

        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                payload = resp.json()
                results = payload.get("data", [])
                for r in results:
                    p_info = r.get("productInfo", {})
                    v_info = r.get("vendorInfo", {})

                    base_price = float(p_info.get("price") or 0.0)
                    discount_price = float(p_info.get("priceAfterDiscount") or base_price or 0.0)
                    if discount_price <= 0 and base_price > 0:
                        discount_price = base_price

                    raw_pct = p_info.get("discountRatio")
                    try:
                        pct = float(raw_pct) if raw_pct is not None else 0.0
                    except (ValueError, TypeError):
                        pct = 0.0

                    if pct == 0.0 and base_price > discount_price > 0:
                        pct = round(((base_price - discount_price) / base_price) * 100.0, 1)

                    # In-stock check: price must be strictly positive and vendor active
                    v_status = v_info.get("vendorStatus", True)
                    is_in_stock = (discount_price > 0) and (v_status is True or v_status == "Open")

                    images = p_info.get("images", [])
                    image_url = images[0] if images and isinstance(images, list) else ""

                    p_id = str(p_info.get("id") or p_info.get("headerId") or r.get("id") or "")
                    v_code = str(v_info.get("vendorCode") or self._cached_store_id or "tapsi_market")

                    is_flash = pct >= 20.0

                    items.append(StoreItem(
                        platform=self.platform_name,
                        store_id=v_code,
                        product_id=p_id,
                        title=p_info.get("name", ""),
                        brand=None,
                        base_price=base_price,
                        discount_price=discount_price,
                        discount_percent=round(pct, 1),
                        is_flash_deal=is_flash,
                        is_in_stock=is_in_stock,
                        image_url=image_url,
                    ))
        except Exception as e:
            print(f"Error searching Tapsi Market: {e}")

        # Prioritize in-stock items first
        items.sort(key=lambda x: not x.is_in_stock)
        return items

    async def get_flash_deals(self, lat: float, lng: float) -> List[StoreItem]:
        """Discovers daily flash deals and promotional items."""
        deals: List[StoreItem] = []
        popular_seeds = ["شیر", "روغن", "پنیر", "ماست", "میوه"]
        for seed in popular_seeds:
            try:
                results = await self.search(seed, lat, lng)
                for item in results:
                    if item.is_flash_deal or item.discount_percent >= 15.0:
                        deals.append(item)
            except Exception:
                pass

        # Deduplicate deals by product_id
        unique_deals: List[StoreItem] = []
        seen_ids = set()
        for d in deals:
            if d.product_id not in seen_ids:
                seen_ids.add(d.product_id)
                unique_deals.append(d)

        return unique_deals

    async def send_otp(self, phone: str) -> Dict[str, Any]:
        """Sends OTP SMS challenge to user's phone via Tapsi Food / Market auth API."""
        from sabad.normalizer.persian_digits import to_english_digits
        clean_phone = to_english_digits(phone.strip())
        url = f"{self.base_url}/v1/api/Authentication/otp"
        payload = {"CellPhone": clean_phone, "redirect": ""}
        try:
            resp = await self.client.post(url, json=payload)
            body = resp.json() if resp.status_code in [200, 400] else {}
            if resp.status_code == 200:
                if body.get("status", False) or "ارسال شد" in body.get("message", ""):
                    return {
                        "success": True,
                        "message": f"کد تأیید تپسی مارکت به شماره {clean_phone} ارسال شد."
                    }
                return {"success": False, "message": body.get("message") or "خطا در ارسال کد تایید تپسی"}
            return {"success": False, "message": body.get("message") or f"خطای سرور تپسی: {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"خطا در ارتباط با تپسی مارکت: {e}"}

    async def verify_otp(self, phone: str, otp_code: str, challenge_token: Optional[str] = None) -> Dict[str, Any]:
        """Verifies OTP challenge and persists user session credentials."""
        from sabad.normalizer.persian_digits import to_english_digits
        clean_phone = to_english_digits(phone.strip())
        clean_code = to_english_digits(otp_code.strip())
        url = f"{self.base_url}/v1/api/Authentication/token"
        payload = {
            "cellPhone": clean_phone,
            "otpCode": clean_code,
            "redirect": ""
        }
        try:
            resp = await self.client.post(url, json=payload)
            body = resp.json() if resp.status_code in [200, 400] else {}
            if resp.status_code == 200:
                token = body.get("token")
                refresh_token = body.get("refreshToken")
                if token:
                    SessionManager.save_tokens(
                        self.platform_name,
                        token=token,
                        refresh_token=refresh_token,
                        phone=clean_phone,
                        metadata=body
                    )
                    return {"success": True, "message": "ورود به تپسی مارکت با موفقیت انجام شد."}
            return {"success": False, "message": body.get("message") or "کد تأیید وارد شده نامعتبر است."}
        except Exception as e:
            return {"success": False, "message": f"خطا در تأیید کد تپسی مارکت: {e}"}

    async def add_to_cart(self, mutations: List[CartItemMutation]) -> CartMutationResult:
        """Executes authenticated add-to-cart mutations."""
        token = SessionManager.get_token(self.platform_name)
        active_store_id = self._cached_store_id or "tapsi_market"
        if not token:
            return CartMutationResult(
                platform=self.platform_name,
                store_id=active_store_id,
                success=False,
                error_message="نشست کاربری تپسی مارکت یافت نشد. لطفاً لاگین نمایید."
            )

        headers = {**TAPSI_HEADERS, "Authorization": f"Bearer {token}"}
        items_added = 0

        # Attempt remote cart addition if supported
        for m in mutations:
            target_store = m.store_id or active_store_id
            url = f"{self.base_url}/v3/api/Cart/{target_store}/item"
            payload = {
                "productId": int(m.product_id) if m.product_id.isdigit() else m.product_id,
                "quantity": m.quantity,
            }
            try:
                resp = await self.client.post(url, json=payload, headers=headers)
                if resp.status_code in [200, 201]:
                    items_added += 1
            except Exception:
                pass

        # If direct mutation succeeds or fallback to verified status
        return CartMutationResult(
            platform=self.platform_name,
            store_id=active_store_id,
            success=items_added > 0,
            items_added=items_added,
            verified_with_optimizer=items_added == len(mutations)
        )

    def get_checkout_url(self, store_id: Optional[str] = None) -> str:
        """Returns direct web checkout URL for user handoff."""
        if store_id and store_id != "tapsi_market_default":
            return f"https://tapsi.food/vendor/{store_id}"
        return "https://tapsi.food/basket/list"
