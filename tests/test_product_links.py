from sabad.product_links import build_product_link


def test_relative_product_path_is_resolved_to_public_store_url():
    assert build_product_link(
        "digikala_jet",
        "شامپو",
        explicit_url="/product/shampoo-400",
    ) == "https://www.digikalajet.com/product/shampoo-400"


def test_api_product_url_is_moved_to_public_store_origin():
    assert build_product_link(
        "digikala_jet",
        "شامپو",
        explicit_url="https://api.digikalajet.ir/product/shampoo-400?store=1",
    ) == "https://www.digikalajet.com/product/shampoo-400?store=1"


def test_search_fallback_stays_on_the_public_store_domain():
    url = build_product_link("snapp_market", "ماکارونی آنکارا ۵۰۰ گرمی")
    assert url.startswith("https://snapp.market/search?query=")


def test_digikala_jet_opens_the_product_page():
    title = "شامپو مو لوکس مدل Soft and Smooth مناسب موهای خشک حجم 400 میلی‌لیتر"
    url = build_product_link(
        "digikala_jet",
        title,
        product_id="72232303",
        store_id="193117851239",
        explicit_url="https://www.digikalajet.com/search?q=shampoo",
    )
    assert url == "https://www.digikalajet.com/shop/product/193117851239/72232303/"


def test_digikala_jet_search_fallback_drops_the_long_title():
    title = "شامپو مو لوکس مدل Soft and Smooth مناسب موهای خشک حجم 400 میلی‌لیتر"
    url = build_product_link("digikala_jet", title)
    assert url == "https://www.digikalajet.com/search?q=%D8%B4%D8%A7%D9%85%D9%BE%D9%88+%D9%85%D9%88+%D9%84%D9%88%DA%A9%D8%B3"
