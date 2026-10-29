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
from sabad.normalizer.persian_digits import clean_persian_text

# Tokens that do not identify a category on their own.
_CATEGORY_STOPWORDS = {"و", "از", "با", "یا", "در", "برای"}


def _category_tokens(text: str) -> List[str]:
    """Split a Persian label into matchable words."""
    cleaned = clean_persian_text(text or "")
    return [part for part in cleaned.split(" ") if part and part not in _CATEGORY_STOPWORDS]


def best_category_slug(categories: List[Dict[str, Any]], query: str) -> Optional[str]:
    """Pick the Okala category slug whose name best matches a grocery query.

    Text search on Okala now requires a logged-in token. The public catalog is
    browsed by category slug, so "شیر" has to land on ``milk`` rather than a
    longer label such as "شیرینی" that merely shares a prefix.
    """
    query_tokens = _category_tokens(query)
    if not query_tokens:
        return None
    query_set = set(query_tokens)
    best_slug: Optional[str] = None
    best_key = None
    normalized_query = clean_persian_text(query)
    for category in categories:
        name = str(category.get("name") or "")
        slug = category.get("latinName") or category.get("slug")
        if not name or not slug:
            continue
        category_tokens = _category_tokens(name)
        if not category_tokens:
            continue
        overlap = len(query_set & set(category_tokens))
        if overlap == 0:
            continue
        exact = int(category_tokens == query_tokens or clean_persian_text(name) == normalized_query)
        extra = len(category_tokens) - overlap
        key = (overlap, exact, -extra, -len(name))
        if best_key is None or key > best_key:
            best_key = key
            best_slug = str(slug)
    return best_slug


def _flatten_categories(nodes: Any) -> List[Dict[str, Any]]:
    """Walk the nearby-category tree into a flat name/slug list."""
    flat: List[Dict[str, Any]] = []
    if not isinstance(nodes, list):
        return flat
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("name") and (node.get("latinName") or node.get("slug")):
            flat.append(node)
        flat.extend(_flatten_categories(node.get("children")))
    return flat


def _catalog_rows(payload: Any) -> List[Dict[str, Any]]:
    """Normalize the product shapes Okala has used for search and category pages."""
    if not isinstance(payload, dict):
        return []
    rows: List[Dict[str, Any]] = []
    entities = payload.get("entities")
    if isinstance(entities, list):
        for entry in entities:
            if not isinstance(entry, dict):
                continue
            nested = entry.get("products")
            if isinstance(nested, list):
                rows.extend(product for product in nested if isinstance(product, dict))
            elif entry.get("name") or entry.get("price") is not None:
                rows.append(entry)
        if rows:
            return rows
    data = payload.get("data")
    if isinstance(data, list):
        return [
            product for product in data
            if isinstance(product, dict) and (product.get("name") or product.get("price") is not None)
        ]
    if isinstance(data, dict):
        for key in ("entities", "products", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [product for product in value if isinstance(product, dict)]
    return []


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
        self._category_cache: Optional[List[Dict[str, Any]]] = None

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

    def _items_from_payload(self, payload: Any, store_id: str, *, force_flash: bool = False) -> List[StoreItem]:
        """Map an Okala catalog payload onto store items, in Tomans."""
        items: List[StoreItem] = []
        for entry in _catalog_rows(payload):
            raw_price = entry.get("price")
            base_price_tomans = self.rials_to_tomans(raw_price, fallback=0.0)

            raw_pct = entry.get("discountPercent")
            try:
                discount_pct = float(raw_pct) if raw_pct is not None else 0.0
            except (ValueError, TypeError):
                discount_pct = 0.0

            ok_price_raw = entry.get("okPrice")
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

            product_id = str(entry.get("id") or entry.get("productId") or "")
            name = entry.get("name") or entry.get("highlightName") or ""
            quantity_val = entry.get("quantity")
            try:
                has_quantity = int(quantity_val) > 0 if quantity_val is not None else True
            except (ValueError, TypeError):
                has_quantity = True
            row_store = str(entry.get("storeId") or store_id)
            items.append(StoreItem(
                platform=self.platform_name,
                store_id=row_store,
                product_id=product_id,
                title=name,
                brand=None,
                base_price=base_price_tomans,
                discount_price=selling_price_tomans,
                discount_percent=discount_pct,
                is_flash_deal=True if force_flash else discount_pct >= 25.0,
                is_in_stock=has_quantity and base_price_tomans > 0,
                image_url=self.first_url(entry.get("imageUrl") or entry.get("images") or entry.get("image")),
                product_url=self.first_url(entry.get("url") or entry.get("productUrl") or entry.get("product_url") or entry.get("webUrl") or entry.get("link")),
            ))
        return items

    async def _load_categories(self, lat: float, lng: float) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Return nearby categories, or a catalog payload when the response is already products.

        Recorded fixtures and the retired search endpoint return product rows.
        The live category tree is cached so a basket does not download it once per item.
        """
        if self._category_cache is not None:
            return self._category_cache, None
        url = f"{self.base_url}/api/unicorn/v3/categories/nearby?lat={lat}&lon={lng}"
        try:
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return [], None
            payload = resp.json()
        except Exception as err:
            self.note_store_error("categories", err, reraise_timeout=True)
            return [], None

        data = payload.get("data") if isinstance(payload, dict) else None
        categories = _flatten_categories(data.get("categories") if isinstance(data, dict) else None)
        if categories:
            self._category_cache = categories
            return categories, None
        if _catalog_rows(payload):
            return [], payload
        self._category_cache = []
        return [], None

    async def search(self, query: str, lat: float, lng: float) -> List[StoreItem]:
        """Queries the public Okala catalog for the resolved store branch.

        ``/api/Search/v1/Product/Search`` now 404s, and the replacement text
        search requires a customer token. Category pages stay public, so a
        query is matched to a category slug and read from that store's shelf.
        """
        store_id = await self._ensure_store_id(lat, lng)
        try:
            categories, direct_catalog = await self._load_categories(lat, lng)
            if direct_catalog is not None:
                return self._items_from_payload(direct_catalog, store_id)
            slug = best_category_slug(categories, query)
            if not slug:
                return []
            encoded_slug = urllib.parse.quote(slug)
            url = (
                f"{self.base_url}/api/unicorn/v2/products/store/{store_id}"
                f"?slug={encoded_slug}&lat={lat}&lon={lng}"
            )
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return []
            return self._items_from_payload(resp.json(), store_id)
        except Exception as err:
            self.note_store_error("search", err, reraise_timeout=True)
            return []

    async def get_flash_deals(self, lat: float, lng: float) -> List[StoreItem]:
        """Fetches timed special discounts from the resolved Okala store."""
        store_id = await self._ensure_store_id(lat, lng)
        url = (
            f"{self.base_url}/api/carousel/v4/offers/highest-discount"
            f"?storeId={store_id}&take=20&page=1"
        )
        try:
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return []
            deals = self._items_from_payload(resp.json(), store_id, force_flash=True)
            return [deal for deal in deals if deal.discount_percent > 0]
        except Exception as err:
            self.note_store_error("flash_deals", err)
            return []

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
