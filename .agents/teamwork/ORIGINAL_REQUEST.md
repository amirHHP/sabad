# Original User Request

## 2026-10-01T12:54:12Z

A production-grade cross-store grocery optimizer and automated cart dispatcher connecting directly to live Iranian quick-commerce endpoints (SnappMarket, Digikala Jet, Okala) to harvest daily flash deals, parse Persian shopping lists, solve optimal multi-store baskets, and execute cart dispatching.

Working directory: /Users/sotoon/personal/Sabad
Integrity mode: development

## Requirements

### R1. Live Reverse-Engineered Platform Adapters (SnappMarket, Digikala Jet, Okala)
Connect directly to live service APIs with spoofed browser/mobile headers and location-aware coordinates (`lat`, `lng`):
- **SnappMarket (`snapp.market`):** Support OTP login (`/api/v1/auth/otp/send`, `/api/v1/auth/otp/verify`) persisting Bearer tokens in `.sessions/`; live flash deal carousel scraper (`/api/v1/promotions/flash-deals`); live search (`/api/v1/search/products`); cart mutation (`POST /api/v1/cart/items`); and shipping fee tiered rule extraction.
- **Digikala Jet (`jet.digikala.com`):** Support SSO token / cookie authentication; live "شگفت‌انگیز جت" deal extractor; live search endpoint with store ID, pricing, discounts, and inventory status; and cart mutation (`POST /v1/cart/add/`).
- **Okala (`okala.com`):** Session management via Okala API tokens; scraper for "تخفیف‌های ویژه / تایم‌دار"; live product catalog query with package size & barcode mapping; and remote basket mutation.
- Dynamic error handling for rate-limiting (HTTP 429), session expiration (HTTP 401), and out-of-stock items. No mock data or fallback stubs in production paths.

### R2. Natural Language Persian Basket Normalizer
Ingest natural language Persian grocery prompts (e.g. "دو تا شیر پرچرب کاله یک لیتری، یه پنیر ویلی ۳۵۰ گرمی، یه مایع ظرفشویی پریل ۴ لیتری"). Extract structured specifications (item, brand, quantity, volume/weight, category) using a robust schema. Match extracted entities against live catalog search results via fuzzy string matching and strict attribute verification (brand, package volume, fat percentage) to guarantee zero incorrect SKU pairings.

### R3. Mathematical Basket Optimizer & Flash Deal Trap Auditor
Formulate and solve a combinatorial / Mixed-Integer Linear Program (MILP) model minimizing:
$$\text{Total Cost} = \sum_{s \in S} \left( \sum_{i \in I} \text{Price}(i, s) \cdot q_i \cdot x_{i, s} + \text{DeliveryFee}_s(\text{Subtotal}_s) \right)$$
Evaluate and output:
1. **Single-Store Best:** Cost breakdown if 100% of items are bought from SnappMarket, Digikala Jet, or Okala.
2. **Flash Deal Trap Audit:** Quantify whether buying a promotional loss-leader at store X forces the remaining items to be bought at higher margins or incurs surplus delivery fees that negate the deal's discount.
3. **Multi-Store Split:** Determine whether splitting the order across 2+ stores is net-positive after accounting for multiple shipping fees and minimum order thresholds.

### R4. Cart Dispatcher & Payment Handoff
Upon user confirmation, execute authenticated `add-to-cart` mutations against the winning platform(s), verify basket items and applied discounts match optimizer expectations, and provide direct checkout / payment gateway handoff links for completion.

### R5. Interactive Streamlit Web Dashboard (`app.py`)
Provide a Streamlit web application featuring:
1. **Connection Status Panel:** Real-time status badges for SnappMarket, Digikala Jet, and Okala sessions alongside active delivery GPS coordinates.
2. **Persian Basket Input:** Natural language text area with real-time parsed preview.
3. **Live Execution Pipeline:** Live search logs across all 3 stores, visual "تله‌ی شگفت‌انگیز" audit report, cost comparison matrix (items, discounts, shipping), and a one-click "افزودن مستقیم به سبد خرید" cart population trigger with checkout links.

## Verification Mechanisms

- **Automated Live Endpoint Verification:** A dedicated verification suite (`tests/verify_live_endpoints.py`) that queries live unauthenticated search and flash-deal endpoints for SnappMarket, Digikala Jet, and Okala using Tehran test coordinates, asserting valid JSON responses, non-empty catalog items, and live price/stock fields.
- **Normalizer Test Suite:** Programmatic unit tests covering diverse Persian quantity expressions, numerical formats (Persian and English digits), and edge cases (e.g., volume/fat mismatches).
- **Optimizer Verification Suite:** Unit tests for MILP solver validating single-store, multi-store split decisions, and flash-deal trap detection against controlled price/shipping matrices.
- **Session & Cart Test Harness:** Interactive CLI/test runner to verify OTP flow and cart mutation with live credentials without breaking automated CI.

## Acceptance Criteria

### Platform Connectivity & Harvest
- [ ] Automated verification script successfully connects to SnappMarket, Digikala Jet, and Okala live endpoints, returning real product items and active flash deals for given coordinates.
- [ ] No dummy JSON databases or mock fallbacks in the live adapter code.
- [ ] Session tokens and cookies are securely persisted in `.sessions/` and reused across application restarts.

### Normalization & SKU Mapping
- [ ] Correctly parses Persian grocery inputs with Persian/Arabic digits, brands, and quantities.
- [ ] High-confidence fuzzy/attribute matching prevents size or variant confusion (e.g. 1L vs 200ml milk).

### Optimization & Trap Audit
- [ ] Mathematically finds the global minimum cost across single-store and multi-store configurations including shipping tiers.
- [ ] Accurately flags marketing "traps" where flash-deal savings are swallowed by remaining basket item markups or shipping fees.

### Execution & UI
- [ ] Streamlit interface runs smoothly with live connection status, real-time search progress, interactive audit tables, and responsive layout.
- [ ] Cart dispatcher populates remote carts on target stores and yields working checkout links.
