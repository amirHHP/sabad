"""
Okala Live Platform Adapter (Ofoq Kourosh & Emin).
Connects directly to live apigateway.okala.com endpoints.
"""

from typing import List, Optional, Dict, Any
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
        self.client = httpx.AsyncClient(
            headers=OKALA_HEADERS,
            timeout=HTTP_TIMEOUT,
            verify=False  # Required for Iranian internal SSL root chain
        )
        self._cached_store_id: Optional[str] = None
        self._cached_store_title: Optional[str] = None

    @property
    def platform_name(self) -> str:
        return "okala"

    @property
    def platform_title_fa(self) -> str:
        return "افق کوروش / اکالا"

    def is_authenticated(self) -> bool:
        return SessionManager.is_authenticated(self.platform_name)

    async def get_store_info(self, lat: float, lng: float) -> Optional[StoreInfo]:
        """Resolves local Ofoq Kourosh store dynamically and retrieves live MOV and delivery details."""
        nearby_url = f"{self.base_url}/api/opex/v4/stores/nearby?latitude={lat}&longitude={lng}"
        try:
            resp = await self.client.get(nearby_url)
            if resp.status_code == 200:
                payload = resp.json()
                stores = payload.get("data", {}).get("stores", [])
                
                # Prioritize Ofoq Kourosh branch, then any supermarket
                selected_store = None
                for s in stores:
                    cat_name = s.get("storeCategoryName", "")
                    partner_name = s.get("partnerName", "")
                    if "افق کوروش" in cat_name or "افق کوروش" in partner_name:
                        selected_store = s
                        break
                if not selected_store and stores:
                    selected_store = stores[0]

                if selected_store:
                    store_id = str(selected_store.get("storeId"))
                    store_name = selected_store.get("storeName") or "افق کوروش"
                    self._cached_store_id = store_id
                    self._cached_store_title = store_name

                    # Fetch store details for live MOV and delivery rules
                    details_url = (
                        f"{self.base_url}/api/opex/v2/stores/details"
                        f"?Latitude={lat}&longitude={lng}&StoreId={store_id}&customerSegments=0"
                    )
                    details_resp = await self.client.get(details_url)
                    mov_tomans = DEFAULT_MOV_TOMANS["okala"]
                    is_open = True
                    delivery_fee = 25000.0

                    if details_resp.status_code == 200:
                        ddata = details_resp.json().get("data", {})
                        min_order_rials = ddata.get("minimumOrder")
                        if min_order_rials:
                            mov_tomans = self.rials_to_tomans(min_order_rials, fallback=DEFAULT_MOV_TOMANS["okala"])
                        is_open = ddata.get("isActive", True) and ddata.get("isExist", True)
                        
                        raw_cost = ddata.get("cost")
                        delivery_fee = self.rials_to_tomans(raw_cost, fallback=25000.0)

                    tiers = [
                        DeliveryTier(min_subtotal=0, max_subtotal=400000, fee=delivery_fee),
                        DeliveryTier(min_subtotal=400000, max_subtotal=None, fee=0),
                    ]

                    return StoreInfo(
                        platform=self.platform_name,
                        store_id=store_id,
                        title=f"افق کوروش ({store_name})",
                        is_open=is_open,
                        minimum_order_value=mov_tomans,
                        delivery_tiers=tiers
                    )
        except Exception as e:
            self.note_store_error("store_info", e)

        # Fallback if connection fails
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

    async def _ensure_store_id(self, lat: float, lng: float) -> str:
        """Returns the active nearby store id for this location."""
        if not self._cached_store_id:
            info = await self.get_store_info(lat, lng)
            if info:
                self._cached_store_id = info.store_id
        return self._cached_store_id or "2319"

    async def search(self, query: str, lat: float, lng: float) -> List[StoreItem]:
        """Queries live Okala catalog for the dynamically resolved store branch."""
        store_id = await self._ensure_store_id(lat, lng)
        encoded_q = urllib.parse.quote(query)
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
                if not entities and isinstance(payload.get("data"), dict):
                    data = payload["data"]
                    entities = data.get("entities") or data.get("products") or data.get("items") or data.get("results") or []
                if isinstance(entities, dict):
                    entities = entities.get("items") or entities.get("results") or entities.get("entities") or []
                if not isinstance(entities, list):
                    entities = []
                
                for e in entities:
                    raw_price = e.get("price")
                    base_price_tomans = self.rials_to_tomans(raw_price, fallback=0.0)

                    raw_pct = e.get("discountPercent")
                    try:
                        discount_pct = float(raw_pct) if raw_pct is not None else 0.0
                    except (ValueError, TypeError):
                        discount_pct = 0.0

                    ok_price_raw = e.get("okPrice")
                    if ok_price_raw is not None:
                        try:
                            ok_val = float(ok_price_raw)
                            selling_price_tomans = self.rials_to_tomans(ok_val, fallback=0.0) if ok_val > 0 else (
                                max(1.0, base_price_tomans - base_price_tomans * (discount_pct / 100.0)) if base_price_tomans > 0 else 0.0
                            )
                        except (ValueError, TypeError):
                            discount_tomans = base_price_tomans * (discount_pct / 100.0)
                            selling_price_tomans = max(1.0, base_price_tomans - discount_tomans) if base_price_tomans > 0 else 0.0
                    else:
                        discount_tomans = base_price_tomans * (discount_pct / 100.0)
                        selling_price_tomans = max(1.0, base_price_tomans - discount_tomans) if base_price_tomans > 0 else 0.0

                    if base_price_tomans > 0 and selling_price_tomans > 0 and discount_pct == 0.0 and base_price_tomans > selling_price_tomans:
                        discount_pct = round(((base_price_tomans - selling_price_tomans) / base_price_tomans) * 100.0, 1)

                    product_id = str(e.get("id"))
                    name = e.get("name") or e.get("highlightName") or ""
                    img = self.first_url(e.get("imageUrl") or e.get("images") or e.get("image"))

                    quantity_val = e.get("quantity")
                    try:
                        has_quantity = int(quantity_val) > 0 if quantity_val is not None else True
                    except (ValueError, TypeError):
                        has_quantity = True

                    is_in_stock = has_quantity and base_price_tomans > 0

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
                        is_in_stock=is_in_stock,
                        image_url=img,
                        product_url=self.first_url(e.get("url") or e.get("productUrl") or e.get("product_url") or e.get("webUrl") or e.get("link")),
                    ))
        except Exception as err:
            self.note_store_error("search", err, reraise_timeout=True)

        return items

    async def get_flash_deals(self, lat: float, lng: float) -> List[StoreItem]:
        """Fetches timed special discounts from the resolved Okala store."""
        store_id = await self._ensure_store_id(lat, lng)
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
                    raw_price = e.get("price")
                    base_t = self.rials_to_tomans(raw_price, fallback=0.0)

                    raw_pct = e.get("discountPercent")
                    try:
                        discount_pct = float(raw_pct) if raw_pct is not None else 0.0
                    except (ValueError, TypeError):
                        discount_pct = 0.0

                    ok_price_raw = e.get("okPrice")
                    if ok_price_raw is not None:
                        try:
                            ok_val = float(ok_price_raw)
                            sell_t = self.rials_to_tomans(ok_val, fallback=0.0) if ok_val > 0 else (
                                max(1.0, base_t - base_t * (discount_pct / 100.0)) if base_t > 0 else 0.0
                            )
                        except (ValueError, TypeError):
                            disc_t = base_t * (discount_pct / 100.0)
                            sell_t = max(1.0, base_t - disc_t) if base_t > 0 else 0.0
                    else:
                        disc_t = base_t * (discount_pct / 100.0)
                        sell_t = max(1.0, base_t - disc_t) if base_t > 0 else 0.0

                    if base_t > 0 and sell_t > 0 and discount_pct == 0.0 and base_t > sell_t:
                        discount_pct = round(((base_t - sell_t) / base_t) * 100.0, 1)

                    quantity_val = e.get("quantity")
                    try:
                        has_quantity = int(quantity_val) > 0 if quantity_val is not None else True
                    except (ValueError, TypeError):
                        has_quantity = True

                    is_in_stock = has_quantity and base_t > 0

                    deals.append(StoreItem(
                        platform=self.platform_name,
                        store_id=store_id,
                        product_id=str(e.get("id")),
                        title=e.get("name", ""),
                        base_price=base_t,
                        discount_price=sell_t,
                        discount_percent=discount_pct,
                        is_flash_deal=True,
                        is_in_stock=is_in_stock,
                        image_url=self.first_url(e.get("imageUrl") or e.get("images") or e.get("image")),
                        product_url=self.first_url(e.get("url") or e.get("productUrl") or e.get("product_url") or e.get("webUrl") or e.get("link")),
                    ))
        except Exception as err:
            self.note_store_error("flash_deals", err)

        return deals

    async def send_otp(self, phone: str) -> Dict[str, Any]:
        """Sends OTP SMS code to the user's phone via Okala customer gateway."""
        from sabad.normalizer.persian_digits import to_english_digits
        clean_phone = to_english_digits(phone.strip())
        url = f"{self.base_url}/api/voyager/C/CustomerAccount/OTPRegister"
        payload = {
            "mobile": clean_phone,
            "deviceTypeCode": 0,
            "confirmTerms": True,
            "notRobot": False,
            "otpType": 0,
            "ValidationCodeCreateReason": 0,
            "OtpApp": 0,
            "IsAppOnly": False,
            "AppVersion": "1.0.0"
        }
        try:
            resp = await self.client.post(url, json=payload)
            body = resp.json() if resp.status_code in [200, 400] else {}
            if resp.status_code == 200:
                if body.get("success", False):
                    return {"success": True, "message": "کد تأیید با موفقیت ارسال شد."}
                return {"success": False, "message": body.get("message") or "ارسال کد با خطا مواجه شد."}
            return {"success": False, "message": body.get("message") or f"خطای سرور: {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"خطا در ارتباط با سرور اکالا: {e}"}

    async def verify_otp(self, phone: str, otp_code: str, challenge_token: Optional[str] = None) -> Dict[str, Any]:
        """Exchanges Okala OTP code for Bearer and refresh tokens."""
        from sabad.normalizer.persian_digits import to_english_digits
        clean_phone = to_english_digits(phone.strip())
        clean_code = to_english_digits(otp_code.strip())
        url = f"{self.base_url}/api/v1/accounts/tokens"
        form_data = {
            "grant_type": "customer_grant_type",
            "client_id": "customer_client_id",
            "client_secret": "u_M{'57j!%LI21#",
            "client_name": "customer_client_name",
            "device_type_code": "0",
            "scope": "offline_access",
            "mobile_number": clean_phone,
            "otp_code": clean_code,
        }
        headers = {**OKALA_HEADERS, "Content-Type": "application/x-www-form-urlencoded"}
        try:
            resp = await self.client.post(url, data=form_data, headers=headers)
            body = resp.json() if resp.status_code in [200, 400] else {}
            if resp.status_code == 200:
                access_token = body.get("access_token")
                refresh_token = body.get("refresh_token")
                if access_token:
                    SessionManager.save_tokens(
                        self.platform_name,
                        token=access_token,
                        refresh_token=refresh_token,
                        phone=clean_phone,
                        metadata=body
                    )
                    return {"success": True, "message": "احراز هویت با موفقیت انجام شد."}
            return {"success": False, "message": body.get("error_description") or body.get("message") or "کد تأیید وارد شده نامعتبر یا منقضی شده است."}
        except Exception as e:
            return {"success": False, "message": f"خطا در تأیید کد اکالا: {e}"}

    async def add_to_cart(self, mutations: List[CartItemMutation]) -> CartMutationResult:
        """Executes authenticated add-to-cart against Okala."""
        token = SessionManager.get_token(self.platform_name)
        active_store_id = self._cached_store_id or "2319"
        if not token:
            return CartMutationResult(
                platform=self.platform_name,
                store_id=active_store_id,
                success=False,
                error_message="نشست کاربری اکالا یافت نشد. لطفاً لاگین نمایید."
            )

        headers = {**OKALA_HEADERS, "Authorization": f"Bearer {token}"}
        items_added = 0

        for m in mutations:
            url = f"{self.base_url}/api/Basket/v2/ShoppingCart/AddToShoppingCart"
            target_store = m.store_id if m.store_id and m.store_id != "unknown" else active_store_id
            payload = {
                "StoreId": int(target_store) if str(target_store).isdigit() else 2223,
                "ProductId": int(m.product_id) if m.product_id.isdigit() else m.product_id,
                "Quantity": m.quantity,
            }
            try:
                resp = await self.client.post(url, json=payload, headers=headers)
                if resp.status_code in [200, 201]:
                    items_added += 1
            except Exception:
                pass

        return CartMutationResult(
            platform=self.platform_name,
            store_id=active_store_id,
            success=items_added > 0,
            items_added=items_added,
            verified_with_optimizer=items_added == len(mutations)
        )

    def get_checkout_url(self, store_id: Optional[str] = None) -> str:
        return "https://okala.com/cart"
