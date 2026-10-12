# Spec 02: Data Models & Domain Contracts

> **Status**: Approved & Verified  
> **Source Directory**: `sabad/models/`  
> **Validation Framework**: Pydantic v2 (`BaseModel`, `Field`)

---

## 1. Catalog Models (`sabad/models/catalog.py`)

### `StoreItem`
Represents an individual stock keeping unit (SKU) returned by a store's catalog search.

| Field | Type | Description | Unit / Constraint |
|:---|:---|:---|:---|
| `platform` | `str` | Platform identifier (`snapp_market`, `digikala_jet`, `okala`) | - |
| `store_id` | `str` | Vendor or branch ID | - |
| `product_id` | `str` | Platform product SKU identifier | - |
| `title` | `str` | Product title in Persian | Raw catalog text |
| `brand` | `Optional[str]` | Brand name (if parsed from API) | - |
| `base_price` | `float` | Original pre-discount price | **Tomans** (>= 1.0) |
| `discount_price` | `float` | Final selling price after discount | **Tomans** (>= 1.0) |
| `discount_percent` | `float` | Discount percentage | 0.0 to 100.0 |
| `is_flash_deal` | `bool` | True if product is marked as special deal | - |
| `is_in_stock` | `bool` | True if item has inventory and positive price | Mandatory stock guard |
| `image_url` | `str` | Thumbnail or main image URL | - |

**Computed Property**:
- `saving_amount -> float`: `max(0.0, self.base_price - self.discount_price)` (in Tomans).

### `DeliveryTier`
Defines tiered delivery fee thresholds for a supermarket branch.

| Field | Type | Description |
|:---|:---|:---|
| `min_subtotal` | `float` | Lower bound of items subtotal in Tomans (inclusive) |
| `max_subtotal` | `Optional[float]` | Upper bound in Tomans (`None` indicates infinity/free delivery) |
| `fee` | `float` | Shipping fee in Tomans for this bracket |

### `StoreInfo`
Represents a serving branch/vendor resolved for the user's geolocation.

| Field | Type | Description |
|:---|:---|:---|
| `platform` | `str` | `snapp_market` \| `digikala_jet` \| `okala` |
| `store_id` | `str` | Unique branch ID |
| `title` | `str` | Branch title (e.g., "هایپراستار ارم", "افق کوروش وصال") |
| `is_open` | `bool` | True if store is currently accepting orders |
| `minimum_order_value` | `float` | Minimum Order Value (MOV) in **Tomans** |
| `delivery_tiers` | `List[DeliveryTier]` | Applicable delivery fee tiers |

---

## 2. Grocery & Normalizer Models (`sabad/models/grocery.py`)

### `ParsedGroceryItem`
A single line item parsed from Persian natural language input.

| Field | Type | Description | Examples |
|:---|:---|:---|:---|
| `raw_text` | `str` | Original phrase as written by user | `"دو تا شیر پرچرب کاله یک لیتری"` |
| `name` | `str` | Core product noun | `"شیر"`, `"مایع ظرفشویی"`, `"پنیر"` |
| `brand` | `Optional[str]` | Requested brand name | `"کاله"`, `"پریل"`, `"ویلی"` |
| `quantity` | `int` | Unit quantity multiplier (>= 1) | `2`, `1`, `3` |
| `volume_weight` | `Optional[float]` | Numeric size / weight | `1.0`, `350.0`, `4.0`, `955.0` |
| `unit` | `Optional[str]` | Standardized unit | `"لیتر"`, `"میلی‌لیتر"`, `"کیلوگرم"`, `"گرم"` |
| `fat_percentage` | `Optional[float]` | Dairy fat level | `3.0` (پرچرب), `1.5` (کم‌چرب) |
| `category` | `Optional[str]` | Category taxonomy | `"لبنیات"`, `"شوینده"`, `"خواربار"` |

**Computed Property**:
- `display_title -> str`: Human-readable Persian summary, e.g., `"2 عدد شیر کاله 1 لیتر 3٪ چربی"`.

### `ParsedGroceryBasket`
Container for a parsed user input:
- `raw_input`: `str`
- `items`: `List[ParsedGroceryItem]`
- `engine`: `str` (`"rule_based"` or `"gemini"`)

---

## 3. Optimization Models (`sabad/models/optimization.py`)

### `BasketItemAssignment`
An individual SKU assignment in an order plan:
- `item`: `StoreItem`
- `quantity`: `int`
- `line_total`: `float` (`item.discount_price * quantity`)
- `nominal_saving`: `float` (`item.saving_amount * quantity`)

### `StoreOrder`
Fulfillment order from a single store:
- `platform`: `str`
- `store_id`: `str`
- `items`: `List[BasketItemAssignment]`
- `items_subtotal`: `float` (Tomans)
- `delivery_fee`: `float` (Tomans)
- `total_cost`: `float` (`items_subtotal + delivery_fee`)
- `total_savings`: `float` (Tomans)
- `minimum_order_value`: `float` (Tomans)
- `meets_mov`: `bool` (`items_subtotal >= minimum_order_value`)
- `missing_items_count`: `int` (Items requested but unavailable)

### `OptimizationResult`
Aggregate output of the optimization engine:
- `single_store_orders`: `Dict[str, Optional[StoreOrder]]`
- `optimal_orders`: `List[StoreOrder]`
- `is_multi_store`: `bool`
- `total_items_cost`: `float`
- `total_delivery_fees`: `float`
- `grand_total_cost`: `float`
- `total_discounts_saved`: `float`
- `net_savings_versus_worst`: `float`
- `net_savings_versus_best_single`: `float`
- `trap_audit`: `TrapAuditor`
