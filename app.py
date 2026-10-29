"""
Sabad (سبد) - Production-Grade Cross-Store Grocery Optimizer & Cart Dispatcher.
Interactive Streamlit Application with Persian RTL layout and Live Network Execution.
Voice-first shopping with on-demand settings and basket comparison.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
import os
import inspect
import hashlib
from dataclasses import asdict
import streamlit as st

import sabad.config as config
GEMINI_API_KEY = getattr(config, "GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "")).strip()
GEMINI_MODEL = getattr(config, "GEMINI_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")).strip()

from sabad.normalizer.parser import parse_grocery_input
from sabad.normalizer.gemini_parser import transcribe_audio_gemini
from sabad.normalizer.matcher import extract_volume_from_title
from sabad.models.grocery import ParsedGroceryBasket
from sabad.models.catalog import StoreItem
from sabad.models.optimization import OptimizationResult
from sabad.optimizer.deal_advisor import FlashDealAdvisor
from sabad.optimizer.single_store import calculate_delivery_fee
from sabad.harvester import CatalogHarvester
from sabad.app_services import compare_and_optimize_basket
from sabad.dispatcher.dispatcher import CartDispatcher
from sabad.product_links import build_product_link
from sabad.ui_assets import (
    resolve_product_image_and_fallback,
)
from sabad.pricing import comparable_price_text
from sabad.price_history import PriceHistoryStore
from sabad.feedback import FEEDBACK_REASONS, FeedbackStore
from sabad.search_explanations import explain_missing_item
from sabad.security import MAX_BASKET_ITEMS, SlidingWindowLimiter, log_store_failure, validate_audio_size, validate_basket_text


def _uses_serverless_voice_recorder() -> bool:
    """Vercel Functions cannot reliably serve Streamlit's multipart upload route."""
    return bool(
        os.getenv("VERCEL")
        or os.getenv("VERCEL_ENV")
        or os.getenv("AWS_LAMBDA_FUNCTION_VERSION")
    )


# -------------------------------------------------------------
# Streamlit Page Configuration
# -------------------------------------------------------------
st.set_page_config(
    page_title="سبد | سوپرمارکت آنلاین فوری و بهینه‌ساز قیمت‌ها",
    page_icon=":material/shopping_basket:",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Keep the landing page focused on the native, accessible audio recorder.
from sabad.ui_settings import (
    LOCATIONS, initialize_preferences, invalidate_comparison, render_settings,
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap');
:root { --ink:#102a43; --muted:#627d98; --line:#e5e9ed; --brand:#0b8f78; --brand-dark:#06705f; }
html, body, input, textarea, button, select, .stMarkdown, .stText, p, h1, h2, h3, h4 { font-family:'Vazirmatn',sans-serif; }
[data-testid="stAppViewContainer"] { background:#fff; direction:rtl; }
[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], #MainMenu, footer { display:none; }
[data-testid="stMainBlockContainer"] { max-width:1120px; padding:24px 28px 60px; }
[data-testid="stDialog"] { direction:rtl; }
input, textarea, .stMarkdown, .stText, label { direction:rtl; text-align:right; }
button:focus-visible { outline:3px solid #72cbb8; outline-offset:5px; }
.st-key-app_toolbar button { color:#697782; background:transparent; border:1px solid #e9edef; border-radius:50px; padding:8px 16px; }
.st-key-voice_landing { margin-top:clamp(110px,24vh,260px); margin-bottom:36px; }
.st-key-voice_review { margin:38px 0 28px; }
.st-key-voice_landing [data-testid="stMarkdownContainer"] p,
.st-key-voice_review [data-testid="stMarkdownContainer"] p { text-align:center; color:#6b747b; font-size:16px; line-height:1.9; }
.st-key-voice_landing [data-testid="stAudioInput"],
.st-key-voice_review [data-testid="stAudioInput"] { max-width:340px; margin:auto; }
.st-key-voice_landing [data-testid="stAudioInput"] > div:last-child,
.st-key-voice_review [data-testid="stAudioInput"] > div:last-child {
  background:transparent; border:0; overflow:visible; height:auto; min-height:142px;
  display:flex; flex-direction:column; padding:12px; gap:12px;
}
[data-testid="stAudioInput"] button[aria-label="Record"],
[data-testid="stAudioInput"] button[aria-label="Stop recording"] {
  width:112px; height:112px; min-width:112px; border-radius:50%; background:#0b8f78;
  color:#fff; border:0; box-shadow:0 0 0 12px #f1f9f6,0 8px 24px #0b8f781c;
  transition:background .2s,box-shadow .2s,transform .2s;
}
[data-testid="stAudioInput"] button[aria-label="Record"]:hover { background:#087563; transform:translateY(-2px); }
[data-testid="stAudioInput"] button[aria-label="Stop recording"] { background:#d94747; box-shadow:0 0 0 12px #fdf1f1; }
[data-testid="stAudioInput"] button[aria-label="Record"] svg,
[data-testid="stAudioInput"] button[aria-label="Stop recording"] svg { width:38px; height:38px; }
[data-testid="stAudioInput"]:has(button[aria-label="Record"]:not(:disabled)):not(:has(button[aria-label="Play"],button[aria-label="Pause"])) [data-testid="stAudioInputWaveformTimeCode"] { display:none; }
/* The native idle waveform is decorative. Keep permission/error messages visible. */
[data-testid="stAudioInput"]:has(button[aria-label="Record"]:not(:disabled)):not(:has(button[aria-label="Play"],button[aria-label="Pause"])) > div:last-child > div:has(> [data-testid="stAudioInputWaveSurfer"]) { display:none; }
[data-testid="stAudioInputWaveSurfer"] { width:260px; }
[data-testid="stAudioInputWaveformTimeCode"] { direction:ltr; }
@media (max-width:640px) {
  [data-testid="stMainBlockContainer"] { padding:18px 20px 40px; }
  .st-key-voice_landing { margin-top:25vh; }
  .st-key-voice_landing [data-testid="stMarkdownContainer"] p { font-size:14px; }
}
.shelf-product-item,.jet-cart-item-card,.jet-product-card { background:#fff; border:1px solid var(--line); border-radius:16px; padding:13px; box-shadow:0 3px 12px rgba(16,42,67,.04); transition:.2s ease; }
.shelf-product-item:hover,.jet-cart-item-card:hover,.jet-product-card:hover { border-color:#83d9c8; transform:translateY(-2px); box-shadow:0 10px 22px rgba(16,42,67,.08); }
.shelf-img-box,.jet-cart-img-box,.jet-card-img-container { width:100%; height:112px; display:flex; align-items:center; justify-content:center; background:#f4f7fa; border-radius:12px; margin-bottom:10px; padding:8px; overflow:hidden; position:relative; }
.shelf-img,.jet-cart-img,.jet-card-img { max-width:100%; max-height:100%; object-fit:contain; }
.shelf-discount-tag,.jet-card-discount-badge { position:absolute; top:7px; right:7px; background:#e8590c; color:#fff; padding:3px 7px; border-radius:999px; font-size:.68rem; font-weight:800; direction:ltr; }
.shelf-title,.jet-cart-title,.jet-card-product-title { font-size:.83rem; font-weight:700; color:var(--ink); line-height:1.45; min-height:2.4em; margin-bottom:5px; }
.shelf-price,.jet-card-price-primary { font-size:.85rem; font-weight:800; color:var(--ink); }
.jet-cart-grid,.jet-product-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(205px,1fr)); gap:13px; margin:12px 0 18px; }
.jet-cart-card-top,.jet-card-header-bar,.jet-card-meta-row,.jet-card-price-container,.jet-card-footer-summary { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.jet-cart-brand-tag,.jet-cart-vol-badge,.jet-card-qty-badge { background:#f0f4f7; color:var(--muted); padding:3px 8px; border-radius:7px; font-size:.69rem; font-weight:700; }
.jet-cart-qty-tag { background:#d7f5ee; color:var(--brand-dark); padding:3px 8px; border-radius:999px; font-size:.7rem; font-weight:800; }
.jet-card-req-title,.jet-currency-unit,.jet-card-old-price { color:var(--muted); font-size:.71rem; }
.jet-card-stock-in,.jet-cart-ready-chip,.jet-card-saving-pill { color:#087f5b; font-size:.71rem; font-weight:800; }
.jet-card-stock-out { color:#c92a2a; font-size:.71rem; font-weight:800; }
.jet-card-price-container { margin:9px 0 7px; border-top:1px dashed var(--line); padding-top:8px; }
.jet-card-line-total { color:var(--ink); font-size:.73rem; }
.jet-checkout-summary-card { background:linear-gradient(135deg,#fff 0%,#edfdf8 100%); border:1px solid #9ee8d7; border-radius:20px; padding:20px 24px; margin:18px 0; box-shadow:0 10px 28px rgba(11,143,120,.08); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:18px; }
.jet-summary-col { text-align:right; }.jet-summary-label { color:var(--muted); font-size:.75rem; margin-bottom:4px; }.jet-summary-val-highlight { color:var(--brand-dark); font-size:1.45rem; font-weight:800; }.jet-summary-val-saving { color:#087f5b; font-size:1.05rem; font-weight:800; }.jet-summary-val-fee,.jet-summary-val-badge { color:var(--ink); font-size:1.05rem; font-weight:800; }
.badge-ok { background:#d7f5ee; color:#087f5b; padding:4px 9px; border-radius:999px; font-size:.76rem; font-weight:700; display:inline-block; }.badge-err { background:#ffe3e3; color:#c92a2a; padding:4px 9px; border-radius:999px; font-size:.76rem; font-weight:700; display:inline-block; }

</style>
""", unsafe_allow_html=True)


def _oidc_is_configured() -> bool:
    try:
        return bool(st.secrets.get("auth", {}).get("client_id"))
    except Exception:
        return False


AUTH_ENABLED = _oidc_is_configured() or os.getenv("SABAD_REQUIRE_AUTH", "").lower() in {"1", "true", "yes"}
COMPARE_LIMITER = SlidingWindowLimiter()
initialize_preferences()


@st.cache_resource
def get_price_history_store() -> PriceHistoryStore:
    return PriceHistoryStore()


@st.cache_resource
def get_feedback_store() -> FeedbackStore:
    return FeedbackStore()


@st.fragment
def render_feedback_control(item: StoreItem, requested_text: str, view_key: str) -> None:
    """Ask why a shown product is wrong without rerunning the whole comparison."""
    token = hashlib.sha256(f"{view_key}:{item.platform}:{item.product_id}:{requested_text}".encode()).hexdigest()[:16]
    with st.popover("این کالا مناسب نیست"):
        reason = st.pills(
            "چرا مناسب نیست؟",
            FEEDBACK_REASONS,
            key=f"feedback_reason_{token}",
        )
        if st.button("ثبت دلیل", key=f"feedback_submit_{token}"):
            if not reason:
                st.warning("یک دلیل را انتخاب کن.")
            else:
                get_feedback_store().submit(
                    requested_text=requested_text,
                    selected_title=item.title,
                    platform=item.platform,
                    reason=reason,
                    session_key=_session_identity(),
                )
                st.success("ثبت شد.")


def _session_identity() -> str:
    user = getattr(st, "user", None)
    email = getattr(user, "email", None) if user else None
    return str(email or st.session_state.get("session_identity") or id(st.session_state))


def close_settings():
    st.session_state["settings_open"] = False


@st.dialog("تنظیمات", on_dismiss=close_settings)
def settings_dialog():
    render_settings(auth_enabled=AUTH_ENABLED, oidc_configured=_oidc_is_configured())


def render_product_grid(cards: list[dict], view: str) -> None:
    """Render safe native Streamlit product cards with clickable retailer links."""
    if not cards:
        st.info("کالایی برای نمایش وجود ندارد.")
        return

    columns = st.columns(min(4, len(cards)), gap="small")
    for index, card in enumerate(cards):
        item: StoreItem = card["item"]
        requested_title = card.get("requested_title", item.title)
        store_title = card.get("store_title", item.platform)
        with columns[index % len(columns)]:
            with st.container(border=True):
                st.caption(store_title)
                image_url, _ = resolve_product_image_and_fallback(item.title, item.image_url)
                st.image(image_url, width="stretch")
                st.caption(f"درخواستی: {requested_title}")
                product_link = build_product_link(
                    item.platform,
                    item.title,
                    product_id=item.product_id,
                    store_id=item.store_id,
                    explicit_url=item.product_url,
                )
                # API titles can contain Markdown markers (for example
                # ``**ماکارونی**``). Escape them so the anchor remains a real
                # clickable link instead of becoming malformed Markdown.
                safe_title = (
                    str(item.title)
                    .replace("\\", "\\\\")
                    .replace("*", "\\*")
                    .replace("_", "\\_")
                    .replace("[", "\\[")
                    .replace("]", "\\]")
                )
                st.markdown(f"[**{safe_title}**]({product_link})")
                price_text = f"{item.discount_price:,.0f} تومان"
                if item.base_price > item.discount_price:
                    price_text += f" · {item.discount_percent:.0f}٪ تخفیف"
                st.markdown(f"**{price_text}** · {card.get('quantity', 1)} عدد")
                unit_text = comparable_price_text(item)
                if unit_text:
                    st.caption(unit_text)
                options = card.get("unit_options") or []
                cheapest = next((row for row in options if row.get("is_cheapest")), None)
                if cheapest and len(options) > 1:
                    if str(cheapest.get("product_id")) == str(item.product_id):
                        st.caption("ارزان‌ترین گزینهٔ بررسی‌شده بر اساس حجم")
                    else:
                        st.caption(f"ارزان‌ترین بر اساس حجم: {cheapest['title']} · {cheapest['text']}")
                change = st.session_state.get("price_changes", {}).get(PriceHistoryStore.item_key(item))
                if change and change.get("label"):
                    st.caption(change["label"])
                st.link_button("مشاهدهٔ محصول ↗", product_link, type="secondary")
                render_feedback_control(item, requested_title, f"{view}:{index}")


with st.container(key="app_toolbar", horizontal=True, horizontal_alignment="right"):
    if st.button("تنظیمات", icon=":material/settings:", key="open_settings"):
        st.session_state["settings_open"] = True
if st.session_state.get("settings_open"):
    settings_dialog()

lat, lng = LOCATIONS.get(st.session_state["delivery_location"], next(iter(LOCATIONS.values())))
use_ai = st.session_state["use_ai"] and bool(GEMINI_API_KEY)
allow_split = st.session_state["allow_split"]
split_penalty = st.session_state["split_penalty"]

has_basket = bool(st.session_state["user_basket_text"].strip()) or st.session_state["show_editor"] or "opt_result" in st.session_state
with st.container(key="voice_review" if has_basket else "voice_landing", horizontal_alignment="center"):
    voice_key = f"basket_voice_note_{st.session_state['voice_generation']}"
    voice_note = None
    voice_payload = None
    if _uses_serverless_voice_recorder():
        # Avoid Streamlit's internal multipart upload endpoint on Vercel. The
        # browser component sends the short recording through the session
        # state channel instead, which works with a Python Function.
        from sabad.voice_recorder import decode_recording, voice_recorder

        voice_payload = voice_recorder(key=voice_key)
    else:
        voice_note = st.audio_input(
            "ضبط لیست خرید", key=voice_key,
            label_visibility="collapsed", width=340,
        )
    st.markdown("خریدت رو بگو؛ ارزون‌ترین سبد رو با هزینهٔ ارسال پیدا می‌کنیم.")

# Consume each recording once and update the editor before it is instantiated.
recording = None
recording_mime_type = "audio/wav"
if voice_payload:
    recording = decode_recording(voice_payload)
    if recording:
        voice_bytes, recording_mime_type = recording
elif voice_note is not None:
    voice_bytes = voice_note.getvalue()
    recording = (voice_bytes, getattr(voice_note, "type", None) or "audio/wav")

if recording is not None:
    voice_hash = hashlib.sha256(voice_bytes).hexdigest()
    if st.session_state.get("last_voice_hash") != voice_hash:
        st.session_state["last_voice_hash"] = voice_hash
        st.session_state.pop("voice_error", None)
        audio_validation = validate_audio_size(len(voice_bytes))
        if not audio_validation.ok:
            st.session_state["voice_error"] = audio_validation.message
        elif not GEMINI_API_KEY:
            st.session_state["voice_error"] = "تبدیل صدا به متن هنوز فعال نشده؛ از تنظیمات می‌تونی لیستت رو بنویسی."
        else:
            with st.spinner("داریم لیست خریدت رو می‌نویسیم…"):
                transcript = transcribe_audio_gemini(voice_bytes, recording_mime_type)
            if transcript:
                st.session_state["user_basket_text"] = transcript
                st.session_state["basket_editor"] = transcript
                st.session_state["show_editor"] = True
                invalidate_comparison()
                st.rerun()
            else:
                st.session_state["voice_error"] = "صدا واضح نبود. دوباره ضبط کن یا از تنظیمات لیستت رو بنویس."
if st.session_state.get("voice_error"):
    st.warning(st.session_state["voice_error"])


def update_basket():
    st.session_state["user_basket_text"] = st.session_state["basket_editor"]
    invalidate_comparison()


def replace_basket(text):
    st.session_state["user_basket_text"] = text
    st.session_state["basket_editor"] = text
    invalidate_comparison()


def clear_basket():
    replace_basket("")
    st.session_state["show_editor"] = False
    st.session_state["voice_generation"] += 1
    st.session_state.pop("last_voice_hash", None)
    st.session_state.pop("voice_error", None)


user_input = st.session_state["user_basket_text"]
if user_input.strip() or st.session_state["show_editor"]:
    if st.session_state.pop("_sync_basket_editor", False):
        st.session_state["basket_editor"] = user_input
    st.session_state.setdefault("basket_editor", user_input)
    st.text_area(
        "لیست خریدت", key="basket_editor", height=100,
        placeholder="مثلاً دو تا شیر و یک پنیر…", on_change=update_basket,
    )
    user_input = st.session_state["user_basket_text"]

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


def get_catalog_harvester() -> CatalogHarvester:
    # Adapters hold branch and account state; keep them within this user's session.
    if "catalog_harvester" not in st.session_state:
        st.session_state["catalog_harvester"] = CatalogHarvester()
    return st.session_state["catalog_harvester"]


parse_key = (user_input, use_ai, GEMINI_MODEL)
if st.session_state.get("parsed_basket_key") != parse_key:
    st.session_state["parsed_basket"] = (
        safe_parse_grocery_input(user_input, use_ai=use_ai)
        if user_input.strip() else ParsedGroceryBasket(raw_input=user_input, items=[])
    )
    st.session_state["parsed_basket_key"] = parse_key
parsed_basket = st.session_state["parsed_basket"]

if parsed_basket.items:
    for i, item in enumerate(parsed_basket.items):
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
            st.markdown(f"{i + 1}. {item.display_title}")
            remaining = "، ".join(
                it.raw_text.strip() if it.raw_text and it.raw_text.strip() else it.display_title
                for idx, it in enumerate(parsed_basket.items) if idx != i
            )
            st.button(
                f"حذف {item.name}", key=f"del_cart_item_{i}", icon=":material/close:",
                on_click=replace_basket, args=(remaining,),
            )
if user_input.strip() or st.session_state["show_editor"] or "opt_result" in st.session_state:
    st.button("خالی کردن سبد", key="clear_all_basket_btn", on_click=clear_basket)

# -------------------------------------------------------------
# Section 2: Live Execution Pipeline
# -------------------------------------------------------------
if (user_input.strip() or st.session_state["show_editor"]) and st.button("پیدا کردن ارزان‌ترین سبد", type="primary", icon=":material/search:", key="compare_basket"):
    if AUTH_ENABLED and not getattr(st.user, "is_logged_in", False):
        st.warning("برای مقایسه، از تنظیمات وارد حساب سبد شو.")
        st.stop()
    basket_check = validate_basket_text(user_input)
    if not basket_check.ok:
        st.warning(basket_check.message)
        st.stop()
    if not parsed_basket.items:
        st.warning("لطفاً حداقل یک قلم کالا در سبد بنویسید.")
        st.stop()
    if len(parsed_basket.items) > MAX_BASKET_ITEMS:
        st.warning(f"حداکثر {MAX_BASKET_ITEMS} قلم در هر جست‌وجو بررسی می‌شود.")
        st.stop()
    allowed, retry_after = COMPARE_LIMITER.allow(_session_identity())
    if not allowed:
        st.warning(f"جست‌وجوهای این دقیقه تمام شد. {retry_after} ثانیهٔ دیگر دوباره امتحان کن.")
        st.stop()

    with st.status("در حال بررسی قیمت، تخفیف و ارسال…", expanded=False) as status:
        harvester = get_catalog_harvester()
        harvester, store_infos, catalog_matches, flash_deals, opt_result = asyncio.run(
            compare_and_optimize_basket(
                parsed_basket.items,
                lat,
                lng,
                split_penalty_tomans=split_penalty,
                allow_multi_store=allow_split,
                harvester=harvester,
            )
        )
        st.session_state["flash_deals_by_store"] = flash_deals

        status.update(label="بررسی فروشگاه‌ها انجام شد", state="complete", expanded=False)

    # Store result in session state for dispatch and itemized audit
    try:
        changes = get_price_history_store().record_matches(catalog_matches)
        st.session_state["price_changes"] = {key: asdict(change) for key, change in changes.items()}
    except Exception as exc:
        log_store_failure("app", "price_history", exc)
        st.session_state["price_changes"] = {}
    st.session_state["catalog_matches"] = catalog_matches
    st.session_state["search_evidence"] = getattr(harvester, "last_search_evidence", {})
    st.session_state["store_infos"] = store_infos
    st.session_state["basket_items"] = parsed_basket.items
    st.session_state["opt_result"] = opt_result
    st.session_state["adapters"] = harvester.adapters


# -------------------------------------------------------------
# Section 3: Optimization Results & Comparison
# -------------------------------------------------------------
if "opt_result" in st.session_state:
    opt_result = st.session_state["opt_result"]
    adapters = st.session_state.get("adapters")
    if not adapters:
        adapters = get_catalog_harvester().adapters
        st.session_state["adapters"] = adapters
    catalog_matches = st.session_state.get("catalog_matches", {})
    search_evidence = st.session_state.get("search_evidence", {})
    store_infos = st.session_state.get("store_infos", {})
    basket_items = st.session_state.get("basket_items", [])
    if not basket_items and "parsed_basket" in locals() and getattr(parsed_basket, "items", None):
        basket_items = parsed_basket.items

    st.subheader("نتیجهٔ مقایسه")

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

    st.success(
        "این سبد از بین فروشگاه‌های بررسی‌شده کم‌هزینه‌ترین گزینه است؛ "
        "قیمت کالا، تخفیف و هزینهٔ ارسال همگی در محاسبه لحاظ شده‌اند."
    )

    # Store comparison: compact cards are the primary view. The numerical
    # dataframe stays available inside a collapsed details panel.
    comparison_data = []
    for s_name, order in opt_result.single_store_orders.items():
        adapter = adapters.get(s_name) if adapters else None
        title = adapter.platform_title_fa if adapter else s_name
        store_missing = []
        for requested_item in basket_items:
            found = catalog_matches.get(requested_item.raw_text, {}).get(s_name)
            if not found or not found.is_in_stock:
                store_missing.append(requested_item.display_title)

        with st.container(border=True):
            head_col, status_col = st.columns([3, 1], vertical_alignment="center")
            with head_col:
                st.markdown(f"### {title}")
            with status_col:
                if order and not store_missing:
                    st.badge("کامل", icon=":material/check_circle:", color="green")
                elif order:
                    st.badge(f"{len(store_missing)} قلم کسری", icon=":material/warning:", color="orange")
                else:
                    st.badge("تأمین نشد", icon=":material/error:", color="red")
            if order:
                cost_col, fee_col, discount_col = st.columns(3)
                cost_col.metric("پرداختی", f"{order.total_cost:,.0f} ت")
                fee_col.metric("ارسال", f"{order.delivery_fee:,.0f} ت")
                discount_col.metric("تخفیف", f"{order.total_savings:,.0f} ت")
            if store_missing:
                for requested_item in basket_items:
                    if requested_item.display_title not in store_missing:
                        continue
                    evidence = search_evidence.get(requested_item.raw_text, {}).get(s_name, {})
                    st.markdown(
                        explain_missing_item(
                            evidence,
                            requested_title=requested_item.display_title,
                            product_name=requested_item.name,
                        )
                    )
                with st.expander("صحت‌سنجی جست‌وجو", icon=":material/search:"):
                    for requested_item in basket_items:
                        if requested_item.display_title not in store_missing:
                            continue
                        evidence = search_evidence.get(requested_item.raw_text, {}).get(s_name, {})
                        attempts = evidence.get("queries", [])
                        query_text = " ← ".join(a.get("query", "") for a in attempts if a.get("query")) or "—"
                        st.markdown(f"**{requested_item.display_title}**")
                        st.caption(f"عبارت‌های جست‌وجو: {query_text}")
                        st.caption(f"تعداد نتایج خام: {evidence.get('candidate_count', 0)}")
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

    with st.expander("جزئیات عددی مقایسه فروشگاه‌ها", expanded=False, icon=":material/table_chart:"):
        st.dataframe(comparison_data, width="stretch")

    def render_store_audit_tab(
        platform: str,
        basket_items: list,
        catalog_matches: dict,
        store_infos: dict,
        opt_result: OptimizationResult,
        adapters: dict,
        search_evidence: dict | None = None,
    ) -> None:
        search_evidence = search_evidence or {}
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
        store_cards = []
        for item in basket_items:
            match = None
            if catalog_matches and item.raw_text in catalog_matches:
                match = catalog_matches[item.raw_text].get(platform)
            elif catalog_matches and getattr(item, "name", None) in catalog_matches:
                match = catalog_matches[item.name].get(platform)

            if match:
                store_cards.append({
                    "item": match,
                    "requested_title": item.display_title,
                    "store_title": platform_title,
                    "quantity": item.quantity,
                    "unit_options": search_evidence.get(item.raw_text, {}).get(platform, {}).get("unit_options") or [],
                })

        if store_cards:
            with st.expander(f"🖼️ ویترین تصویری کالاهای منطبق در {platform_title}", expanded=True):
                render_product_grid(store_cards, platform)

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
                unit_text = comparable_price_text(match) or "-"

                audit_rows.append({
                    "قلم درخواستی": item.display_title,
                    "کالای متناظر در فروشگاه": match.title,
                    "حجم/مشخصات انطباق‌یافته": vol_spec,
                    "قیمت پایه واحد (تومان)": f"{match.base_price:,.0f}",
                    "قیمت فروش واحد (تومان)": f"{match.discount_price:,.0f}",
                    "قیمت قابل مقایسه": unit_text,
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
                    "قیمت قابل مقایسه": comparable_price_text(match) or "-",
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
                    "قیمت قابل مقایسه": "-",
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
                    evidence = search_evidence.get(m_item.raw_text, {}).get(platform, {})
                    attempts = evidence.get("queries", [])
                    query_text = " ← ".join(a.get("query", "") for a in attempts if a.get("query")) or "—"
                    st.markdown(f"- **{m_item.display_title}**:")
                    st.markdown(f"  - عبارت جست‌وجو: `{query_text}`")
                    st.markdown(
                        "  - "
                        + explain_missing_item(
                            evidence,
                            requested_title=m_item.display_title,
                            product_name=m_item.name,
                        )
                    )
                    if evidence.get("candidate_titles"):
                        st.caption("نتایج خام: " + "، ".join(evidence["candidate_titles"][:4]))
                    if m_item.volume_weight is not None:
                        st.markdown(
                            "این قلم با حجم/وزن مشخص درخواست شده و تطبیق حجم هم بررسی شده است؛ "
                            "رد شدن به دلیل عدم انطباق با حجم درخواستی ممکن است."
                        )
                    else:
                        st.caption("حجم یا وزن مشخص نشده بود؛ اندازه‌های مختلف با همان نام کالا قابل‌قبول‌اند.")

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
        search_evidence: dict | None = None,
    ) -> None:
        search_evidence = search_evidence or {}
        st.markdown("#### 🏆 سبد پیشنهادی")

        # -------------------------------------------------------------
        # Visual Product Cards Gallery (Digikala Jet Aesthetics)
        # -------------------------------------------------------------
        st.markdown("##### کالاهای انتخاب‌شده")

        visual_cards = []
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
                    visual_cards.append({
                        "item": found_asgn.item,
                        "requested_title": item.display_title,
                        "store_title": winning_store_title,
                        "quantity": found_asgn.quantity,
                        "unit_options": search_evidence.get(item.raw_text, {}).get(winning_platform, {}).get("unit_options") or [],
                    })

        if not basket_items and opt_result and opt_result.optimal_orders:
            for order in opt_result.optimal_orders:
                adapter = adapters.get(order.platform) if adapters else None
                store_title = adapter.platform_title_fa if adapter else order.platform
                if order.items:
                    for asgn in order.items:
                        visual_cards.append({
                            "item": asgn.item,
                            "requested_title": asgn.item.title,
                            "store_title": store_title,
                            "quantity": asgn.quantity,
                        })

        if visual_cards:
            render_product_grid(visual_cards, "optimal")
        else:
            st.info("اقلامی برای نمایش تصویری در سبد برگزیده ثبت نشده است.")

        st.markdown("##### اقلام سبد پیشنهادی")
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
                        "کالا": found_asgn.item.title,
                        "قیمت واحد (تومان)": f"{found_asgn.item.discount_price:,.0f}",
                        "قیمت قابل مقایسه": comparable_price_text(found_asgn.item) or "-",
                        "تعداد": found_asgn.quantity,
                        "مجموع ردیف (تومان)": f"{found_asgn.line_total:,.0f}",
                        "سود تخفیف (تومان)": f"{found_asgn.nominal_saving:,.0f}",
                    })
                else:
                    optimal_table_rows.append({
                        "قلم درخواستی": item.display_title,
                        "فروشگاه برنده": "❌ عدم تامین",
                        "کالا": "❌ تأمین نشد",
                        "قیمت واحد (تومان)": "-",
                        "قیمت قابل مقایسه": "-",
                        "تعداد": item.quantity,
                        "مجموع ردیف (تومان)": "-",
                        "سود تخفیف (تومان)": "-",
                    })
        elif basket_items:
            for item in basket_items:
                optimal_table_rows.append({
                    "قلم درخواستی": item.display_title,
                    "فروشگاه برنده": "❌ عدم تامین",
                    "کالا": "❌ تأمین نشد",
                    "قیمت واحد (تومان)": "-",
                    "قیمت قابل مقایسه": "-",
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
                            "کالا": asgn.item.title,
                            "قیمت واحد (تومان)": f"{asgn.item.discount_price:,.0f}",
                            "قیمت قابل مقایسه": comparable_price_text(asgn.item) or "-",
                            "تعداد": asgn.quantity,
                            "مجموع ردیف (تومان)": f"{asgn.line_total:,.0f}",
                            "سود تخفیف (تومان)": f"{asgn.nominal_saving:,.0f}",
                        })

        if optimal_table_rows:
            st.dataframe(optimal_table_rows, width="stretch")
        else:
            st.warning("هیچ قلم کالایی در سبد بهینه ثبت نشده است.")

        st.markdown("##### جمع سفارش‌ها")
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

    with st.expander("جزئیات فروشگاه‌ها و صحت‌سنجی جست‌وجو", expanded=False, icon=":material/fact_check:"):
        tab_opt, tab_snapp, tab_jet, tab_okala, tab_tapsi = st.tabs([
            "🏆 سبد بهینه نهایی (تخصیص هوشمند)",
            "🟡 اسنپ‌مارکت (SnappMarket)",
            "🔴 دیجی‌کالا جت (Digikala Jet)",
            "🟢 افق کوروش / اکالا (Okala)",
            "🟠 تپسی مارکت (Tapsi Market)",
        ])

        with tab_opt:
            render_optimal_basket_tab(opt_result, basket_items, catalog_matches, adapters, search_evidence)

        with tab_snapp:
            render_store_audit_tab("snapp_market", basket_items, catalog_matches, store_infos, opt_result, adapters, search_evidence)

        with tab_jet:
            render_store_audit_tab("digikala_jet", basket_items, catalog_matches, store_infos, opt_result, adapters, search_evidence)

        with tab_okala:
            render_store_audit_tab("okala", basket_items, catalog_matches, store_infos, opt_result, adapters, search_evidence)

        with tab_tapsi:
            render_store_audit_tab("tapsi_market", basket_items, catalog_matches, store_infos, opt_result, adapters, search_evidence)

    # Optional deals belong at the end of the decision flow so they do not
    # distract from the cheapest-basket result.
    deal_opps = getattr(opt_result, "deal_opportunities", [])
    if deal_opps:
        with st.expander("پیشنهادهای تخفیفی اختیاری", expanded=True, icon=":material/local_offer:"):
            st.caption("این پیشنهادها اختیاری‌اند و قبل از افزودن کالا به سبد نمایش داده می‌شوند.")
            for deal_idx, opportunity in enumerate(deal_opps):
                is_switch = opportunity.opportunity_type == "store_switch_deal"
                action_label = (
                    f"انتقال به {opportunity.target_store_title} و افزودن"
                    if is_switch
                    else f"افزودن با {opportunity.deal_discount_percent:.0f}٪ تخفیف"
                )
                with st.container(border=True):
                    title_col, action_col = st.columns([3, 1], vertical_alignment="center")
                    with title_col:
                        st.markdown(f"**{opportunity.deal_item.title}**")
                        st.caption(
                            f"{opportunity.target_store_title} · "
                            f"قیمت نهایی {opportunity.deal_discount_price:,.0f} تومان · "
                            f"صرفه‌جویی {opportunity.deal_nominal_saving:,.0f} تومان"
                        )
                    with action_col:
                        action_key_prefix = "btn_switch_opp" if is_switch else "btn_addon_opp"
                        if st.button(action_label, key=f"{action_key_prefix}_{deal_idx}_{opportunity.deal_item.product_id}"):
                            current_text = st.session_state.get("user_basket_text", "").strip()
                            added_text = f"یک {opportunity.deal_item.title}"
                            new_text = f"{current_text}، {added_text}" if current_text else added_text
                            st.session_state["user_basket_text"] = new_text
                            st.session_state["_sync_basket_editor"] = True
                            updated_opt, updated_basket, updated_catalog = FlashDealAdvisor.apply_opportunity(
                                opt_result=opt_result,
                                opportunity=opportunity,
                                store_infos=store_infos,
                                basket_items=basket_items,
                                catalog_matches=catalog_matches,
                            )
                            st.session_state["opt_result"] = updated_opt
                            st.session_state["basket_items"] = updated_basket
                            st.session_state["catalog_matches"] = updated_catalog
                            st.rerun()


    # -------------------------------------------------------------
    # Section 5: Cart Population & Payment Handoff
    # -------------------------------------------------------------
    st.subheader("🛒 آمادهٔ خرید")

    st.caption("وقتی آماده‌ای، کالاها را به سبد فروشگاه‌های منتخب منتقل کن و پرداخت را ادامه بده.")

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
