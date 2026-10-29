"""On-demand account, delivery, and shopping preferences."""

import asyncio

import streamlit as st

from sabad import config
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
from sabad.adapters.session_manager import SessionManager
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.tapsi_market import TapsiMarketAdapter


LOCATIONS = {
    "تهران - بلوار کشاورز / یوسف‌آباد": (35.715298, 51.404343),
    "تهران - سعادت‌آباد / شهرک غرب": (35.780833, 51.371389),
    "تهران - تجریش / شمیرانات": (35.804167, 51.428889),
    "تهران - تهرانپارس": (35.733333, 51.533333),
}

STORES = {
    "اسنپ‌مارکت": ("snapp_market", SnappMarketAdapter),
    "دیجی‌کالا جت": ("digikala_jet", DigikalaJetAdapter),
    "اکالا": ("okala", OkalaAdapter),
    "تپسی مارکت": ("tapsi_market", TapsiMarketAdapter),
}

RESULT_KEYS = (
    "opt_result", "catalog_matches", "store_infos", "basket_items",
    "adapters", "flash_deals_by_store", "search_evidence",
)


def invalidate_comparison():
    for key in RESULT_KEYS:
        st.session_state.pop(key, None)


def reset_location_context():
    """Invalidate prices and the branch-resolving adapter cache together."""
    invalidate_comparison()
    st.session_state.pop("catalog_harvester", None)


def initialize_preferences():
    st.session_state.setdefault("delivery_location", next(iter(LOCATIONS)))
    st.session_state.setdefault("allow_split", True)
    st.session_state.setdefault("split_penalty", config.DEFAULT_SPLIT_PENALTY_TOMANS)
    st.session_state.setdefault("use_ai", bool(config.GEMINI_API_KEY))
    st.session_state.setdefault("user_basket_text", "")
    st.session_state.setdefault("show_editor", False)
    st.session_state.setdefault("voice_generation", 0)


def render_settings(*, auth_enabled: bool, oidc_configured: bool):
    if auth_enabled:
        st.subheader("حساب سبد")
        if getattr(st.user, "is_logged_in", False):
            st.caption(getattr(st.user, "name", None) or getattr(st.user, "email", ""))
            if st.button("خروج از سبد", icon=":material/logout:"):
                st.logout()
        elif oidc_configured:
            if st.button("ورود به سبد", icon=":material/login:"):
                st.login()
        else:
            st.warning("ورود به حساب هنوز روی سرور تنظیم نشده است.")

    st.selectbox(
        "محدوده تحویل", list(LOCATIONS), key="delivery_location",
        persist_state="session", on_change=reset_location_context,
    )

    with st.expander("حساب فروشگاه‌ها", icon=":material/storefront:"):
        for label, (platform, _) in STORES.items():
            connected = SessionManager.is_authenticated(platform)
            st.caption(f"{label} · {'متصل' if connected else 'وارد نشده‌اید'}")

        selected = st.selectbox(
            "فروشگاه", list(STORES), key="login_store", persist_state="session",
        )
        platform, adapter_type = STORES[selected]
        adapter = adapter_type()
        if SessionManager.is_authenticated(platform):
            st.success(f"حساب فعال: {SessionManager.get_phone(platform) or selected}")
            if st.button("خروج از فروشگاه", key=f"logout_{platform}"):
                SessionManager.clear_session(platform)
                st.session_state[f"otp_sent_{platform}"] = False
                invalidate_comparison()
                st.rerun(scope="fragment")
        else:
            phone = st.text_input(
                "شماره موبایل", placeholder="۰۹۱۲…", key=f"phone_input_{platform}",
                persist_state="session",
            )
            if st.button("ارسال کد تأیید", key=f"send_otp_btn_{platform}"):
                if len(phone.strip()) < 10:
                    st.warning("شماره موبایل معتبر وارد کنید.")
                else:
                    with st.spinner("در حال ارسال کد…"):
                        response = asyncio.run(adapter.send_otp(phone))
                    if response.get("success"):
                        st.session_state[f"otp_sent_{platform}"] = True
                        st.session_state[f"saved_phone_{platform}"] = phone.strip()
                        st.session_state[f"challenge_{platform}"] = response.get("challenge_token")
                        st.success("کد تأیید ارسال شد.")
                    else:
                        st.error(response.get("message", "ارسال کد انجام نشد."))

            if st.session_state.get(f"otp_sent_{platform}"):
                with st.form(f"verify_otp_form_{platform}"):
                    code = st.text_input("کد تأیید", max_chars=6, key=f"otp_input_{platform}")
                    verify = st.form_submit_button("ورود به فروشگاه", type="primary")
                if verify:
                    if len(code.strip()) < 4:
                        st.warning("کد تأیید باید حداقل ۴ رقم باشد.")
                    else:
                        with st.spinner("در حال ورود…"):
                            response = asyncio.run(adapter.verify_otp(
                                st.session_state[f"saved_phone_{platform}"], code.strip(),
                                st.session_state.get(f"challenge_{platform}"),
                            ))
                        if response.get("success"):
                            st.session_state[f"otp_sent_{platform}"] = False
                            invalidate_comparison()
                            st.rerun(scope="fragment")
                        else:
                            st.error(response.get("message", "کد نامعتبر یا منقضی شده است."))
                if st.button("تغییر شماره / ارسال دوباره", key=f"reset_otp_btn_{platform}"):
                    st.session_state[f"otp_sent_{platform}"] = False
                    st.rerun(scope="fragment")

    with st.expander("ترجیحات خرید", icon=":material/tune:"):
        st.checkbox(
            "خرید از چند فروشگاه", key="allow_split", persist_state="session",
            on_change=invalidate_comparison,
        )
        st.slider(
            "حداقل صرفه‌جویی برای یک ارسال اضافه (تومان)", 0, 60000, step=5000,
            key="split_penalty", persist_state="session", on_change=invalidate_comparison,
        )
        st.checkbox(
            "درک هوشمند لیست خرید", key="use_ai", disabled=not bool(config.GEMINI_API_KEY),
            persist_state="session", on_change=invalidate_comparison,
        )
        if not config.GEMINI_API_KEY:
            st.caption("تبدیل صدا به متن هنوز روی سرور فعال نشده است.")

    with st.expander("نوشتن لیست به‌جای ضبط", icon=":material/keyboard:"):
        with st.form("manual_basket_form"):
            text = st.text_area("لیست خرید", value=st.session_state["user_basket_text"], height=110)
            if st.form_submit_button("ادامه با این لیست", type="primary"):
                st.session_state["user_basket_text"] = text
                st.session_state["basket_editor"] = text
                st.session_state["show_editor"] = True
                st.session_state["settings_open"] = False
                invalidate_comparison()
                st.rerun()

    if st.button("بستن تنظیمات", width="stretch"):
        st.session_state["settings_open"] = False
        st.rerun()
