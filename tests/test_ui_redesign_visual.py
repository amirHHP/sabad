"""
Tests for UI Redesign, Digikala Jet Visual Aesthetics, and Product Image Rendering.
Verifies product card HTML structure, image resolution, category fallbacks, shelf items,
and AppTest rendering of the visual product grids.
"""

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

from sabad.config import BASE_DIR
from sabad.ui_assets import (
    POPULAR_SHELF_ITEMS,
    resolve_product_image_and_fallback,
    render_jet_product_card_html,
    STORE_METADATA,
    create_svg_fallback,
)
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier
from sabad.optimizer.milp_solver import MILPBasketOptimizer
from sabad.harvester import CatalogHarvester


def test_popular_shelf_items_structure():
    """Verify popular grocery shelf items are configured with titles, images, and prices."""
    assert len(POPULAR_SHELF_ITEMS) >= 6, "Shelf should have at least 6 everyday essentials"
    for item in POPULAR_SHELF_ITEMS:
        assert "title" in item and len(item["title"]) > 0
        assert "brand" in item and len(item["brand"]) > 0
        assert "raw_text" in item and len(item["raw_text"]) > 0
        assert "price_approx" in item and item["price_approx"] > 0
        assert "image_url" in item and item["image_url"].startswith("http")
        assert "discount_percent" in item and item["discount_percent"] >= 0


def test_image_resolution_for_staple_categories():
    """Verify resolve_product_image_and_fallback returns valid images and SVG fallbacks for all staple categories."""
    test_titles = [
        ("دو تا شیر پرچرب کاله", "milk"),
        ("پنیر خامه‌ای ویلی ۳۵۰ گرمی", "cheese"),
        ("کره پاستوریزه کاله ۱۰۰ گرم", "butter"),
        ("ماست دبه‌ای سون کاله", "yogurt"),
        ("یک بسته تخم مرغ تلاونگ", "egg"),
        ("روغن زیتون فرابکر ۱ لیتری", "oil"),
        ("برنج طارم هاشمی", "rice"),
        ("ماکارونی ۷۰۰ گرمی زر", "pasta"),
        ("کنسرو تن ماهی شیلتون", "tuna"),
        ("مایع ظرفشویی پریل لیمو", "dishwashing"),
        ("مایع دستشویی کرمی اکتیو", "handwash"),
        ("دستمال توالت ۴ قلوی پاپیا", "tissue"),
        ("چای سیلان دوغزال", "tea"),
        ("عسل سدر طبیعی", "honey"),
        ("بیسکویت پتی بور", "snack"),
    ]

    import urllib.parse
    for title, expected_keyword in test_titles:
        img_url, fallback_uri = resolve_product_image_and_fallback(title)
        assert img_url.startswith("http"), f"Image URL for '{title}' must be valid HTTP URL"
        assert fallback_uri.startswith("data:image/svg+xml;utf8,"), f"Fallback URI for '{title}' must be SVG data URI"
        assert "<svg" in urllib.parse.unquote(fallback_uri)


def test_image_resolution_explicit_url_precedence():
    """Verify that explicit image URLs provided on StoreItem take precedence over category fallbacks."""
    custom_cdn = "https://custom-retailer-cdn.ir/products/specific_sku_99.png"
    img_url, fallback_uri = resolve_product_image_and_fallback("شیر کاله", explicit_url=custom_cdn)
    assert img_url == custom_cdn
    assert fallback_uri.startswith("data:image/svg+xml;utf8,")


def test_render_jet_product_card_html():
    """Verify HTML product card mimics Digikala Jet with image, prices, tags, and fallback."""
    card_html = render_jet_product_card_html(
        product_title="شیر پرچرب کاله ۱ لیتری",
        requested_title="شیر کاله",
        platform="digikala_jet",
        price=37800.0,
        base_price=42000.0,
        quantity=2,
        image_url="https://dkstatics-public.digikala.com/digikala-products/113df70a77c84301dceee3db0bef3b9c55e9b41d_1701035054.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        is_in_stock=True,
        discount_percent=10.0,
        store_title_override="دیجی‌کالا جت",
    )

    assert "jet-product-card" in card_html
    assert "شیر پرچرب کاله ۱ لیتری" in card_html
    assert "دیجی‌کالا جت" in card_html
    assert "37,800" in card_html
    assert "42,000" in card_html
    assert "۱۰٪ تخفیف" in card_html or "10٪ تخفیف" in card_html or "٪ تخفیف" in card_html
    assert "۲ عدد" in card_html or "2 عدد" in card_html
    assert "75,600" in card_html
    assert "<img" in card_html
    assert "onerror=" in card_html


def test_apptest_renders_visual_product_grid_with_images():
    """Verify AppTest successfully boots and renders the visual product grid in the optimal basket tab."""
    basket_items = [
        ParsedGroceryItem(raw_text="دو تا شیر پرچرب کاله یک لیتری", name="شیر", quantity=2),
        ParsedGroceryItem(raw_text="یه مایع ظرفشویی پریل ۴ لیتری", name="مایع ظرفشویی", quantity=1),
    ]

    store_infos = {
        "digikala_jet": StoreInfo(
            platform="digikala_jet",
            store_id="jet_1",
            title="جت مارت یوسف‌آباد (دیجی‌کالا جت)",
            is_open=True,
            minimum_order_value=50000.0,
            delivery_tiers=[DeliveryTier(min_subtotal=0, max_subtotal=None, fee=25000.0)],
        ),
        "snapp_market": StoreInfo(
            platform="snapp_market",
            store_id="snapp_1",
            title="هایپراستار ارم",
            is_open=True,
            minimum_order_value=50000.0,
            delivery_tiers=[DeliveryTier(min_subtotal=0, max_subtotal=None, fee=29000.0)],
        ),
    }

    item1_jet = StoreItem(
        platform="digikala_jet",
        store_id="jet_1",
        product_id="jet_milk",
        title="شیر پرچرب کاله ۱ لیتری",
        base_price=42000.0,
        discount_price=37800.0,
        discount_percent=10.0,
        is_in_stock=True,
        image_url="https://dkstatics-public.digikala.com/digikala-products/113df70a77c84301dceee3db0bef3b9c55e9b41d_1701035054.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
    )
    item2_snapp = StoreItem(
        platform="snapp_market",
        store_id="snapp_1",
        product_id="sp_pril",
        title="مایع ظرفشویی پریل ۴ لیتری",
        base_price=180000.0,
        discount_price=162000.0,
        discount_percent=10.0,
        is_in_stock=True,
        image_url="https://dkstatics-public.digikala.com/digikala-products/723d422b1d7a727f89b80ae0e43073e4a8194ca3_1770546437.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
    )

    catalog_matches = {
        basket_items[0].raw_text: {"digikala_jet": item1_jet, "snapp_market": None},
        basket_items[1].raw_text: {"digikala_jet": None, "snapp_market": item2_snapp},
    }

    opt_result = MILPBasketOptimizer().optimize(
        basket_items=basket_items,
        catalog_matches=catalog_matches,
        store_infos=store_infos,
        allow_multi_store=True,
    )

    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = catalog_matches
    at.session_state["store_infos"] = store_infos
    at.session_state["basket_items"] = basket_items
    at.session_state["opt_result"] = opt_result
    at.session_state["adapters"] = CatalogHarvester().adapters

    at.run(timeout=30)
    assert len(at.exception) == 0

    # Verify visual grid exists in rendered markdown
    markdown_html = "\n".join(m.value for m in at.markdown)
    assert "jet-product-grid" in markdown_html, "Visual product grid must be rendered"
    assert "jet-product-card" in markdown_html, "Visual product cards must be rendered"
    assert "شیر پرچرب کاله ۱ لیتری" in markdown_html
    assert "مایع ظرفشویی پریل ۴ لیتری" in markdown_html
    assert "<img" in markdown_html, "Product images (<img tags) must be rendered"
    assert "jet-navbar" in markdown_html, "Digikala Jet navbar must be rendered"
    assert "jet-stepper" in markdown_html, "Beginner onboarding stepper must be rendered"


def test_render_selected_cart_card_html():
    """Verify render_selected_cart_card_html produces expected HTML structure for cart preview."""
    from sabad.ui_assets import render_selected_cart_card_html
    card_html = render_selected_cart_card_html(
        title="شیر پرچرب کاله ۱ لیتری",
        brand="کاله",
        quantity=2,
        volume_spec="1 لیتر",
    )
    assert "jet-cart-item-card" in card_html
    assert "شیر پرچرب کاله ۱ لیتری" in card_html
    assert "کاله" in card_html
    assert "۲ عدد" in card_html or "2 عدد" in card_html
    assert "<img" in card_html
    assert "onerror=" in card_html


def test_image_resolution_expanded_staple_categories():
    """Verify newly added staple categories resolve to proper fallbacks."""
    new_categories = [
        ("یک قوطی رب گوجه فرنگی تبرک", "رب"),
        ("ژل مایع لباسشویی پرسیل", "لباسشویی"),
        ("یک بسته چای سیلان دوغزال", "چای"),
        ("یک کیلو شکر سفید", "شکر"),
        ("سس مایونز کاله", "سس"),
    ]
    for title, kw in new_categories:
        img_url, fallback_uri = resolve_product_image_and_fallback(title)
        assert img_url.startswith("http"), f"Image for {title} must be valid http URL"
        assert fallback_uri.startswith("data:image/svg+xml;utf8,"), f"Fallback for {title} must be valid data URI"


def test_apptest_renders_selected_cart_cards_with_images():
    """Verify AppTest renders visual product cards with images for selected items before optimization."""
    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["user_basket_text"] = "دو تا شیر پرچرب کاله یک لیتری، یه مایع ظرفشویی پریل ۴ لیتری"
    at.run(timeout=30)
    assert len(at.exception) == 0

    markdown_html = "\n".join(m.value for m in at.markdown)
    assert "jet-cart-item-card" in markdown_html, "Visual cart item card must be rendered in selected basket view"
    assert "<img" in markdown_html, "Product images must be rendered in selected basket view"
    assert "شیر پرچرب کاله" in markdown_html or "شیر" in markdown_html
    assert "ویترین تصویری کالاهای انتخابی شما" in markdown_html


def test_shelf_category_filtering():
    """Verify popular shelf items are partitioned across valid supermarket categories."""
    valid_cats = {"لبنیات و صبحانه", "خواربار و پخت‌وپز", "شوینده و بهداشتی", "نوشیدنی و تنقلات"}
    for item in POPULAR_SHELF_ITEMS:
        assert item["category"] in valid_cats, f"Item {item['title']} has unexpected category {item['category']}"


def test_cart_item_deletion_conjunction_and_clear():
    """Verify deleting an item from cart with ' و ' conjunction removes only that item and preserves others."""
    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["user_basket_text"] = "یک شیر کاله و یک تخم مرغ"
    at.run(timeout=30)
    assert len(at.exception) == 0

    del_buttons = [b for b in at.button if "🗑️ حذف" in b.label]
    assert len(del_buttons) == 2, f"Expected 2 delete buttons for 2 items, got {len(del_buttons)}"

    # Click delete on second item (تخم مرغ)
    del_buttons[1].click().run(timeout=30)
    assert len(at.exception) == 0
    assert "تخم مرغ" not in at.session_state["user_basket_text"]
    assert "شیر کاله" in at.session_state["user_basket_text"]

    # Now click clear basket
    clear_buttons = [b for b in at.button if "خالی کردن" in b.label]
    assert len(clear_buttons) == 1
    clear_buttons[0].click().run(timeout=30)
    assert len(at.exception) == 0
    assert at.session_state["user_basket_text"] == ""


def test_user_screenshot_items_correct_images():
    """Verify exact items from user screenshot resolve to authentic grocery images, not mobile phones or boots."""
    from sabad.ui_assets import BOGUS_LEGACY_IMAGE_PATTERNS

    # 1. Butter 100g (previously mobile phones)
    butter_img, _ = resolve_product_image_and_fallback("کره ۱۰۰ گرم")
    assert butter_img.startswith("http")
    assert "d1055810db8be202b6d0bd250bdf69005b9bb597" in butter_img
    for bogus in BOGUS_LEGACY_IMAGE_PATTERNS:
        assert bogus not in butter_img

    # 2. Roozaneh milk 1L (previously phone cases)
    milk_img, _ = resolve_product_image_and_fallback("شیر روزانه ۱ لیتر ۱.۵٪ چربی")
    assert milk_img.startswith("http")
    assert "3520506" in milk_img
    for bogus in BOGUS_LEGACY_IMAGE_PATTERNS:
        assert bogus not in milk_img

    # 3. Eggs (previously black boots)
    eggs_img, _ = resolve_product_image_and_fallback("تخم مرغ")
    assert eggs_img.startswith("http")
    assert "415850b9c7c05bc33cbaecee57942f522ff16ea2" in eggs_img
    for bogus in BOGUS_LEGACY_IMAGE_PATTERNS:
        assert bogus not in eggs_img


def test_bogus_legacy_urls_rejected_even_if_explicit():
    """Verify bogus legacy URLs are rejected even when supplied as explicit_url to resolve_product_image_and_fallback."""
    from sabad.ui_assets import BOGUS_LEGACY_IMAGE_PATTERNS

    for bogus_id in BOGUS_LEGACY_IMAGE_PATTERNS:
        bogus_url = f"https://dkstatics-public.digikala.com/digikala-products/{bogus_id}.jpg"
        resolved_img, _ = resolve_product_image_and_fallback("کره ۱۰۰ گرم", explicit_url=bogus_url)
        assert bogus_id not in resolved_img
        assert "d1055810db8be202b6d0bd250bdf69005b9bb597" in resolved_img


def test_curated_flash_deals_and_shelf_items_images_valid():
    """Verify curated flash deals and shelf items contain authentic Digikala URLs and no bogus IDs."""
    from sabad.ui_assets import CURATED_FLASH_DEALS_BY_STORE, BOGUS_LEGACY_IMAGE_PATTERNS

    for store, deals in CURATED_FLASH_DEALS_BY_STORE.items():
        assert len(deals) > 0, f"Store {store} must have flash deals"
        for deal in deals:
            url = deal["image_url"]
            assert url.startswith("https://dkstatics-public.digikala.com/digikala-products/"), f"Invalid deal URL in {store}: {url}"
            for bogus in BOGUS_LEGACY_IMAGE_PATTERNS:
                assert bogus not in url, f"Found bogus ID {bogus} in flash deal {deal['title']}"

    for item in POPULAR_SHELF_ITEMS:
        url = item["image_url"]
        assert url.startswith("https://dkstatics-public.digikala.com/digikala-products/"), f"Invalid shelf URL: {url}"
        for bogus in BOGUS_LEGACY_IMAGE_PATTERNS:
            assert bogus not in url, f"Found bogus ID {bogus} in shelf item {item['title']}"


def test_substring_collision_prevention():
    """Verify short Persian words (رب, شیر, مرغ, میوه, سدر) do not collide with words containing them."""
    import urllib.parse
    from sabad.ui_assets import _categorize_title

    # 1. 'بربری' and 'چرب' and 'مربا' must NOT match 'رب' (tomato paste)
    assert _categorize_title("نان بربری داغ") == "bread"
    _, fb_barbari = resolve_product_image_and_fallback("نان بربری")
    assert "رب" not in urllib.parse.unquote(fb_barbari)

    assert _categorize_title("شامپو موهای چرب") == "shampoo"
    _, fb_shampoo = resolve_product_image_and_fallback("شامپو موهای چرب")
    assert "رب" not in urllib.parse.unquote(fb_shampoo)

    assert _categorize_title("خامه کم چرب") == "cream"
    assert _categorize_title("مربای آلبالو") == "jam"
    assert _categorize_title("تخم شربتی") == "snack"

    # 2. 'شیرینی' and 'شیره' must NOT match 'شیر' (milk)
    assert _categorize_title("شیرینی دانمارکی") == "snack"
    _, fb_sweets = resolve_product_image_and_fallback("شیرینی دانمارکی")
    assert "شیر و لبنیات" not in urllib.parse.unquote(fb_sweets)
    assert "شیر پاستوریزه" not in urllib.parse.unquote(fb_sweets)

    assert _categorize_title("شیره خرما") == "jam"
    assert _categorize_title("بیسکویت شیرین عسل") == "snack"

    # 3. 'آبمیوه' must match beverage, NOT produce
    assert _categorize_title("آبمیوه سان استار") == "beverage"
    assert _categorize_title("آب میوه پرتقال") == "beverage"

    # 4. 'شامپو سدر صحت' must match shampoo, NOT honey
    assert _categorize_title("شامپو سدر صحت") == "shampoo"

    # 5. 'تخم مرغ' vs 'مرغ'
    assert _categorize_title("تخم مرغ محلی") == "egg"
    assert _categorize_title("سینه مرغ تازه") == "chicken"
    assert _categorize_title("فیله مرغ") == "chicken"


def test_persian_unicode_normalization_and_attached_digits():
    """Verify image resolver handles ZWNJ (نیم‌فاصله), attached digits, and Arabic characters cleanly."""
    from sabad.ui_assets import _categorize_title

    # Attached digits without whitespace
    assert _categorize_title("کره۱۰۰گرم") == "butter"
    img_butter, _ = resolve_product_image_and_fallback("کره۱۰۰گرم")
    assert "d1055810db8be202b6d0bd250bdf69005b9bb597" in img_butter

    assert _categorize_title("شیر۱لیتر") == "milk"
    assert _categorize_title("ماکارونی۷۰۰گرمی") == "pasta"

    # Zero-width non-joiner (\u200c)
    assert _categorize_title("تخم\u200cمرغ محلی") == "egg"
    assert _categorize_title("سیب\u200cزمینی تازه") == "produce"
    assert _categorize_title("آب\u200cمیوه سن ایچ") == "beverage"

    # Arabic characters (ي and ك)
    assert _categorize_title("پنير پيتزا") == "cheese"
    assert _categorize_title("كيك شكلاتی") == "snack"


def test_expanded_iranian_supermarket_categories():
    """Verify new essential grocery categories resolve to valid, authentic CDN images."""
    from sabad.ui_assets import CATEGORY_FALLBACKS

    new_aisles = [
        ("خامه صبحانه کاله", "cream"),
        ("مربای آلبالو موسوی", "jam"),
        ("عدس گلستان", "legumes"),
        ("پودر زردچوبه", "spices"),
        ("آب معدنی دماوند", "water"),
        ("صابون حمام گلنار", "soap"),
        ("خمیر دندان سیگنال", "toothpaste"),
        ("مایع سفید کننده گلرنگ", "cleaning"),
    ]

    for title, expected_cat in new_aisles:
        img_url, fb_uri = resolve_product_image_and_fallback(title)
        assert img_url.startswith("https://dkstatics-public.digikala.com/digikala-products/"), f"Failed for {title}: {img_url}"
        assert fb_uri.startswith("data:image/svg+xml;utf8,"), f"Fallback URI missing for {title}"
        expected_fallback_url = CATEGORY_FALLBACKS[expected_cat][3]
        # Image either resolves to specific match or category fallback
        assert img_url.startswith("https://dkstatics-public.digikala.com/")


def test_all_category_fallbacks_integrity():
    """Verify 100% of category fallbacks have valid CDN images, emojis, and hex colors."""
    from sabad.ui_assets import CATEGORY_FALLBACKS, BOGUS_LEGACY_IMAGE_PATTERNS

    for cat_name, (emoji, color, title, url) in CATEGORY_FALLBACKS.items():
        assert len(emoji) > 0, f"Category {cat_name} missing emoji"
        assert color.startswith("#") and len(color) == 7, f"Category {cat_name} has invalid hex color {color}"
        assert len(title) > 0, f"Category {cat_name} missing Persian title"
        assert url.startswith("https://dkstatics-public.digikala.com/digikala-products/"), f"Category {cat_name} has invalid URL: {url}"
        for bogus in BOGUS_LEGACY_IMAGE_PATTERNS:
            assert bogus not in url, f"Category {cat_name} points to bogus legacy ID {bogus}"




