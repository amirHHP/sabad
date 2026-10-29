"""Safe public links for products shown in the comparison UI."""

from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin, urlparse


SEARCH_URLS = {
    "snapp_market": "https://snapp.market/search",
    "digikala_jet": "https://www.digikalajet.com/search",
    "okala": "https://www.okala.com/search",
    "tapsi_market": "https://tapsi.food/search",
}

STORE_ORIGINS = {
    "snapp_market": "https://snapp.market/",
    "digikala_jet": "https://www.digikalajet.com/",
    "okala": "https://www.okala.com/",
    "tapsi_market": "https://tapsi.food/",
}

PUBLIC_HOSTS = {
    "snapp_market": {"snapp.market", "www.snapp.market"},
    "digikala_jet": {"digikalajet.com", "www.digikalajet.com"},
    "okala": {"okala.com", "www.okala.com"},
    "tapsi_market": {"tapsi.food", "www.tapsi.food"},
}

_NUMERIC_ID = re.compile(r"^\d+$")


def digikala_jet_product_page(store_id: str | None, product_id: str | None) -> str | None:
    """Public Digikala Jet product page.

    The site route is ``/shop/product/{shopId}/{productId}/``. ``productId`` is
    the search result ``id`` (the shop product), not the separate ``product_id``
    barcode field. Searching the full title instead makes the Jet API return
    status 404, and the website then shows a not-found page.
    """
    shop = str(store_id or "").strip()
    product = str(product_id or "").strip()
    if not _NUMERIC_ID.fullmatch(shop) or not _NUMERIC_ID.fullmatch(product):
        return None
    return f"https://www.digikalajet.com/shop/product/{shop}/{product}/"


def _jet_search_query(title: str) -> str:
    """Keep the fallback search short enough that Jet does not 404 it."""
    words = title.replace("\u200c", " ").split()
    return " ".join(words[:3])


def build_product_link(
    platform: str,
    title: str,
    product_id: str | None = None,
    explicit_url: str | None = None,
    store_id: str | None = None,
) -> str:
    """Return a clickable product link, preferring an API-provided URL.

    Retailer APIs do not expose one consistent URL field. When a response has
    a canonical URL we preserve it; otherwise the link opens that retailer's
    search page with the exact matched product title and SKU id.
    Digikala Jet is the exception: the product page is built from the shop id
    and shop-product id, because a search for the full title 404s.
    """
    if platform == "digikala_jet":
        page = digikala_jet_product_page(store_id, product_id)
        if page:
            return page
    if isinstance(explicit_url, str) and explicit_url.strip():
        raw_url = explicit_url.strip()
        if raw_url.startswith(("http://", "https://")):
            parsed = urlparse(raw_url)
            public_hosts = PUBLIC_HOSTS.get(platform, set())
            if parsed.netloc and (not public_hosts or parsed.hostname in public_hosts):
                return raw_url
            # API responses occasionally expose the same public path on an
            # API hostname. Never send users to the API JSON endpoint; reuse
            # only its path on the retailer's public origin.
            if parsed.path.startswith(("/product", "/item", "/p/")) and platform in STORE_ORIGINS:
                return urljoin(STORE_ORIGINS[platform], parsed.path + (f"?{parsed.query}" if parsed.query else ""))
        elif raw_url.startswith(("/", "./")) and platform in STORE_ORIGINS:
            # Several retailer APIs return a canonical path such as
            # ``/product/...`` instead of an absolute URL.
            return urljoin(STORE_ORIGINS[platform], raw_url)
        elif raw_url.startswith(("www.", "snapp.", "tapsi.")):
            return f"https://{raw_url}"

    base = SEARCH_URLS.get(platform, "https://www.google.com/search")
    query = title.strip() or (product_id or "محصول")
    if platform == "tapsi_market":
        return f"{base}?query={quote_plus(query)}"
    if platform == "snapp_market":
        return f"{base}?query={quote_plus(query)}"
    if platform == "okala":
        return f"{base}?searchText={quote_plus(query)}"
    if platform == "digikala_jet":
        short_query = _jet_search_query(query)
        return f"{base}?q={quote_plus(short_query or query)}"
    return f"{base}?q={quote_plus(query)}"


__all__ = ["build_product_link", "digikala_jet_product_page"]
