# Spec 06: UI Architecture & Calculation Transparency

> **Status**: Approved & Verified  
> **Source Files**: `app.py`, `streamlit_app.py`  
> **Framework**: Streamlit v1.35+ (Persian RTL)

---

## 1. UI Hierarchy & Structure

The Streamlit interface follows a structured 5-section layout:
1. **Sidebar**: Store health badges (🟢/🔴), Geolocation selector (Tehran zones), OTP authentication modals, and MILP coordination sliders.
2. **Section 1: Natural Language Input**: Persian text area with sample presets (*سبد روزمره*, *سبد صبحانه*, *سبد شوینده*) and chip previews of extracted attributes.
3. **Section 2: Execution Status Pipeline**: Real-time spinner tracking concurrent harvesting, matching, and optimization.
4. **Section 3: Macro Comparison Matrix**: High-level KPIs (Total Optimal Cost, Delivery Fees, Net Savings) and store comparison table.
5. **Section 4: Itemized Audit & Calculation Breakdown ("روند محاسبات و جزئیات اقلام")**: Detailed 4-tab auditing interface for end-user verification.
6. **Section 5: Direct Cart Dispatch**: Automated remote cart population and payment gateway handoff links.

---

## 2. 4-Tab Itemized Audit Breakdown ("روند محاسبات")

The calculation breakdown is rendered within `render_store_audit_tab()` and organized into 4 interactive tabs:
- **Tab 1: 🏆 سبد ترکیبی بهینه (Multi-Store)**: Displays the winning SKU allocation across stores and shows split friction calculations.
- **Tab 2: 🟡 اسنپ‌مارکت (SnappMarket)**: Full item-by-item breakdown for SnappMarket.
- **Tab 3: 🟣 دیجی‌کالا جت (Digikala Jet)**: Full item-by-item breakdown for Digikala Jet.
- **Tab 4: 🔴 افق کوروش / اکالا (Okala)**: Full item-by-item breakdown for Okala.

### 9-Column Itemized Audit Table
Every store tab displays a dataframe with 9 exact audit columns:

| Column Header | Description | Example |
|:---|:---|:---|
| **قلم درخواستی** | User's parsed item title with quantity | `2 عدد شیر کاله 1 لیتر 3٪ چربی` |
| **کالای متناظر در فروشگاه** | Exact product title from store catalog | `شیر پرچرب مدت دار کاله 1 لیتری` |
| **حجم/مشخصات انطباق‌یافته** | Normalized size extracted from matched SKU | `1 لیتر` |
| **قیمت پایه واحد (تومان)** | Store base catalog unit price | `169,000` |
| **قیمت فروش واحد (تومان)** | Store selling unit price after discount | `169,000` |
| **تعداد** | Requested quantity multiplier | `2` |
| **مجموع ردیف (تومان)** | `قیمت فروش واحد * تعداد` | `338,000` |
| **سود تخفیف (تومان)** | `(قیمت پایه - قیمت فروش) * تعداد` | `0` |
| **وضعیت** | Stock and compatibility state | `✅ موجود و متناظر` / `❌ کسری / عدم تطابق` |

### Diagnostic Callout Containers
If an item is missing or out of stock in a given store:
- An expandable alert box (`st.error` / `st.warning`) details:
  - Exact missing requested item.
  - Reason for rejection (out-of-stock, attribute mismatch, or no candidates found).
  - Impact on the single-store fulfillment feasibility.

### Delivery Tier Breakdown View
An expandable container (`st.expander("🚚 جزئیات محاسبه کرایه حمل و حداقل سفارش (MOV)")`) detailing:
- Items subtotal in Tomans.
- MOV threshold and compliance status (`بله / خیر`).
- Active delivery tier rule and applied shipping fee.

---

## 3. Session Isolation & Multi-Tenancy

To support public deployment on Streamlit Community Cloud without cross-user session leakage:
- User credentials and tokens are stored inside `st.session_state` with unique per-browser session keys.
- Fallback persistent storage in `.sessions/` is scoped to isolated device UDIDs.
- Configuration variables in `sabad/config.py` resolve gracefully from `st.secrets` first, falling back to `os.environ`.
