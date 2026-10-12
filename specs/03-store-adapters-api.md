# Spec 03: Store Adapters & Live API Contracts

> **Status**: Approved & Verified  
> **Source Directory**: `sabad/adapters/`  
> **Currency Unit Standard**: **Strict Iranian Toman (تومان)**

---

## 1. Currency Normalization Rule (CRITICAL)

```
┌─────────────────┬───────────────────┬───────────────────────────────────────────┐
│ Platform        │ Upstream Currency │ Normalization Required in Sabad           │
├─────────────────┼───────────────────┼───────────────────────────────────────────┤
│ SnappMarket     │ TOMANS (تومان)    │ NONE (Keep native Tomans intact)          │
│ Digikala Jet    │ RIALS (ریال)      │ Divide by 10.0 via `rials_to_tomans()`    │
│ Okala (Koorosh) │ RIALS (ریال)      │ Divide by 10.0 via `rials_to_tomans()`    │
└─────────────────┴───────────────────┴───────────────────────────────────────────┘
```

> [!CAUTION]
> **Historic Regression Warning**: Never divide SnappMarket search prices or discounts by 10!
> In SnappMarket's `/mobile/v3/search` API, `p["price"]` and `p["discount"]` are **already in Tomans**.
> Dividing by 10 causes a 10x deflation bug (e.g. 1.2M Tomans reported as 120k Tomans).

### Currency Conversion Function (`sabad/adapters/base.py`)
```python
def rials_to_tomans(val_rials: Optional[float], fallback: float = 0.0) -> float:
    """Converts upstream API values from Rials to Tomans with strict rounding."""
    if val_rials is None:
        return fallback
    try:
        fval = float(val_rials)
        return round(fval / 10.0, 1) if fval > 0 else fallback
    except (ValueError, TypeError):
        return fallback
```

---

## 2. SnappMarket Adapter (`sabad/adapters/snapp_market.py`)

- **Base URL**: `https://svc.snapp.market`
- **Default Headers**:
  - `User-Agent`: `Mozilla/5.0 ...`
  - `App-Version`: `pwa`
  - `Content-Type`: `application/json`

### Endpoints
1. **Branch & Vendor Resolution**:
   - `GET /express-vendor/general/vendors-list?lat={lat}&lng={lng}`
   - Resolves active serving branch, `deliveryFee` (in Tomans), and `minimumOrderValue` (in Tomans).
2. **Product Search**:
   - `GET /mobile/v3/search?query={encoded_q}&lat={lat}&lng={lng}`
   - Structure: `payload["data"]["vendor_product_variations"]["items"][...]["products"]`
   - Fields: `price` (Tomans), `discount` (Tomans), `stock` (int).
3. **Authentication (OTP)**:
   - Request Code: `POST /mobile/v4/user/loginMobileWithNoPass` (Payload: `cellphone`)
   - Verify Code: `POST /mobile/v2/user/loginMobileWithToken` (Payload: `cellphone`, `code`)
4. **Remote Cart Mutation**:
   - `POST /cart/v1/carts` (Headers: `Authorization: Bearer {token}`)
   - Web checkout URL: `https://snapp.market/cart`

---

## 3. Digikala Jet Adapter (`sabad/adapters/digikala_jet.py`)

- **Base URL**: `https://api.digikalajet.ir`
- **Default Headers**:
  - `User-Agent`: `Mozilla/5.0 ...`
  - `App-Version`: `2.0.0`
  - `Client-ID`: `jet-web-client`

### Endpoints
1. **Branch Resolution**:
   - `GET /user/address/v3/nearby-shops/?latitude={lat}&longitude={lng}`
   - Resolves nearest dark-store/supermarket `shop_id`.
2. **Product Search**:
   - `GET /products/search/all/?q={encoded_q}&latitude={lat}&longitude={lng}`
   - Structure: `payload["data"]["result"]`
   - Fields: `price` dictionary with `price` (Rials), `discount` (Rials), `status` (`"active"`).
   - **Guard**: If `r.get("price")` is missing or out of stock, do NOT default to 1 Toman; mark `is_in_stock = False`.
3. **Authentication (OTP)**:
   - Request Code: `POST /user/authenticate/` (Payload: `phone`)
   - Verify Code: `POST /user/login/` (Payload: `phone`, `code`)
4. **Remote Cart Mutation**:
   - `POST /cart/add/` (Payload: `shop_id`, `product_id`, `count`)
   - Web checkout URL: `https://www.digikalajet.com/cart`

---

## 4. Okala / Ofogh Koorosh Adapter (`sabad/adapters/okala.py`)

- **Base URL**: `https://apigateway.okala.com`
- **Default Headers**:
  - `User-Agent`: `Mozilla/5.0 ...`
  - `App-Version`: `11.0.0`
  - `Platform`: `Pwa`

### Endpoints
1. **Branch Resolution**:
   - `GET /api/Store/v1/NearbyStores?Latitude={lat}&Longitude={lng}&take=5`
   - Queries `GET /api/Store/v1/Detail/{store_id}` for `minimumOrder` (Rials) and `cost` (Rials).
2. **Product Search**:
   - `GET /api/Search/v1/Product/Search?StoreIds={store_id}&SearchText={encoded_q}&HasQuantity=true&Page=1&Take=20`
   - Structure: `payload["entities"]`
   - Fields: `price` (Rials), `discountPercent` (float or `None`), `quantity` (int).
   - **Guard**: `discountPercent` can be `None`; treat as `0.0`.
3. **Authentication (OTP)**:
   - Request Code: `POST /api/Account/v1/RegisterVerificationCode` (Payload: `mobile`)
   - Verify Code: `POST /api/Account/v1/VerifyCode` (Payload: `mobile`, `code`)
4. **Remote Cart Mutation**:
   - `POST /api/Cart/v1/Item` (Payload: `storeId`, `productId`, `count`)
   - Web checkout URL: `https://okala.com/cart`
