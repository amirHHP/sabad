"""
Sabad (سبد) - Production-Grade Cross-Store Grocery Optimizer & Cart Dispatcher.
Interactive Streamlit Application with Persian RTL layout and Live Network Execution.
Redesigned with Digikala Jet (دیجی‌کالا جت) visual aesthetics and beginner-friendly shopping UX.
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
import sabad.ui_assets as ui_assets_module

for _mod in (config, persian_digits_module, gemini_parser_module, parser_module, matcher_module, normalizer_pkg, ui_assets_module):
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
from sabad.models.optimization import OptimizationResult, StoreOrder, FlashDealOpportunity
from sabad.optimizer.deal_advisor import FlashDealAdvisor
from sabad.optimizer.single_store import calculate_delivery_fee
from sabad.harvester import CatalogHarvester
from sabad.optimizer.milp_solver import MILPBasketOptimizer
from sabad.dispatcher.dispatcher import CartDispatcher
from sabad.ui_assets import (
    POPULAR_SHELF_ITEMS,
    resolve_product_image_and_fallback,
    render_jet_product_card_html,
    render_selected_cart_card_html,
    render_flash_deal_opportunity_card_html,
    CURATED_FLASH_DEALS_BY_STORE,
    get_default_flash_deals,
    STORE_METADATA,
)


# -------------------------------------------------------------
# Streamlit Page Configuration
# -------------------------------------------------------------
st.set_page_config(
    page_title="سبد | سوپرمارکت آنلاین فوری و بهینه‌ساز قیمت‌ها",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# Persian RTL Styling & Digikala Jet Visual Aesthetics
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800;900&display=swap');
    
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

    /* Digikala Jet Top Header Bar */
    .jet-navbar {
        background: linear-gradient(135deg, #E6123D 0%, #D4002A 50%, #99001C 100%);
        color: #ffffff;
        border-radius: 18px;
        padding: 24px 28px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px rgba(230, 18, 61, 0.22);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
    }
    .jet-brand-badge {
        display: inline-block;
        background: rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.35);
        color: #ffffff;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .jet-navbar-title {
        font-size: 1.65rem;
        font-weight: 900;
        margin: 0 0 6px 0;
        color: #ffffff !important;
        letter-spacing: -0.5px;
    }
    .jet-navbar-sub {
        font-size: 0.95rem;
        color: rgba(255, 255, 255, 0.92);
        line-height: 1.6;
        margin: 0;
    }
    .jet-navbar-badges {
        display: flex;
        flex-direction: column;
        gap: 8px;
        align-items: flex-start;
    }
    .jet-navbar-chip {
        background: #ffffff;
        color: #E6123D;
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 700;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    /* Beginner Stepper Guide */
    .jet-stepper {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 14px;
        margin-bottom: 24px;
    }
    @media (max-width: 768px) {
        .jet-stepper {
            grid-template-columns: 1fr;
        }
    }
    .jet-step-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
        transition: all 0.2s ease-in-out;
    }
    .jet-step-card:hover {
        transform: translateY(-2px);
        border-color: #fca5a5;
        box-shadow: 0 6px 16px rgba(230, 18, 61, 0.08);
    }
    .jet-step-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
        font-size: 1rem;
        font-weight: 800;
        color: #1e293b;
    }
    .jet-step-num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        background: #fee2e2;
        color: #E6123D;
        font-weight: 900;
        border-radius: 50%;
        font-size: 0.85rem;
    }
    .jet-step-card p {
        font-size: 0.85rem;
        color: #64748b;
        margin: 0;
        line-height: 1.5;
    }

    /* Quick Shelf Items */
    .shelf-product-item {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 12px;
        text-align: center;
        margin-bottom: 8px;
        transition: all 0.2s;
    }
    .shelf-product-item:hover {
        border-color: #E6123D;
        box-shadow: 0 4px 12px rgba(230, 18, 61, 0.08);
    }
    .shelf-img-box {
        position: relative;
        width: 100%;
        height: 100px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f8fafc;
        border-radius: 10px;
        margin-bottom: 8px;
        padding: 6px;
        overflow: hidden;
    }
    .shelf-img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }
    .shelf-discount-tag {
        position: absolute;
        top: 6px;
        right: 6px;
        background: #E6123D;
        color: #ffffff;
        padding: 2px 6px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 800;
        direction: ltr;
    }
    .shelf-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #1e293b;
        height: 2.5em;
        line-height: 1.25;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 4px;
    }
    .shelf-price {
        font-size: 0.82rem;
        font-weight: 800;
        color: #0f172a;
    }

    /* Selected Cart Cards (Digikala Jet Cart Aisle) */
    .jet-cart-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
        gap: 14px;
        margin: 14px 0 20px 0;
    }
    .jet-cart-item-card {
        background: #ffffff;
        border: 1.5px solid #fee2e2;
        border-radius: 14px;
        padding: 12px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 2px 8px rgba(230, 18, 61, 0.05);
        transition: all 0.2s ease-in-out;
        position: relative;
    }
    .jet-cart-item-card:hover {
        border-color: #E6123D;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(230, 18, 61, 0.12);
    }
    .jet-cart-card-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .jet-cart-brand-tag {
        background: #f1f5f9;
        color: #475569;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 700;
    }
    .jet-cart-qty-tag {
        background: #fee2e2;
        color: #E6123D;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 800;
    }
    .jet-cart-img-box {
        width: 100%;
        height: 110px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f8fafc;
        border-radius: 10px;
        margin-bottom: 8px;
        padding: 6px;
        overflow: hidden;
    }
    .jet-cart-img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }
    .jet-cart-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #1e293b;
        height: 2.5em;
        line-height: 1.25;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 6px;
    }
    .jet-cart-subrow {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.72rem;
    }
    .jet-cart-vol-badge {
        background: #f8fafc;
        color: #64748b;
        padding: 1px 6px;
        border-radius: 4px;
        border: 1px solid #e2e8f0;
    }
    .jet-cart-ready-chip {
        color: #059669;
        font-weight: 700;
    }

    /* Product Grid & Jet Product Cards */
    .jet-product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
        gap: 16px;
        margin: 16px 0 24px 0;
    }
    .jet-product-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 14px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.04);
        transition: all 0.25s ease-in-out;
        position: relative;
    }
    .jet-product-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.08);
        border-color: #cbd5e1;
    }
    .jet-card-header-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .jet-store-chip {
        padding: 3px 8px;
        border-radius: 8px;
        font-size: 0.72rem;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .jet-card-discount-badge {
        background-color: #E6123D;
        color: #ffffff;
        padding: 2px 7px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 800;
        direction: ltr;
    }
    .jet-card-img-container {
        width: 100%;
        height: 140px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f8fafc;
        border-radius: 12px;
        margin-bottom: 10px;
        overflow: hidden;
        padding: 8px;
    }
    .jet-card-img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }
    .jet-card-content {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .jet-card-req-title {
        font-size: 0.72rem;
        color: #94a3b8;
        margin-bottom: 2px;
    }
    .jet-card-product-title {
        font-size: 0.92rem;
        font-weight: 700;
        color: #1e293b;
        line-height: 1.35;
        height: 2.7em;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 8px;
    }
    .jet-card-meta-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .jet-card-stock-in {
        font-size: 0.72rem;
        color: #059669;
        font-weight: 700;
    }
    .jet-card-stock-out {
        font-size: 0.72rem;
        color: #dc2626;
        font-weight: 700;
    }
    .jet-card-qty-badge {
        background: #f1f5f9;
        color: #334155;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 800;
    }
    .jet-card-price-container {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 8px;
        border-top: 1px dashed #e2e8f0;
        padding-top: 8px;
    }
    .jet-card-price-primary {
        color: #0f172a;
        font-weight: 800;
        font-size: 1.05rem;
    }
    .jet-price-digits {
        font-weight: 900;
    }
    .jet-currency-unit {
        font-size: 0.75rem;
        font-weight: normal;
        color: #64748b;
        margin-right: 4px;
    }
    .jet-card-old-price {
        font-size: 0.8rem;
        color: #94a3b8;
        text-decoration: line-through;
    }
    .jet-card-footer-summary {
        background: #f8fafc;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 0.78rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .jet-card-line-total {
        color: #334155;
    }
    .jet-card-saving-pill {
        color: #059669;
        font-weight: 800;
        font-size: 0.75rem;
    }

    /* Golden Checkout Summary Card */
    .jet-checkout-summary-card {
        background: linear-gradient(135deg, #ffffff 0%, #fff7ed 100%);
        border: 2px solid #fdba74;
        border-radius: 18px;
        padding: 20px 24px;
        margin: 20px 0;
        box-shadow: 0 8px 25px rgba(249, 115, 22, 0.08);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
    }
    .jet-summary-col {
        text-align: right;
    }
    .jet-summary-label {
        font-size: 0.85rem;
        color: #64748b;
        margin-bottom: 4px;
    }
    .jet-summary-val-highlight {
        font-size: 1.45rem;
        font-weight: 900;
        color: #E6123D;
    }
    .jet-summary-val-saving {
        font-size: 1.15rem;
        font-weight: 800;
        color: #059669;
    }
    .jet-summary-val-fee {
        font-size: 1.15rem;
        font-weight: 800;
        color: #334155;
    }
    .jet-summary-val-badge {
        font-size: 1.15rem;
        font-weight: 800;
        color: #2563EB;
    }

    /* Standard Badges & Cards (Retained for Test Anchors) */
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

is_otp_active = any(st.session_state.get(f"otp_sent_{k}") for k in ["snapp_market", "digikala_jet", "okala", "tapsi_market"])
with st.sidebar.expander("🔑 ورود به حساب فروشگاه‌ها (OTP)", expanded=is_otp_active):
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
            st.session_state[f"otp_sent_{sel_platform}"] = False
            st.rerun()
    else:
        phone_val = st.text_input(
            "شماره موبایل (۰۹XXXXXXXXX):",
            placeholder="0912...",
            key=f"phone_input_{sel_platform}"
        )
        if st.button("📩 ارسال کد تایید پیامکی", key=f"send_otp_btn_{sel_platform}"):
            if len(phone_val.strip()) >= 10:
                with st.spinner("در حال ارسال پیامک..."):
                    send_res = asyncio.run(sel_adapter.send_otp(phone_val))
                if send_res.get("success"):
                    st.session_state[f"otp_sent_{sel_platform}"] = True
                    st.session_state[f"saved_phone_{sel_platform}"] = phone_val.strip()
                    if "challenge_token" in send_res:
                        st.session_state[f"challenge_{sel_platform}"] = send_res["challenge_token"]
                    st.success(send_res.get("message", "کد تأیید ارسال شد."))
                    st.rerun()
                else:
                    st.error(send_res.get("message", "خطا در ارسال کد."))
            else:
                st.warning("لطفاً شماره موبایل معتبر وارد کنید.")

        if st.session_state.get(f"otp_sent_{sel_platform}"):
            st.markdown("---")
            target_phone = st.session_state.get(f"saved_phone_{sel_platform}") or phone_val
            st.caption(f"کد ارسال‌شده به {target_phone} را وارد کنید:")

            with st.form(key=f"verify_otp_form_{sel_platform}"):
                otp_val = st.text_input(
                    "کد پیامک‌شده را وارد کنید:",
                    max_chars=6,
                    key=f"otp_input_{sel_platform}"
                )
                submit_otp = st.form_submit_button("✅ تأیید و ذخیره نشست", type="primary")

            if submit_otp:
                clean_otp = otp_val.strip()
                if len(clean_otp) >= 4:
                    with st.spinner("در حال تأیید کد و دریافت توکن..."):
                        ch_token = st.session_state.get(f"challenge_{sel_platform}")
                        verify_res = asyncio.run(sel_adapter.verify_otp(target_phone, clean_otp, ch_token))
                    if verify_res.get("success"):
                        st.session_state[f"otp_sent_{sel_platform}"] = False
                        st.success("✅ ورود با موفقیت انجام شد و نشست ذخیره گردید!")
                        st.rerun()
                    else:
                        st.error(verify_res.get("message", "کد تأیید نامعتبر یا منقضی شده است. لطفاً مجدداً کد ارسال کنید."))
                else:
                    st.warning("کد تأیید باید حداقل ۴ رقم باشد.")

            if st.button("🔄 تغییر شماره / ارسال مجدد", key=f"reset_otp_btn_{sel_platform}"):
                st.session_state[f"otp_sent_{sel_platform}"] = False
                st.rerun()

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
# Main Application Header (Digikala Jet Visual Style)
# -------------------------------------------------------------
st.markdown(f"""
<div class="jet-navbar">
  <div>
    <div class="jet-brand-badge">🚀 دیجی‌کالا جت × سبد</div>
    <h1 class="jet-navbar-title">سوپرمارکت آنلاین فوری با تضمین کمترین قیمت</h1>
    <p class="jet-navbar-sub">
      استعلام لحظه‌ای و مقایسه هوشمند قیمت اقلام بین <b>دیجی‌کالا جت</b>، <b>اسنپ‌مارکت</b>، <b>افق کوروش (اکالا)</b> و <b>تپسی مارکت</b>
    </p>
  </div>
  <div class="jet-navbar-badges">
    <div class="jet-navbar-chip">⚡ تحویل فوری ۳۰ تا ۴۵ دقیقه</div>
    <div class="jet-navbar-chip">📍 تحویل به: {loc_choice}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# 3-Step Beginner Visual Onboarding Stepper
st.markdown("""
<div class="jet-stepper">
  <div class="jet-step-card">
    <div class="jet-step-header">
      <span class="jet-step-num">۱</span>
      <span>انتخاب ساده اقلام</span>
    </div>
    <p>کالاهای دلخواهت رو از قفسه سریع کلیک کن یا به زبان عامیانه بنویس (مثلاً: دو تا شیر، یه پنیر، مایع پریل).</p>
  </div>
  <div class="jet-step-card">
    <div class="jet-step-header">
      <span class="jet-step-num">۲</span>
      <span>استعلام خودکار قیمت‌ها</span>
    </div>
    <p>ما قیمت، موجودی انبار و تخفیف‌ها رو همزمان از دیجی‌کالا جت، اسنپ‌مارکت و اکالا دریافت و مقایسه می‌کنیم.</p>
  </div>
  <div class="jet-step-card">
    <div class="jet-step-header">
      <span class="jet-step-num">۳</span>
      <span>سبد برنده و تحویل فوری</span>
    </div>
    <p>ارزان‌ترین سبد با تصاویر واقعی کالاها نمایش داده می‌شه و تله‌های تخفیف کاذب حذف می‌شن.</p>
  </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# Section 1: Persian Natural Language Basket Input & Visual Shelf
# -------------------------------------------------------------
st.subheader("📝 متن سبد خرید شما به زبان فارسی")

sample_baskets = {
    "سبد روزمره": "دو تا شیر پرچرب کاله یک لیتری، یه پنیر ویلی ۳۵۰ گرمی، یه مایع ظرفشویی پریل ۴ لیتری",
    "سبد صبحانه": "یه بسته تخم مرغ، دو تا شیر کم چرب روزانه ۱ لیتری، یه کره ۱۰۰ گرمی",
    "سبد شوینده و بهداشتی": "یه مایع ظرفشویی پریل، یه مایع دستشویی اکتیو، یه دستمال توالت پاپیا",
}

selected_sample = st.pills("نمونه‌های آماده:", list(sample_baskets.keys()))
default_text = sample_baskets.get(selected_sample, "دو تا شیر پرچرب کاله یک لیتری، یه پنیر ویلی ۳۵۰ گرمی، یه مایع ظرفشویی پریل ۴ لیتری")

# Shelf of Popular Essentials for Novice Shoppers (1-Click Add)
with st.expander("🛍️ قفسه کالاهای پرمصرف سوپرمارکتی (افزودن سریع به سبد با تصاویر)", expanded=True):
    st.caption("روی هر کالا کلیک کنید تا با تصویر به سبد شما اضافه شود:")
    
    shelf_categories = ["همه اقلام", "لبنیات و صبحانه", "خواربار و پخت‌وپز", "شوینده و بهداشتی", "نوشیدنی و تنقلات"]
    selected_shelf_cat = st.pills("دسته‌بندی سوپرمارکت جت:", shelf_categories, default="همه اقلام")

    if selected_shelf_cat and selected_shelf_cat != "همه اقلام":
        filtered_shelf_items = [it for it in POPULAR_SHELF_ITEMS if it.get("category") == selected_shelf_cat]
    else:
        filtered_shelf_items = POPULAR_SHELF_ITEMS

    shelf_cols = st.columns(4)
    for idx, s_item in enumerate(filtered_shelf_items):
        with shelf_cols[idx % 4]:
            img_src, fallback_uri = resolve_product_image_and_fallback(s_item["title"], s_item.get("image_url"))
            st.markdown(f"""
            <div class="shelf-product-item">
              <div class="shelf-img-box">
                <img src="{img_src}" alt="{s_item['title']}" class="shelf-img" loading="lazy" onerror="this.onerror=null; this.src='{fallback_uri}';" />
                <span class="shelf-discount-tag">%{s_item['discount_percent']}</span>
              </div>
              <div class="shelf-title">{s_item['title']}</div>
              <div class="shelf-price">{s_item['price_approx']:,} تومان</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"➕ افزودن {s_item['brand']}", key=f"shelf_add_{s_item['id']}"):
                cur_text = st.session_state.get("user_basket_text", "").strip()
                if not cur_text:
                    new_text = s_item['raw_text']
                else:
                    new_text = f"{cur_text}، {s_item['raw_text']}"
                st.session_state["user_basket_text"] = new_text
                st.rerun()

# Shelf of Daily High-Discount Flash Deals (40% - 70% Discounts)
with st.expander("⚡ حراج‌های شگفت‌انگیز روزانه فروشگاه‌ها (۴۰٪ تا ۷۰٪ تخفیف)", expanded=False):
    st.caption("پیشنهادهای شگفت‌انگیز روزانه فروشگاه‌ها با بالاترین تخفیف (مشابه دیجی‌کالا جت و اسنپ‌مارکت) - روی هر کالا کلیک کنید تا به سبد شما اضافه شود:")
    all_flash = get_default_flash_deals()
    flash_cols = st.columns(4)
    deal_counter = 0
    for plat_name, items in all_flash.items():
        for d_item in items[:2]:
            with flash_cols[deal_counter % 4]:
                img_src, fallback_uri = resolve_product_image_and_fallback(d_item.title, d_item.image_url)
                st.markdown(f"""
                <div class="shelf-product-item" style="border: 2px solid #fecaca; background: #fff5f5;">
                  <div class="shelf-img-box">
                    <img src="{img_src}" alt="{d_item.title}" class="shelf-img" loading="lazy" onerror="this.onerror=null; this.src='{fallback_uri}';" />
                    <span class="shelf-discount-tag" style="background:#dc2626;">%{d_item.discount_percent:.0f}</span>
                  </div>
                  <div class="shelf-title" style="font-weight:700;">{d_item.title}</div>
                  <div class="shelf-price" style="color:#dc2626;">{d_item.discount_price:,.0f} تومان <span style="text-decoration:line-through; color:#94a3b8; font-size:0.75rem;">{d_item.base_price:,.0f}</span></div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"➕ افزودن ({d_item.discount_percent:.0f}٪)", key=f"shelf_flash_add_{d_item.product_id}"):
                    cur_text = st.session_state.get("user_basket_text", default_text).strip()
                    if not cur_text:
                        new_text = f"یک {d_item.title}"
                    else:
                        new_text = f"{cur_text}، یک {d_item.title}"
                    st.session_state["user_basket_text"] = new_text
                    st.rerun()
                deal_counter += 1

# Sync user basket text with selected sample if sample changed or state uninitialized
if "user_basket_text" not in st.session_state:
    st.session_state["user_basket_text"] = default_text

    st.session_state["_last_selected_sample"] = selected_sample
elif selected_sample != st.session_state.get("_last_selected_sample"):
    st.session_state["_last_selected_sample"] = selected_sample
    if selected_sample:
        st.session_state["user_basket_text"] = sample_baskets.get(selected_sample, default_text)

user_input = st.text_area(
    "اقلام مورد نظرتان را به صورت طبیعی بنویسید (با ویرگول یا «و» جدا کنید):",
    value=st.session_state.get("user_basket_text", default_text),
    height=85
)
st.session_state["user_basket_text"] = user_input

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
        f'<span class="badge-ok" style="font-size:0.75rem;">✨ تحلیل هوشمند با {GEMINI_MODEL}</span>'
        if used_gemini
        else '<span style="font-size:0.75rem; color:#64748b;">(موتور هوشمند محلی)</span>'
    )

    # Visual Selected Basket Showcase with Real Product Images & Remove Buttons
    st.markdown(f"#### 🛍️ ویترین تصویری کالاهای انتخابی شما در سبد خرید ({len(parsed_basket.items)} قلم کالا) {engine_badge}", unsafe_allow_html=True)
    st.caption("تصاویر واقعی، برند و تعداد اقلام انتخاب‌شده شما در سبد سوپرمارکتی دیجی‌کالا جت:")

    cart_cols = st.columns(min(len(parsed_basket.items), 4))
    for i, item in enumerate(parsed_basket.items):
        with cart_cols[i % len(cart_cols)]:
            vol_spec = f"{item.volume_weight:g} {item.unit}" if item.volume_weight and item.unit else (item.unit or "")
            card_html = render_selected_cart_card_html(
                title=item.display_title,
                brand=item.brand,
                quantity=item.quantity,
                volume_spec=vol_spec,
            )
            st.markdown(card_html, unsafe_allow_html=True)
            if st.button(f"🗑️ حذف {item.name}", key=f"del_cart_item_{i}"):
                remaining_phrases = [
                    (it.raw_text.strip() if it.raw_text and it.raw_text.strip() else it.display_title)
                    for idx, it in enumerate(parsed_basket.items)
                    if idx != i
                ]
                st.session_state["user_basket_text"] = "، ".join(remaining_phrases)
                st.rerun()

    c_act1, c_act2 = st.columns([1, 4])
    with c_act1:
        if st.button("🗑️ خالی کردن کل سبد", key="clear_all_basket_btn"):
            st.session_state["user_basket_text"] = ""
            st.rerun()

    st.markdown(f"**اقلام تفکیک‌شده و ویژگی‌های استخراج‌شده:**", unsafe_allow_html=True)
    cols = st.columns(min(len(parsed_basket.items), 4))
    for i, item in enumerate(parsed_basket.items):
        with cols[i % len(cols)]:
            st.info(f"📌 **{item.display_title}**\n\n• نام: {item.name}\n• برند: {item.brand or 'هر برندی'}")
else:
    st.info("🛒 سبد خرید شما در حال حاضر خالی است. از قفسه کالاهای پرمصرف بالا کالاها را با یک کلیک اضافه کنید یا در کادر متنی بنویسید.")


# -------------------------------------------------------------
# Section 2: Live Execution Pipeline
# -------------------------------------------------------------
if st.button("🚀 استعلام زنده و حل سبد بهینه", type="primary"):
    if not parsed_basket.items:
        st.warning("لطفاً حداقل یک قلم کالا در سبد بنویسید.")
        st.stop()

    with st.status("🔍 در حال استعلام زنده قیمت‌ها و موجودی شعب سوپرمارکت...", expanded=True) as status:
        harvester = CatalogHarvester()
        adapters = harvester.adapters

        st.write("📡 استعلام همزمان شعب و کاتالوگ اقلام از دیجی‌کالا جت، اسنپ‌مارکت و افق کوروش...")
        store_infos, catalog_matches = asyncio.run(
            harvester.harvest_catalog_matches(parsed_basket.items, lat, lng)
        )

        st.write("⚡ رصد حراج‌های شگفت‌انگیز روزانه (۴۰٪ تا ۷۰٪ تخفیف)...")
        try:
            flash_deals = asyncio.run(harvester.harvest_flash_deals(lat, lng))
        except Exception:
            flash_deals = {}
        st.session_state["flash_deals_by_store"] = flash_deals

        # Step 3: Optimization
        st.write("🧮 حل مدل برنامه‌ریزی خطی عدد صحیح (MILP) و آدیت تله‌های شگفت‌انگیز...")
        optimizer = MILPBasketOptimizer(split_penalty_tomans=split_penalty)
        opt_result = optimizer.optimize(
            basket_items=parsed_basket.items,
            catalog_matches=catalog_matches,
            store_infos=store_infos,
            allow_multi_store=allow_split,
            flash_deals_by_store=flash_deals,
        )


        status.update(label="✅ استعلام و بهینه‌سازی سبد خرید با موفقیت انجام شد!", state="complete", expanded=False)

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

    # Digikala Jet Inspired Golden Summary Card for Beginner Shoppers
    delivery_fee_label = (
        "رایگان (۰ تومان)"
        if opt_result.total_delivery_fees == 0
        else f"{opt_result.total_delivery_fees:,.0f} تومان"
    )
    st.markdown(f"""
    <div class="jet-checkout-summary-card">
      <div class="jet-summary-col">
        <div class="jet-summary-label">مبلغ کل سبد بهینه (پرداختی)</div>
        <div class="jet-summary-val-highlight">{opt_result.grand_total_cost:,.0f} تومان</div>
      </div>
      <div class="jet-summary-col">
        <div class="jet-summary-label">مجموع تخفیف‌های شما</div>
        <div class="jet-summary-val-saving">🎉 {opt_result.total_discounts_saved:,.0f} تومان</div>
      </div>
      <div class="jet-summary-col">
        <div class="jet-summary-label">هزینه کل ارسال</div>
        <div class="jet-summary-val-fee">🚚 {delivery_fee_label}</div>
      </div>
      <div class="jet-summary-col">
        <div class="jet-summary-label">سود بهینه‌سازی سبد</div>
        <div class="jet-summary-val-badge">⚡ {opt_result.net_savings_versus_worst:,.0f} تومان سود</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Metrics summary cards (Required for test assertions)
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
    # Store Comparison Table (Must be at.dataframe[0] for tests)
    # -------------------------------------------------------------
    st.markdown("---")
    st.subheader("🏪 مقایسه خرید تک‌فروشگاهی در برابر سبد هوشمند")

    comparison_data = []
    for s_name, order in opt_result.single_store_orders.items():
        adapter = adapters.get(s_name) if adapters else None
        title = adapter.platform_title_fa if adapter else s_name
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
    # Flash Deal Opportunities Advisor (40% - 70% Amazing Deals)
    # -------------------------------------------------------------
    deal_opps = getattr(opt_result, "deal_opportunities", [])
    if deal_opps:
        st.markdown("---")
        st.subheader("⚡ فرصت‌های طلایی تخفیف‌های شگفت‌انگیز (۴۰٪ تا ۷۰٪ تخفیف)")
        st.markdown(
            "فروشگاه‌ها روزانه تخفیف‌های شگفت‌انگیز فوق‌العاده‌ای (۴۰٪ تا ۷۰٪) ارائه می‌دهند. "
            "سیستم هوشمند سبد با تحلیل سبد خرید فعلی و وضعیت فروشگاه‌ها، بهترین فرصت‌های سودآور زیر را برای شما شناسایی کرده است:"
        )

        same_store_opps = [o for o in deal_opps if o.opportunity_type == "same_store_addon"]
        switch_opps = [o for o in deal_opps if o.opportunity_type == "store_switch_deal"]

        if same_store_opps:
            st.markdown("##### 🎁 پیشنهادهای شگفت‌انگیز از همین فروشگاه (بدون هزینه ارسال اضافه):")
            st.caption("این کالاها از همین فروشگاه منتخب شما تخفیف بسیار بالایی دارند و می‌توانید با قیمت بسیار پایین آن‌ها را به سبد خود بیفزایید:")
            for s_idx, op in enumerate(same_store_opps):
                benefit_text = (
                    f"تحویل با همین سفارش بدون هزینه ارسال مازاد | سود تخفیف کالا: {op.deal_nominal_saving:,.0f} تومان | "
                    f"مبلغ کل جدید سبد: {op.projected_basket_cost:,.0f} تومان"
                )
                card_html = render_flash_deal_opportunity_card_html(
                    title=op.deal_item.title,
                    platform=op.target_store,
                    base_price=op.deal_base_price,
                    discount_price=op.deal_discount_price,
                    discount_percent=op.deal_discount_percent,
                    opportunity_type=op.opportunity_type,
                    benefit_highlight=benefit_text,
                    image_url=op.deal_item.image_url,
                    store_title_override=op.target_store_title,
                )
                st.markdown(card_html, unsafe_allow_html=True)

                col_btn, _ = st.columns([2, 3])
                with col_btn:
                    if st.button(f"➕ افزودن به سبد خرید ({op.deal_discount_price:,.0f} تومان)", key=f"btn_addon_opp_{s_idx}_{op.deal_item.product_id}"):
                        cur_text = st.session_state.get("user_basket_text", "").strip()
                        new_text = f"{cur_text}، یک {op.deal_item.title}" if cur_text else f"یک {op.deal_item.title}"
                        st.session_state["user_basket_text"] = new_text

                        updated_opt, updated_basket, updated_cat = FlashDealAdvisor.apply_opportunity(
                            opt_result=opt_result,
                            opportunity=op,
                            store_infos=store_infos,
                            basket_items=basket_items,
                            catalog_matches=catalog_matches,
                        )
                        st.session_state["opt_result"] = updated_opt
                        st.session_state["basket_items"] = updated_basket
                        st.session_state["catalog_matches"] = updated_cat

                        st.success(f"«{op.deal_item.title}» با تخفیف {op.deal_discount_percent:.0f}٪ به سبد اضافه شد!")
                        st.rerun()

        if switch_opps:
            st.markdown("##### 🔄 فرصت‌های طلایی تغییر فروشگاه (سودآوری بسیار بالاتر سبد):")
            st.caption("اگر فروشگاه خود را عوض کنید و این کالای تخفیف‌دار را هم اضافه کنید، جمع سبد شما بسیار سودآورتر و ارزان‌تر خواهد شد:")
            for sw_idx, op in enumerate(switch_opps):
                if op.is_cheaper_total:
                    benefit_text = (
                        f"🔥 شگفت‌انگیز: حتی با اضافه کردن این کالا، مبلغ کل سبد در {op.target_store_title} "
                        f"ارزان‌تر از خرید فعلی تمام می‌شود! (سود کل: {op.projected_basket_savings:,.0f} تومان)"
                    )
                else:
                    benefit_text = (
                        f"سود کل تخفیف‌ها به {op.projected_basket_savings:,.0f} تومان می‌رسد "
                        f"({op.net_profit_increase:,.0f} تومان سود خالص بیشتر نسبت به حالت قبل)"
                    )

                card_html = render_flash_deal_opportunity_card_html(
                    title=op.deal_item.title,
                    platform=op.target_store,
                    base_price=op.deal_base_price,
                    discount_price=op.deal_discount_price,
                    discount_percent=op.deal_discount_percent,
                    opportunity_type=op.opportunity_type,
                    benefit_highlight=benefit_text,
                    image_url=op.deal_item.image_url,
                    store_title_override=op.target_store_title,
                )
                st.markdown(card_html, unsafe_allow_html=True)

                col_btn, _ = st.columns([2, 3])
                with col_btn:
                    if st.button(f"🔄 انتقال سبد به {op.target_store_title} و افزودن کالا", key=f"btn_switch_opp_{sw_idx}_{op.deal_item.product_id}"):
                        cur_text = st.session_state.get("user_basket_text", "").strip()
                        new_text = f"{cur_text}، یک {op.deal_item.title}" if cur_text else f"یک {op.deal_item.title}"
                        st.session_state["user_basket_text"] = new_text

                        updated_opt, updated_basket, updated_cat = FlashDealAdvisor.apply_opportunity(
                            opt_result=opt_result,
                            opportunity=op,
                            store_infos=store_infos,
                            basket_items=basket_items,
                            catalog_matches=catalog_matches,
                        )
                        st.session_state["opt_result"] = updated_opt
                        st.session_state["basket_items"] = updated_basket
                        st.session_state["catalog_matches"] = updated_cat

                        st.success(f"فروشگاه به {op.target_store_title} تغییر کرد و «{op.deal_item.title}» اضافه شد!")
                        st.rerun()

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
        s_info = store_infos.get(platform) if store_infos else None
        single_order = opt_result.single_store_orders.get(platform) if opt_result and opt_result.single_store_orders else None
        adapter = adapters.get(platform) if adapters else None
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

        # 2. Visual Catalog Cards with Real Product Images
        store_cards_html = []
        for item in basket_items:
            match = None
            if catalog_matches and item.raw_text in catalog_matches:
                match = catalog_matches[item.raw_text].get(platform)
            elif catalog_matches and getattr(item, "name", None) in catalog_matches:
                match = catalog_matches[item.name].get(platform)

            if match:
                card_html = render_jet_product_card_html(
                    product_title=match.title,
                    requested_title=item.display_title,
                    platform=platform,
                    price=match.discount_price,
                    base_price=match.base_price,
                    quantity=item.quantity,
                    image_url=match.image_url,
                    is_in_stock=match.is_in_stock,
                    discount_percent=match.discount_percent,
                    store_title_override=platform_title,
                )
                store_cards_html.append(card_html)

        if store_cards_html:
            with st.expander(f"🖼️ ویترین تصویری کالاهای منطبق در {platform_title}", expanded=True):
                st.markdown(f'<div class="jet-product-grid">{"".join(store_cards_html)}</div>', unsafe_allow_html=True)

        # 3. Itemized audit table
        audit_rows = []
        missing_items = []

        for item in basket_items:
            match = None
            if catalog_matches and item.raw_text in catalog_matches:
                match = catalog_matches[item.raw_text].get(platform)
            elif catalog_matches and getattr(item, "name", None) in catalog_matches:
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

        # 4. Missing / Discrepant items container
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

        # 5. Delivery tier calculation expander
        with st.expander("🚚 روند محاسبه هزینه ارسال و حداقل سفارش (Delivery Tiers & MOV)", expanded=False):
            subtotal = single_order.items_subtotal if single_order else sum(
                (m.discount_price * it.quantity)
                for it in basket_items
                if (m := (catalog_matches.get(it.raw_text, {}).get(platform) if catalog_matches else None) or (catalog_matches.get(it.name, {}).get(platform) if catalog_matches else None)) and m.is_in_stock
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

        # -------------------------------------------------------------
        # Visual Product Cards Gallery (Digikala Jet Aesthetics)
        # -------------------------------------------------------------
        st.markdown("##### 🛍️ ویترین تصویری کالاهای برگزیده سبد بهینه (مشابه دیجی‌کالا جت):")
        st.caption("تصاویر واقعی، قیمت تخفیف‌دار و فروشگاه برگزیده هر قلم از سفارش شما:")

        visual_cards_html = []
        if basket_items and opt_result and opt_result.optimal_orders:
            for item in basket_items:
                found_asgn = None
                winning_platform = None
                winning_store_title = None
                for order in opt_result.optimal_orders:
                    cand = None
                    if catalog_matches:
                        cand = catalog_matches.get(item.raw_text, {}).get(order.platform) or catalog_matches.get(item.name, {}).get(order.platform)
                    if order.items:
                        for asgn in order.items:
                            if cand and asgn.item.product_id == cand.product_id:
                                found_asgn = asgn
                                winning_platform = order.platform
                                adapter = adapters.get(order.platform) if adapters else None
                                winning_store_title = adapter.platform_title_fa if adapter else order.platform
                                break
                    if found_asgn:
                        break

                if found_asgn and winning_store_title:
                    card_html = render_jet_product_card_html(
                        product_title=found_asgn.item.title,
                        requested_title=item.display_title,
                        platform=winning_platform or "digikala_jet",
                        price=found_asgn.item.discount_price,
                        base_price=found_asgn.item.base_price,
                        quantity=found_asgn.quantity,
                        image_url=found_asgn.item.image_url,
                        is_in_stock=found_asgn.item.is_in_stock,
                        discount_percent=found_asgn.item.discount_percent,
                        store_title_override=winning_store_title,
                    )
                    visual_cards_html.append(card_html)

        if not basket_items and opt_result and opt_result.optimal_orders:
            for order in opt_result.optimal_orders:
                adapter = adapters.get(order.platform) if adapters else None
                store_title = adapter.platform_title_fa if adapter else order.platform
                if order.items:
                    for asgn in order.items:
                        card_html = render_jet_product_card_html(
                            product_title=asgn.item.title,
                            requested_title=asgn.item.title,
                            platform=order.platform,
                            price=asgn.item.discount_price,
                            base_price=asgn.item.base_price,
                            quantity=asgn.quantity,
                            image_url=asgn.item.image_url,
                            is_in_stock=asgn.item.is_in_stock,
                            discount_percent=asgn.item.discount_percent,
                            store_title_override=store_title,
                        )
                        visual_cards_html.append(card_html)

        if visual_cards_html:
            grid_container_html = f'<div class="jet-product-grid">{"".join(visual_cards_html)}</div>'
            st.markdown(grid_container_html, unsafe_allow_html=True)
        else:
            st.info("اقلامی برای نمایش تصویری در سبد برگزیده ثبت نشده است.")

        st.markdown("##### 📋 جدول اقلام برگزیده در سبد نهایی:")
        optimal_table_rows = []

        if opt_result and opt_result.optimal_orders:
            for item in basket_items:
                found_asgn = None
                winning_store_title = None
                for order in opt_result.optimal_orders:
                    cand = None
                    if catalog_matches:
                        cand = catalog_matches.get(item.raw_text, {}).get(order.platform) or catalog_matches.get(item.name, {}).get(order.platform)
                    if order.items:
                        for asgn in order.items:
                            if cand and asgn.item.product_id == cand.product_id:
                                found_asgn = asgn
                                adapter = adapters.get(order.platform) if adapters else None
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
        elif basket_items:
            for item in basket_items:
                optimal_table_rows.append({
                    "قلم درخواستی": item.display_title,
                    "فروشگاه برنده": "❌ عدم تامین",
                    "کالای برگزیده (SKU)": "❌ هیچ فروشگاهی این کالا را تامین نکرد",
                    "قیمت واحد (تومان)": "-",
                    "تعداد": item.quantity,
                    "مجموع ردیف (تومان)": "-",
                    "سود تخفیف (تومان)": "-",
                })

        if not basket_items and opt_result and opt_result.optimal_orders:
            for order in opt_result.optimal_orders:
                adapter = adapters.get(order.platform) if adapters else None
                store_title = adapter.platform_title_fa if adapter else order.platform
                if order.items:
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
        if opt_result and opt_result.optimal_orders:
            cols = st.columns(max(1, len(opt_result.optimal_orders)))
            for idx, order in enumerate(opt_result.optimal_orders):
                with cols[idx]:
                    with st.container(border=True):
                        adapter = adapters.get(order.platform) if adapters else None
                        p_name = adapter.platform_title_fa if adapter else order.platform
                        item_count = len(order.items) if order.items else 0
                        st.markdown(f"#### {p_name}")
                        st.markdown(f"• **تعداد اقلام:** {item_count} قلم")
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
