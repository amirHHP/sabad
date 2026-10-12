"""
Sabad (سبد) - Production-Grade Cross-Store Grocery Optimizer & Cart Dispatcher.
Interactive Streamlit Application with Persian RTL layout and Live Network Execution.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
import os
import inspect
import importlib
import streamlit as st

import sabad.config as config
import sabad.normalizer.persian_digits as persian_digits_module
import sabad.normalizer.gemini_parser as gemini_parser_module
import sabad.normalizer.parser as parser_module
import sabad.normalizer.matcher as matcher_module
import sabad.normalizer as normalizer_pkg

for _mod in (config, persian_digits_module, gemini_parser_module, parser_module, matcher_module, normalizer_pkg):
    try:
        importlib.reload(_mod)
    except Exception:
        pass

DEFAULT_LATITUDE = getattr(config, "DEFAULT_LATITUDE", float(os.getenv("LATITUDE", "35.715298")))
DEFAULT_LONGITUDE = getattr(config, "DEFAULT_LONGITUDE", float(os.getenv("LONGITUDE", "51.404343")))
GEMINI_API_KEY = getattr(config, "GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "")).strip()
GEMINI_MODEL = getattr(config, "GEMINI_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")).strip()

from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
from sabad.adapters.tapsi_market import TapsiMarketAdapter
from sabad.adapters.session_manager import SessionManager
from sabad.normalizer.parser import parse_grocery_input
from sabad.normalizer.matcher import match_sku, extract_volume_from_title
from sabad.models.grocery import ParsedGroceryBasket, ParsedGroceryItem
from sabad.models.catalog import StoreItem, StoreInfo
from sabad.models.optimization import OptimizationResult, StoreOrder
from sabad.optimizer.single_store import calculate_delivery_fee
from sabad.harvester import CatalogHarvester
from sabad.optimizer.milp_solver import MILPBasketOptimizer
from sabad.dispatcher.dispatcher import CartDispatcher

# -------------------------------------------------------------
# Streamlit Page Configuration
# -------------------------------------------------------------
st.set_page_config(
    page_title="سبد | بهینه‌ساز هوشمند خریدهای سوپرمارکتی",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# Persian RTL Styling & Vazirmatn Typography
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;700;800;900&display=swap');
    
    html, body, [class*="css"], .stMarkdown, .stText, p, h1, h2, h3, h4, h5, h6, input, textarea, button, select {
        font-family: 'Vazirmatn', sans-serif !important;
        direction: rtl !important;
        text-align: right !important;
    }

    [data-testid="stIcon"], [data-testid="stExpanderToggleIcon"], .material-symbols-rounded, .material-icons {
        font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
        direction: ltr !important;
    }
    
    [data-testid="stSidebar"] {
        direction: rtl !important;
        text-align: right !important;
    }
    
    .badge-ok {
        background-color: #d1fae5;
        color: #065f46;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 700;
        display: inline-block;
    }
    
    .badge-err {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 700;
        display: inline-block;
    }
    
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        text-align: center !important;
    }
    
    .trap-banner {
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
        border: 1px solid #f87171;
        border-radius: 12px;
        padding: 18px;
        margin: 14px 0;
    }
    
    .deal-banner {
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
        border: 1px solid #4ade80;
        border-radius: 12px;
        padding: 18px;
        margin: 14px 0;
    }
</style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# Sidebar: Connection Status & Delivery Coordinates
# -------------------------------------------------------------
st.sidebar.title("⚙️ وضعیت پلتفرم‌ها و موقعیت")

# Delivery location presets in Tehran
locations = {
    "تهران - بلوار کشاورز / یوسف‌آباد": (35.715298, 51.404343),
    "تهران - سعادت‌آباد / شهرک غرب": (35.780833, 51.371389),
    "تهران - تجریش / شمیرانات": (35.804167, 51.428889),
    "تهران - تهرانپارس": (35.733333, 51.533333),
}

loc_choice = st.sidebar.selectbox("محدوده تحویل سفارش:", list(locations.keys()), index=0)
lat, lng = locations[loc_choice]

st.sidebar.markdown(f"**مختصات فعال:** `{lat:.4f}, {lng:.4f}`")

st.sidebar.markdown("---")
st.sidebar.subheader("🔌 وضعیت اتصال فروشگاه‌ها")

# Platform health and session indicators
col_s1, col_s2 = st.sidebar.columns([3, 2])
with col_s1:
    st.write("اسنپ‌مارکت:")
with col_s2:
    if SessionManager.is_authenticated("snapp_market"):
        st.markdown('<span class="badge-ok">🟢 متصل</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-err">🔴 بدون نشست</span>', unsafe_allow_html=True)

col_j1, col_j2 = st.sidebar.columns([3, 2])
with col_j1:
    st.write("دیجی‌کالا جت:")
with col_j2:
    if SessionManager.is_authenticated("digikala_jet"):
        st.markdown('<span class="badge-ok">🟢 متصل</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-err">🔴 بدون نشست</span>', unsafe_allow_html=True)

col_o1, col_o2 = st.sidebar.columns([3, 2])
with col_o1:
    st.write("افق کوروش / اکالا:")
with col_o2:
    if SessionManager.is_authenticated("okala"):
        st.markdown('<span class="badge-ok">🟢 متصل</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-err">🔴 بدون نشست</span>', unsafe_allow_html=True)

col_t1, col_t2 = st.sidebar.columns([3, 2])
with col_t1:
    st.write("تپسی مارکت:")
with col_t2:
    if SessionManager.is_authenticated("tapsi_market"):
        st.markdown('<span class="badge-ok">🟢 متصل</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-err">🔴 بدون نشست</span>', unsafe_allow_html=True)

with st.sidebar.expander("🔑 ورود به حساب فروشگاه‌ها (OTP)", expanded=False):
    store_map = {
        "اسنپ‌مارکت": ("snapp_market", SnappMarketAdapter()),
        "دیجی‌کالا جت": ("digikala_jet", DigikalaJetAdapter()),
        "افق کوروش / اکالا": ("okala", OkalaAdapter()),
        "تپسی مارکت": ("tapsi_market", TapsiMarketAdapter()),
    }
    sel_store_label = st.selectbox("انتخاب فروشگاه:", list(store_map.keys()))
    sel_platform, sel_adapter = store_map[sel_store_label]

    is_logged_in = SessionManager.is_authenticated(sel_platform)
    if is_logged_in:
        user_phone = SessionManager.get_phone(sel_platform) or "احراز هویت شده"
        st.success(f"حساب فعال: {user_phone}")
        if st.button("خروج از حساب", key=f"logout_{sel_platform}"):
            SessionManager.clear_session(sel_platform)
            st.rerun()
    else:
        phone_val = st.text_input(
            "شماره موبایل (۰۹XXXXXXXXX):",
            placeholder="0912...",
            key=f"phone_input_{sel_platform}"
        )
        if st.button("📩 ارسال کد تایید پیامکی", key=f"send_otp_btn_{sel_platform}"):
            if len(phone_val) >= 10:
                with st.spinner("در حال ارسال پیامک..."):
                    send_res = asyncio.run(sel_adapter.send_otp(phone_val))
                if send_res.get("success"):
                    st.session_state[f"otp_sent_{sel_platform}"] = True
                    if "challenge_token" in send_res:
                        st.session_state[f"challenge_{sel_platform}"] = send_res["challenge_token"]
                    st.success(send_res.get("message", "کد تأیید ارسال شد."))
                else:
                    st.error(send_res.get("message", "خطا در ارسال کد."))
            else:
                st.warning("لطفاً شماره موبایل معتبر وارد کنید.")

        if st.session_state.get(f"otp_sent_{sel_platform}"):
            otp_val = st.text_input(
                "کد پیامک‌شده را وارد کنید:",
                max_chars=6,
                key=f"otp_input_{sel_platform}"
            )
            if st.button("✅ تأیید و ذخیره نشست", key=f"verify_otp_btn_{sel_platform}", type="primary"):
                if len(otp_val) >= 4:
                    with st.spinner("در حال تأیید کد و دریافت توکن..."):
                        ch_token = st.session_state.get(f"challenge_{sel_platform}")
                        verify_res = asyncio.run(sel_adapter.verify_otp(phone_val, otp_val, ch_token))
                    if verify_res.get("success"):
                        st.success("✅ ورود با موفقیت انجام شد و نشست ذخیره گردید!")
                        st.session_state[f"otp_sent_{sel_platform}"] = False
                        st.rerun()
                    else:
                        st.error(verify_res.get("message", "کد تأیید نامعتبر است."))
                else:
                    st.warning("کد تأیید باید حداقل ۴ رقم باشد.")

st.sidebar.markdown("---")
st.sidebar.subheader("✨ موتور هوش مصنوعی Gemini")
if GEMINI_API_KEY:
    st.sidebar.markdown(f'<span class="badge-ok">🟢 فعال: {GEMINI_MODEL}</span>', unsafe_allow_html=True)
    use_ai = st.sidebar.checkbox("استفاده از هوش مصنوعی برای درک متن", value=True)
else:
    st.sidebar.markdown('<span class="badge-err">🔴 غیرفعال (بدون کلید)</span>', unsafe_allow_html=True)
    use_ai = False

st.sidebar.markdown("---")
st.sidebar.subheader("🧠 تنظیمات بهینه‌ساز")
allow_split = st.sidebar.checkbox("امکان تقسیم سفارش بین چند فروشگاه (Multi-Store)", value=True)
split_penalty = st.sidebar.slider(
    "جریمه هماهنگی ارسال مضاعف (تومان):",
    min_value=0,
    max_value=60000,
    value=25000,
    step=5000,
    help="حداقل میزان سودی که برای توجیه دریافت دو پیک مجزا لازم است."
)

# -------------------------------------------------------------
# Main Application Header
# -------------------------------------------------------------
st.title("🛒 سبد | موتور هوشمند بهینه‌سازی و ثبت سبد خرید سوپرمارکتی")
st.markdown("""
سیستم زنده استعلام، مقایسه و بهینه‌سازی سبد کالا بین **اسنپ‌مارکت**، **دیجی‌کالا جت** و **افق کوروش (اکالا)**
همراه با **آدیتور تله‌های شگفت‌انگیز** و قابلیت انتقال و شارژ مستقیم سبد خرید.
""")

# -------------------------------------------------------------
# Section 1: Persian Natural Language Basket Input
# -------------------------------------------------------------
st.subheader("📝 متن سبد خرید شما به زبان فارسی")

sample_baskets = {
    "سبد روزمره": "دو تا شیر پرچرب کاله یک لیتری، یه پنیر ویلی ۳۵۰ گرمی، یه مایع ظرفشویی پریل ۴ لیتری",
    "سبد صبحانه": "یه بسته تخم مرغ، دو تا شیر کم چرب روزانه ۱ لیتری، یه کره ۱۰۰ گرمی",
    "سبد شوینده و بهداشتی": "یه مایع ظرفشویی پریل، یه مایع دستشویی اکتیو، یه دستمال توالت پاپیا",
}

selected_sample = st.pills("نمونه‌های آماده:", list(sample_baskets.keys()))
default_text = sample_baskets.get(selected_sample, "دو تا شیر پرچرب کاله یک لیتری، یه پنیر ویلی ۳۵۰ گرمی، یه مایع ظرفشویی پریل ۴ لیتری")

user_input = st.text_area(
    "اقلام مورد نظرتان را به صورت طبیعی بنویسید (با ویرگول یا «و» جدا کنید):",
    value=default_text,
    height=85
)

def safe_parse_grocery_input(raw_text: str, use_ai: bool = True) -> ParsedGroceryBasket:
    """
    Safely invokes parse_grocery_input handling potential stale in-memory cached versions
    retained by Streamlit's long-running server process across hot-reloads.
    """
    try:
        sig = inspect.signature(parse_grocery_input)
        params = sig.parameters
        if "use_llm" in params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return parse_grocery_input(raw_text, use_llm=use_ai)
        elif "use_ai" in params:
            return parse_grocery_input(raw_text, use_ai=use_ai)
    except Exception:
        pass

    try:
        return parse_grocery_input(raw_text, use_llm=use_ai)
    except TypeError as err:
        if "use_llm" in str(err) or "unexpected keyword" in str(err):
            return parse_grocery_input(raw_text)
        raise

parsed_basket = safe_parse_grocery_input(user_input, use_ai=use_ai)

if parsed_basket.items:
    used_gemini = getattr(parsed_basket, "engine", "") == "gemini" or (use_ai and bool(GEMINI_API_KEY))
    engine_badge = (
        f'<span class="badge-ok" style="font-size:0.75rem;">✨ تحلیل‌شده با {GEMINI_MODEL}</span>'
        if used_gemini
        else '<span style="font-size:0.75rem; color:#64748b;">(موتور قاعده‌محور محلی)</span>'
    )
    st.markdown(f"**اقلام تفکیک‌شده و ویژگی‌های استخراج‌شده:** {engine_badge}", unsafe_allow_html=True)
    cols = st.columns(min(len(parsed_basket.items), 4))
    for i, item in enumerate(parsed_basket.items):
        with cols[i % len(cols)]:
            st.info(f"📌 **{item.display_title}**\n\n• نام: {item.name}\n• برند: {item.brand or 'هر برندی'}")


# -------------------------------------------------------------
# Section 2: Live Execution Pipeline
# -------------------------------------------------------------
if st.button("🚀 استعلام زنده و حل سبد بهینه", type="primary"):
    if not parsed_basket.items:
        st.warning("لطفاً حداقل یک قلم کالا در سبد بنویسید.")
        st.stop()

    with st.status("🔍 در حال اجرای خط لوله استعلام زنده از شبکه‌های فروشگاهی...", expanded=True) as status:
        harvester = CatalogHarvester()
        adapters = harvester.adapters

        st.write("📡 استعلام همزمان شعب و کاتالوگ اقلام از اسنپ‌مارکت، دیجی‌کالا جت و افق کوروش...")
        store_infos, catalog_matches = asyncio.run(
            harvester.harvest_catalog_matches(parsed_basket.items, lat, lng)
        )

        # Step 3: Optimization
        st.write("🧮 حل مدل برنامه‌ریزی خطی عدد صحیح (MILP) و آدیت تله‌های شگفت‌انگیز...")
        optimizer = MILPBasketOptimizer(split_penalty_tomans=split_penalty)
        opt_result = optimizer.optimize(
            basket_items=parsed_basket.items,
            catalog_matches=catalog_matches,
            store_infos=store_infos,
            allow_multi_store=allow_split
        )

        status.update(label="✅ استعلام و بهینه‌سازی با موفقیت انجام شد!", state="complete", expanded=False)

    # Store result in session state for dispatch and itemized audit
    st.session_state["catalog_matches"] = catalog_matches
    st.session_state["store_infos"] = store_infos
    st.session_state["basket_items"] = parsed_basket.items
    st.session_state["opt_result"] = opt_result
    st.session_state["adapters"] = adapters


# -------------------------------------------------------------
# Section 3: Optimization Results & Comparison
# -------------------------------------------------------------
if "opt_result" in st.session_state:
    opt_result = st.session_state["opt_result"]
    adapters = st.session_state.get("adapters")
    if not adapters:
        adapters = CatalogHarvester().adapters
        st.session_state["adapters"] = adapters
    catalog_matches = st.session_state.get("catalog_matches", {})
    store_infos = st.session_state.get("store_infos", {})
    basket_items = st.session_state.get("basket_items", [])
    if not basket_items and "parsed_basket" in locals() and getattr(parsed_basket, "items", None):
        basket_items = parsed_basket.items

    st.markdown("---")
    st.subheader("📊 نتایج بهینه‌سازی و مقایسه جامع فروشگاه‌ها")

    # Metrics summary cards
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("هزینه کل سبد بهینه", f"{opt_result.grand_total_cost:,.0f} تومان")
        st.markdown('</div>', unsafe_allow_html=True)
    with m_col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("تخفیف‌های ذخیره‌شده", f"{opt_result.total_discounts_saved:,.0f} تومان")
        st.markdown('</div>', unsafe_allow_html=True)
    with m_col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("هزینه کل ارسال", f"{opt_result.total_delivery_fees:,.0f} تومان")
        st.markdown('</div>', unsafe_allow_html=True)
    with m_col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("سود حاصل از بهینه‌سازی", f"{opt_result.net_savings_versus_worst:,.0f} تومان")
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------
    # Flash Deal Trap Auditor Card
    # -------------------------------------------------------------
    st.markdown("---")
    st.subheader("🕵️ گزارش آدیتور تله‌های شگفت‌انگیز (Marketing Trap Auditor)")
    
    if opt_result.trap_audit.has_traps:
        st.markdown(f"""
        <div class="trap-banner">
            <h4 style="color:#991b1b; margin-top:0;">🚨 هشدار تله‌ی تخفیف شناسایی شد!</h4>
            <p>{opt_result.trap_audit.summary_fa}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="deal-banner">
            <h4 style="color:#166534; margin-top:0;">✅ تخفیف‌های سبد اقتصادی و واقعی هستند</h4>
            <p>{opt_result.trap_audit.summary_fa}</p>
        </div>
        """, unsafe_allow_html=True)

    for audit in opt_result.trap_audit.audited_deals:
        with st.expander(f"بررسی کالای تخفیف‌دار: {audit.product_title}"):
            st.write(audit.explanation_fa)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("تخفیف ظاهری کالا (+)", f"{audit.apparent_deal_saving:,.0f} ت")
            c2.metric("گرانی سایر اقلام سبد (-)", f"{audit.collateral_item_markup:,.0f} ت")
            c3.metric("هزینه ارسال اضافه (-)", f"{audit.extra_shipping_fee:,.0f} ت")
            c4.metric("سود یا زیان خالص (=)", f"{audit.net_advantage:,.0f} ت")

    # -------------------------------------------------------------
    # Store Comparison Table
    # -------------------------------------------------------------
    st.markdown("---")
    st.subheader("🏪 مقایسه خرید تک‌فروشگاهی در برابر سبد هوشمند")

    comparison_data = []
    for s_name, order in opt_result.single_store_orders.items():
        title = adapters[s_name].platform_title_fa
        if order:
            status_txt = "✅ کامل" if order.missing_items_count == 0 else f"⚠️ ناقص ({order.missing_items_count} قلم کسری)"
            mov_txt = "بله" if order.meets_mov else f"خیر (حداقل {order.minimum_order_value:,.0f} ت)"
            comparison_data.append({
                "فروشگاه": title,
                "وضعیت اقلام": status_txt,
                "مبلغ اقلام (تومان)": f"{order.items_subtotal:,.0f}",
                "هزینه ارسال (تومان)": f"{order.delivery_fee:,.0f}",
                "مجموع پرداختی (تومان)": f"{order.total_cost:,.0f}",
                "تخفیف اعمال‌شده": f"{order.total_savings:,.0f}",
                "رسیدن به حداقل سفارش": mov_txt,
            })
        else:
            comparison_data.append({
                "فروشگاه": title,
                "وضعیت اقلام": "❌ عدم امکان تامین",
                "مبلغ اقلام (تومان)": "-",
                "هزینه ارسال (تومان)": "-",
                "مجموع پرداختی (تومان)": "-",
                "تخفیف اعمال‌شده": "-",
                "رسیدن به حداقل سفارش": "-",
            })

    if opt_result.is_multi_store:
        comparison_data.append({
            "فروشگاه": "🏆 سبد ترکیبی بهینه (Multi-Store)",
            "وضعیت اقلام": "✅ ۱۰۰٪ تامین",
            "مبلغ اقلام (تومان)": f"{opt_result.total_items_cost:,.0f}",
            "هزینه ارسال (تومان)": f"{opt_result.total_delivery_fees:,.0f}",
            "مجموع پرداختی (تومان)": f"{opt_result.grand_total_cost:,.0f}",
            "تخفیف اعمال‌شده": f"{opt_result.total_discounts_saved:,.0f}",
            "رسیدن به حداقل سفارش": "بله",
        })

    st.dataframe(comparison_data, width="stretch")

    # -------------------------------------------------------------
    # Section 4: Itemized Audit & Calculation Breakdown
    # -------------------------------------------------------------
    st.markdown("---")
    st.subheader("🔍 روند محاسبات و جزئیات اقلام (Itemized Audit & Calculation Breakdown)")

    def render_store_audit_tab(
        platform: str,
        basket_items: list,
        catalog_matches: dict,
        store_infos: dict,
        opt_result: OptimizationResult,
        adapters: dict,
    ) -> None:
        s_info = store_infos.get(platform)
        single_order = opt_result.single_store_orders.get(platform) if opt_result else None
        adapter = adapters.get(platform)
        platform_title = adapter.platform_title_fa if adapter else platform

        branch_title = s_info.title if s_info else platform_title
        is_open = s_info.is_open if s_info else True
        mov_value = s_info.minimum_order_value if s_info else (single_order.minimum_order_value if single_order else 0.0)

        # 1. Header: Store branch title, status, minimum order value (MOV) in Tomans
        h_col1, h_col2, h_col3 = st.columns([2, 1, 1])
        with h_col1:
            st.markdown(f"#### 🏪 شعبه: **{branch_title}**")
        with h_col2:
            status_badge = "🟢 شعبه باز و فعال" if is_open else "🔴 شعبه غیرفعال"
            st.markdown(f"**وضعیت:** {status_badge}")
        with h_col3:
            st.markdown(f"**حداقل سفارش (MOV):** `{mov_value:,.0f} تومان`")

        # 2. Itemized audit table
        audit_rows = []
        missing_items = []

        for item in basket_items:
            match = None
            if item.raw_text in catalog_matches:
                match = catalog_matches[item.raw_text].get(platform)
            elif getattr(item, "name", None) in catalog_matches:
                match = catalog_matches[item.name].get(platform)

            if match and match.is_in_stock:
                vol, unit = extract_volume_from_title(match.title)
                if vol is not None and unit:
                    vol_spec = f"{vol:g} {unit}"
                elif vol is not None:
                    vol_spec = f"{vol:g}"
                elif unit:
                    vol_spec = unit
                else:
                    vol_spec = "-"

                line_tot = match.discount_price * item.quantity
                line_sav = match.saving_amount * item.quantity

                audit_rows.append({
                    "قلم درخواستی": item.display_title,
                    "کالای متناظر در فروشگاه": match.title,
                    "حجم/مشخصات انطباق‌یافته": vol_spec,
                    "قیمت پایه واحد (تومان)": f"{match.base_price:,.0f}",
                    "قیمت فروش واحد (تومان)": f"{match.discount_price:,.0f}",
                    "تعداد": item.quantity,
                    "مجموع ردیف (تومان)": f"{line_tot:,.0f}",
                    "سود تخفیف (تومان)": f"{line_sav:,.0f}",
                    "وضعیت": "✅ موجود و متناظر",
                })
            elif match and not match.is_in_stock:
                vol, unit = extract_volume_from_title(match.title)
                vol_spec = f"{vol:g} {unit}" if (vol is not None and unit) else (f"{vol:g}" if vol is not None else (unit or "-"))
                audit_rows.append({
                    "قلم درخواستی": item.display_title,
                    "کالای متناظر در فروشگاه": match.title,
                    "حجم/مشخصات انطباق‌یافته": vol_spec,
                    "قیمت پایه واحد (تومان)": f"{match.base_price:,.0f}",
                    "قیمت فروش واحد (تومان)": f"{match.discount_price:,.0f}",
                    "تعداد": item.quantity,
                    "مجموع ردیف (تومان)": "-",
                    "سود تخفیف (تومان)": "-",
                    "وضعیت": "⚠️ ناموجود در انبار",
                })
                missing_items.append((item, match))
            else:
                audit_rows.append({
                    "قلم درخواستی": item.display_title,
                    "کالای متناظر در فروشگاه": "❌ ناموجود / عدم تطابق",
                    "حجم/مشخصات انطباق‌یافته": "-",
                    "قیمت پایه واحد (تومان)": "-",
                    "قیمت فروش واحد (تومان)": "-",
                    "تعداد": item.quantity,
                    "مجموع ردیف (تومان)": "-",
                    "سود تخفیف (تومان)": "-",
                    "وضعیت": "❌ کسری / عدم تطابق",
                })
                missing_items.append((item, None))

        st.markdown("##### 📋 جدول تفکیک اقلام و قیمت‌ها:")
        if audit_rows:
            st.dataframe(audit_rows, width="stretch")
        else:
            st.info("هیچ قلم کالایی در این فروشگاه ثبت نشده است.")

        # 3. Missing / Discrepant items container
        missing_count = len(missing_items)
        if single_order and single_order.missing_items_count > missing_count:
            missing_count = single_order.missing_items_count

        if missing_count > 0:
            with st.container(border=True):
                st.markdown(f"#### ⚠️ اقلام کسری و موارد عدم انطباق ({missing_count} قلم)")
                st.markdown("اقلام زیر در این فروشگاه به سبد نهایی اضافه نشدند:")
                for m_item, m_match in missing_items:
                    st.markdown(f"- **{m_item.display_title}**:")
                    if m_match is None:
                        st.markdown(
                            "  - عدم موجودی یا عدم یافتن کالا در شعبه فعال این فروشگاه.\n"
                            "  - رد شدن به دلیل عدم انطباق با حجم درخواستی (مثلاً ۱ کیلوگرم به جای ۴ لیتر) یا عدم انطباق درصد چربی و طعم."
                        )
                    else:
                        st.markdown(
                            f"  - عدم موجودی یا عدم یافتن کالا در شعبه فعال این فروشگاه.\n"
                            f"  - موجودی کالای «{m_match.title}» در انبار شعبه به پایان رسیده است."
                        )

        # 4. Delivery tier calculation expander
        with st.expander("🚚 روند محاسبه هزینه ارسال و حداقل سفارش (Delivery Tiers & MOV)", expanded=False):
            subtotal = single_order.items_subtotal if single_order else sum(
                (m.discount_price * it.quantity)
                for it in basket_items
                if (m := (catalog_matches.get(it.raw_text, {}).get(platform) or catalog_matches.get(it.name, {}).get(platform))) and m.is_in_stock
            )
            mov_threshold = s_info.minimum_order_value if s_info else (single_order.minimum_order_value if single_order else 0.0)
            meets_mov = (subtotal >= mov_threshold) if mov_threshold > 0 else True

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("مجموع ارزش اقلام سبد", f"{subtotal:,.0f} تومان")
            with c2:
                st.metric("حداقل سفارش (MOV)", f"{mov_threshold:,.0f} تومان")
            with c3:
                mov_status_str = "✅ رعایت شده" if meets_mov else "⚠️ کمتر از حداقل مجاز"
                st.metric("وضعیت حداقل سفارش", mov_status_str)

            st.markdown("##### جدول سطوح هزینه ارسال:")
            tiers = s_info.delivery_tiers if (s_info and s_info.delivery_tiers) else []
            if tiers:
                tiers_data = []
                for tier in tiers:
                    if tier.max_subtotal is None:
                        range_str = f"از {tier.min_subtotal:,.0f} تومان به بالا"
                        is_applied = (subtotal >= tier.min_subtotal)
                    else:
                        range_str = f"از {tier.min_subtotal:,.0f} تا {tier.max_subtotal:,.0f} تومان"
                        is_applied = (tier.min_subtotal <= subtotal < tier.max_subtotal)

                    fee_str = "رایگان (۰ تومان)" if tier.fee == 0 else f"{tier.fee:,.0f} تومان"
                    applied_str = "👈 سطح اعمال‌شده (فعال)" if is_applied else "-"
                    tiers_data.append({
                        "محدوده مبلغ سبد (تومان)": range_str,
                        "هزینه ارسال": fee_str,
                        "وضعیت اعمال": applied_str
                    })
                st.dataframe(tiers_data, width="stretch")
            else:
                st.info("سطوح پلکانی برای این فروشگاه ثبت نشده است.")

            delivery_fee = single_order.delivery_fee if single_order else (
                calculate_delivery_fee(subtotal, s_info) if s_info else 0.0
            )
            st.markdown(f"**هزینه نهایی ارسال این فروشگاه:** `{delivery_fee:,.0f} تومان`")

    def render_optimal_basket_tab(
        opt_result: OptimizationResult,
        basket_items: list,
        catalog_matches: dict,
        adapters: dict,
    ) -> None:
        st.markdown("#### 🏆 سبد بهینه نهایی (تخصیص هوشمند)")
        st.markdown("مدل برنامه‌ریزی خطی عدد صحیح (MILP) هزینه خرید، ارسال و جریمه تفکیک را بهینه کرده است:")
        st.latex(r"\min \left[ \sum_{s \in S} \left( \sum_{i \in I_s} \text{Price}(i, s) \times q_i + \text{DeliveryFee}_s(\text{Subtotal}_s) \right) + \text{SplitPenalty} \times \mathbb{I}_{|S| > 1} \right]")

        st.markdown("##### 📋 جدول اقلام برگزیده در سبد نهایی:")
        optimal_table_rows = []

        for item in basket_items:
            found_asgn = None
            winning_store_title = None
            for order in opt_result.optimal_orders:
                cand = catalog_matches.get(item.raw_text, {}).get(order.platform) or catalog_matches.get(item.name, {}).get(order.platform)
                for asgn in order.items:
                    if cand and asgn.item.product_id == cand.product_id:
                        found_asgn = asgn
                        adapter = adapters.get(order.platform)
                        winning_store_title = adapter.platform_title_fa if adapter else order.platform
                        break
                if found_asgn:
                    break

            if found_asgn and winning_store_title:
                optimal_table_rows.append({
                    "قلم درخواستی": item.display_title,
                    "فروشگاه برنده": winning_store_title,
                    "کالای برگزیده (SKU)": found_asgn.item.title,
                    "قیمت واحد (تومان)": f"{found_asgn.item.discount_price:,.0f}",
                    "تعداد": found_asgn.quantity,
                    "مجموع ردیف (تومان)": f"{found_asgn.line_total:,.0f}",
                    "سود تخفیف (تومان)": f"{found_asgn.nominal_saving:,.0f}",
                })
            else:
                optimal_table_rows.append({
                    "قلم درخواستی": item.display_title,
                    "فروشگاه برنده": "❌ عدم تامین",
                    "کالای برگزیده (SKU)": "❌ هیچ فروشگاهی این کالا را تامین نکرد",
                    "قیمت واحد (تومان)": "-",
                    "تعداد": item.quantity,
                    "مجموع ردیف (تومان)": "-",
                    "سود تخفیف (تومان)": "-",
                })

        if not basket_items and opt_result.optimal_orders:
            for order in opt_result.optimal_orders:
                adapter = adapters.get(order.platform)
                store_title = adapter.platform_title_fa if adapter else order.platform
                for asgn in order.items:
                    optimal_table_rows.append({
                        "قلم درخواستی": asgn.item.title,
                        "فروشگاه برنده": store_title,
                        "کالای برگزیده (SKU)": asgn.item.title,
                        "قیمت واحد (تومان)": f"{asgn.item.discount_price:,.0f}",
                        "تعداد": asgn.quantity,
                        "مجموع ردیف (تومان)": f"{asgn.line_total:,.0f}",
                        "سود تخفیف (تومان)": f"{asgn.nominal_saving:,.0f}",
                    })

        if optimal_table_rows:
            st.dataframe(optimal_table_rows, width="stretch")
        else:
            st.warning("هیچ قلم کالایی در سبد بهینه ثبت نشده است.")

        st.markdown("##### 📦 کارت‌های تفکیک سفارش (Multi-Store Split Cards):")
        if opt_result.optimal_orders:
            cols = st.columns(max(1, len(opt_result.optimal_orders)))
            for idx, order in enumerate(opt_result.optimal_orders):
                with cols[idx]:
                    with st.container(border=True):
                        adapter = adapters.get(order.platform)
                        p_name = adapter.platform_title_fa if adapter else order.platform
                        st.markdown(f"#### {p_name}")
                        st.markdown(f"• **تعداد اقلام:** {len(order.items)} قلم")
                        st.markdown(f"• **مبلغ اقلام:** {order.items_subtotal:,.0f} تومان")
                        st.markdown(f"• **هزینه ارسال:** {order.delivery_fee:,.0f} تومان")
                        st.markdown(f"• **مجموع پرداختی:** **{order.total_cost:,.0f} تومان**")
                        st.markdown(f"• **سود تخفیف‌ها:** {order.total_savings:,.0f} تومان")
                        if order.meets_mov:
                            st.markdown('<span class="badge-ok">✅ حداقل سفارش رعایت شده</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<span class="badge-err">⚠️ کمتر از حداقل سفارش ({order.minimum_order_value:,.0f} ت)</span>', unsafe_allow_html=True)
        else:
            st.info("سفارشی در سبد بهینه ثبت نشده است.")

    tab_opt, tab_snapp, tab_jet, tab_okala, tab_tapsi = st.tabs([
        "🏆 سبد بهینه نهایی (تخصیص هوشمند)",
        "🟡 اسنپ‌مارکت (SnappMarket)",
        "🔴 دیجی‌کالا جت (Digikala Jet)",
        "🟢 افق کوروش / اکالا (Okala)",
        "🟠 تپسی مارکت (Tapsi Market)",
    ])

    with tab_opt:
        render_optimal_basket_tab(opt_result, basket_items, catalog_matches, adapters)

    with tab_snapp:
        render_store_audit_tab("snapp_market", basket_items, catalog_matches, store_infos, opt_result, adapters)

    with tab_jet:
        render_store_audit_tab("digikala_jet", basket_items, catalog_matches, store_infos, opt_result, adapters)

    with tab_okala:
        render_store_audit_tab("okala", basket_items, catalog_matches, store_infos, opt_result, adapters)

    with tab_tapsi:
        render_store_audit_tab("tapsi_market", basket_items, catalog_matches, store_infos, opt_result, adapters)

    # -------------------------------------------------------------
    # Section 5: Cart Population & Payment Handoff
    # -------------------------------------------------------------
    st.markdown("---")
    st.subheader("🛒 اجرای سفارش و شارژ مستقیم سبد خرید")

    st.write("با کلیک بر روی دکمه زیر، اقلام تعیین‌شده به طور خودکار به سبد حساب‌های کاربری شما در هر پلتفرم اضافه خواهند شد:")

    if st.button("🚀 افزودن مستقیم به سبد خرید و ایجاد لینک‌های پرداخت", type="primary"):
        dispatcher = CartDispatcher(adapters=adapters)
        with st.spinner("در حال اجرای تراکنش‌های شبکه و ارسال اقلام به سبدها..."):
            handoffs = asyncio.run(dispatcher.dispatch_orders(opt_result.optimal_orders))

        st.success("✅ سبدها با موفقیت تکمیل شدند!")
        
        for h in handoffs:
            with st.container(border=True):
                st.markdown(f"### 🛍️ فروشگاه: {h.platform_fa}")
                st.write(h.summary_fa)
                
                if h.mutation_result:
                    if h.mutation_result.success:
                        st.markdown(f'<span class="badge-ok">✅ {h.mutation_result.items_added} قلم کالا با موفقیت اضافه شد</span>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<span class="badge-err">⚠️ {h.mutation_result.error_message}</span>', unsafe_allow_html=True)

                col_btn1, col_btn2 = st.columns([1, 4])
                with col_btn1:
                    st.link_button(f"💳 رفتن به پرداخت در {h.platform_fa}", h.web_checkout_url, type="primary")
