"""
Sabad (سبد) - Production-Grade Cross-Store Grocery Optimizer & Cart Dispatcher.
Interactive Streamlit Application with Persian RTL layout and Live Network Execution.
"""

import asyncio
import streamlit as st
from sabad.config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
from sabad.adapters.session_manager import SessionManager
from sabad.normalizer.parser import parse_grocery_input
from sabad.normalizer.matcher import match_sku
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

with st.sidebar.expander("🔑 ورود به حساب فروشگاه‌ها (OTP)", expanded=False):
    store_map = {
        "اسنپ‌مارکت": ("snapp_market", SnappMarketAdapter()),
        "دیجی‌کالا جت": ("digikala_jet", DigikalaJetAdapter()),
        "افق کوروش / اکالا": ("okala", OkalaAdapter()),
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

# Parse Persian text into structured items
parsed_basket = parse_grocery_input(user_input)

if parsed_basket.items:
    st.markdown("**اقلام تفکیک‌شده و ویژگی‌های استخراج‌شده:**")
    cols = st.columns(min(len(parsed_basket.items), 4))
    for i, item in enumerate(parsed_basket.items):
        with cols[i % len(cols)]:
            st.info(f"📌 **{item.display_title}**\n\n• نام: {item.name}\n• برند: {item.brand or 'هر برندی'}")


# -------------------------------------------------------------
# Section 2: Live Execution Pipeline
# -------------------------------------------------------------
if st.button("🚀 استعلام زنده و حل سبد بهینه", type="primary", use_container_width=True):
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

    # Store result in session state for dispatch
    st.session_state["opt_result"] = opt_result
    st.session_state["adapters"] = adapters


# -------------------------------------------------------------
# Section 3: Optimization Results & Comparison
# -------------------------------------------------------------
if "opt_result" in st.session_state:
    opt_result = st.session_state["opt_result"]
    adapters = st.session_state["adapters"]

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

    st.dataframe(comparison_data, use_container_width=True)

    # -------------------------------------------------------------
    # Section 4: Cart Population & Payment Handoff
    # -------------------------------------------------------------
    st.markdown("---")
    st.subheader("🛒 اجرای سفارش و شارژ مستقیم سبد خرید")

    st.write("با کلیک بر روی دکمه زیر، اقلام تعیین‌شده به طور خودکار به سبد حساب‌های کاربری شما در هر پلتفرم اضافه خواهند شد:")

    if st.button("🚀 افزودن مستقیم به سبد خرید و ایجاد لینک‌های پرداخت", type="primary", use_container_width=True):
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
