"""
Tapsi Market Live Platform Adapter.
Connects directly to live api.tapsi.food endpoints for quick-commerce and grocery catalog.
"""

from typing import List, Optional, Dict, Any
import asyncio
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

    _RESTAURANT_TERMS = (
        "رستوران", "کافه", "فست فود", "فست‌فود", "پیتزا", "برگر",
        "ساندویچ", "آشپزخانه", "کترینگ", "کباب", "غذا", "restaurant", "cafe",
        "fast food", "pizza", "burger", "sandwich", "kitchen", "catering",
    )
    _MARKET_TERMS = (
        "مارکت", "سوپر", "هایپر", "فروشگاه", "بقالی", "میوه", "پروتئین",
    )
    # Prepared-food and non-grocery verticals that dominate the unfiltered search.
    _NON_GROCERY_TYPE_TERMS = ("رستوران", "کافه", "فست", "آبمیوه", "بستنی", "پت")
    _FALLBACK_GROCERY_TYPE_IDS = ("5", "13", "6", "3", "12", "11")

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

    def _is_market_vendor(
        self,
        vendor_info: Dict[str, Any],
        product_info: Dict[str, Any],
        *,
        enforce_cached_vendor: bool = True,
    ) -> bool:
        """Reject restaurant results returned by Tapsi's shared discovery API."""
        vendor_code = str(vendor_info.get("vendorCode") or "")
        # The product endpoint is global across Food and Market.  When the
        # caller asks for the resolved branch we can enforce its code; search
        # itself may legitimately return a different market branch code.
        if enforce_cached_vendor and self._cached_store_id and self._cached_store_id != "tapsi_market_default":
            if vendor_code and vendor_code != self._cached_store_id:
                return False

        text_parts = []
        typed_fields = []
        for source in (vendor_info, product_info):
            for key in (
                "title", "name", "vendorType", "type", "businessType",
                "category", "categoryName", "serviceType", "vertical",
            ):
                value = source.get(key)
                if value is not None:
                    normalized = str(value).strip().lower()
                    text_parts.append(normalized)
                    if key in {"vendorType", "type", "businessType", "serviceType", "vertical"}:
                        typed_fields.append(normalized)
        searchable = " ".join(text_parts)
        if (
            not enforce_cached_vendor
            and self._cached_store_id
            and self._cached_store_id != "tapsi_market_default"
            and vendor_code
            and vendor_code != self._cached_store_id
            and not any(term in searchable for term in self._MARKET_TERMS)
        ):
            # A code mismatch without any market identity is more likely a
            # restaurant result from the shared discovery endpoint.
            return False
        if any(value in {"food", "restaurant", "cafe", "resturant", "غذایی", "رستورانی"} for value in typed_fields):
            return False
        if any(term in searchable for term in self._RESTAURANT_TERMS):
            return False
        # Unknown vendor metadata is allowed for backward compatibility with
        # the API and existing test fixtures. The restaurant deny-list and the
        # resolved branch ID above are the authoritative guards.
        return True

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
                        if not self._is_market_vendor(v_info, {}):
                            continue
                        if any(k in title for k in self._MARKET_TERMS):
                            selected_vendor = v
                            break
                    target_vendor = selected_vendor or next(
                        (v for v in vendors if self._is_market_vendor(v.get("vendorInfo", {}), {})),
                        None,
                    )
                    if target_vendor is None:
                        # The discovery endpoint returned Food-only vendors;
                        # keep the fallback branch instead of binding the
                        # session to a restaurant and filtering the catalog.
                        raise ValueError("no market vendor in discovery response")
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
            self.note_store_error("store_info", e)

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

    def _parse_search_payload(self, payload: Any) -> List[StoreItem]:
        """Turn a product-search payload into grocery items, dropping restaurants."""
        if not isinstance(payload, dict):
            return []
        results = payload.get("data", [])
        if not results and isinstance(payload.get("products"), list):
            results = payload.get("products")
        if isinstance(results, dict):
            results = results.get("items") or results.get("products") or results.get("results") or results.get("data") or []
        if not isinstance(results, list):
            return []

        items: List[StoreItem] = []
        seen_ids = set()
        for row in results:
            if not isinstance(row, dict):
                continue
            product_info = row.get("productInfo") if isinstance(row.get("productInfo"), dict) else {}
            vendor_info = row.get("vendorInfo") if isinstance(row.get("vendorInfo"), dict) else {}
            variants = row.get("subDocs") if isinstance(row.get("subDocs"), list) else []
            candidates = [variant for variant in variants if isinstance(variant, dict)]
            if product_info:
                candidates.append(product_info)
            if not candidates and (row.get("name") or row.get("price") is not None):
                candidates = [row]
            for variant in candidates:
                # Shared Food/Market discovery can return a different market
                # branch than the nearby vendor. Keep the restaurant deny-list,
                # but do not drop a grocery result only because the codes differ.
                if not self._is_market_vendor(vendor_info, variant, enforce_cached_vendor=False):
                    continue
                base_price = float(variant.get("price") or 0.0)
                discount_price = float(variant.get("priceAfterDiscount") or base_price or 0.0)
                if discount_price <= 0 and base_price > 0:
                    discount_price = base_price
                raw_pct = variant.get("discountRatio")
                try:
                    pct = float(raw_pct) if raw_pct is not None else 0.0
                except (ValueError, TypeError):
                    pct = 0.0
                if pct == 0.0 and base_price > discount_price > 0:
                    pct = round(((base_price - discount_price) / base_price) * 100.0, 1)

                vendor_status = vendor_info.get("vendorStatus", True)
                is_in_stock = (discount_price > 0) and (vendor_status is True or vendor_status == "Open")
                product_id = str(variant.get("id") or variant.get("headerId") or row.get("id") or "")
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
                items.append(StoreItem(
                    platform=self.platform_name,
                    store_id=str(vendor_info.get("vendorCode") or self._cached_store_id or "tapsi_market"),
                    product_id=product_id,
                    title=variant.get("name") or product_info.get("name") or "",
                    brand=None,
                    base_price=base_price,
                    discount_price=discount_price,
                    discount_percent=round(pct, 1),
                    is_flash_deal=pct >= 20.0,
                    is_in_stock=is_in_stock,
                    image_url=self.first_url(variant.get("images") or variant.get("image") or variant.get("imageUrl")),
                    product_url=self.first_url(variant.get("url") or variant.get("productUrl") or variant.get("product_url") or variant.get("webUrl") or variant.get("link")),
                ))
        items.sort(key=lambda item: not item.is_in_stock)
        return items

    @classmethod
    def _grocery_type_ids(cls, payload: Any) -> List[str]:
        """Keep grocery verticals from a facets response and drop restaurants."""
        data = payload.get("data") if isinstance(payload, dict) else None
        business_types = data.get("businessTypes") if isinstance(data, dict) else None
        if not isinstance(business_types, list):
            return []
        ids: List[str] = []
        for entry in business_types:
            if not isinstance(entry, dict):
                continue
            label = f"{entry.get('faName') or ''} {entry.get('name') or ''}"
            if any(term in label for term in cls._NON_GROCERY_TYPE_TERMS):
                continue
            try:
                count = int(entry.get("count") or 0)
            except (TypeError, ValueError):
                count = 0
            if count <= 0 or entry.get("id") is None:
                continue
            type_id = str(entry.get("id"))
            if type_id not in ids:
                ids.append(type_id)
        return ids[:6]

    async def _search_business_type(self, query: str, lat: float, lng: float, business_type_id: str) -> List[StoreItem]:
        """Search one grocery vertical. The API ignores a list of type ids."""
        encoded_q = urllib.parse.quote(query)
        url = (
            f"{self.base_url}/v1/api/search-discovery/Search/product-search"
            f"?latitude={lat}&longitude={lng}&query={encoded_q}"
            f"&businessTypeIds={urllib.parse.quote(business_type_id)}&pageNumber=1&pageSize=24"
        )
        try:
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return []
            return self._parse_search_payload(resp.json())
        except Exception as exc:
            self.note_store_error("search", exc, reraise_timeout=True)
            return []

    async def search(self, query: str, lat: float, lng: float) -> List[StoreItem]:
        """Queries the grocery verticals of Tapsi's shared discovery API.

        An unfiltered product search returns restaurants first. Those rows are
        discarded by the market filter, so the basket looks empty even when a
        protein shop or grocery nearby has the item.
        """
        encoded_q = urllib.parse.quote(query)
        facet_url = (
            f"{self.base_url}/v1/api/search-discovery/Search/facets"
            f"?latitude={lat}&longitude={lng}&query={encoded_q}"
        )
        payload: Dict[str, Any] = {}
        try:
            resp = await self.client.get(facet_url)
            if resp.status_code == 200:
                body = resp.json()
                payload = body if isinstance(body, dict) else {}
        except Exception as exc:
            self.note_store_error("search", exc, reraise_timeout=True)

        facet_data = payload.get("data")
        if isinstance(facet_data, dict) and "businessTypes" in facet_data:
            type_ids = self._grocery_type_ids(payload)
        else:
            # Fixtures and the previous product-search contract return rows directly.
            direct_items = self._parse_search_payload(payload)
            if direct_items:
                return direct_items
            type_ids = list(self._FALLBACK_GROCERY_TYPE_IDS)

        if not type_ids:
            return []
        groups = await asyncio.gather(
            *(self._search_business_type(query, lat, lng, type_id) for type_id in type_ids)
        )
        merged: List[StoreItem] = []
        seen_ids = set()
        for group in groups:
            for item in group:
                if item.product_id in seen_ids:
                    continue
                seen_ids.add(item.product_id)
                merged.append(item)
        merged.sort(key=lambda item: not item.is_in_stock)
        return merged

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
