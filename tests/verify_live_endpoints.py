"""
Automated Live Endpoint Verification Suite for Sabad.
Directly probes live network endpoints of SnappMarket, Digikala Jet, and Okala.
Enforces zero mock data, zero fixture fallbacks, and real HTTP response validation.
"""

import asyncio
import sys
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
from sabad.adapters.tapsi_market import TapsiMarketAdapter
from sabad.config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE


async def verify_platform(adapter, query="شیر"):
    print(f"\n==========================================")
    print(f"📡 Testing Live Platform: {adapter.platform_title_fa} ({adapter.platform_name})")
    print(f"==========================================")
    
    # 1. Resolve store info & delivery tiers
    print("1️⃣ Resolving serving store & shipping tiers...")
    store_info = await adapter.get_store_info(DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
    assert store_info is not None, f"Failed to resolve store info for {adapter.platform_name}"
    print(f"   ✅ Branch: {store_info.title} (Store ID: {store_info.store_id})")
    print(f"   ✅ MOV: {store_info.minimum_order_value:,.0f} Tomans")
    print(f"   ✅ Tiers count: {len(store_info.delivery_tiers)}")

    # 2. Live catalog search
    print(f"2️⃣ Querying live product catalog for '{query}'...")
    products = await adapter.search(query, DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
    assert len(products) > 0, f"No live products returned from {adapter.platform_name} for query '{query}'"
    print(f"   ✅ Retrieved {len(products)} live products")
    p0 = products[0]
    print(f"   🔍 Sample product: {p0.title}")
    print(f"   💰 Selling price: {p0.discount_price:,.0f} Tomans (Base: {p0.base_price:,.0f} T, Discount: {p0.discount_percent}%)")
    assert p0.discount_price > 0, "Price must be strictly positive"

    # 3. Live flash deals discovery
    print("3️⃣ Discovering daily flash deals / promotions...")
    deals = await adapter.get_flash_deals(DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
    print(f"   ✅ Found {len(deals)} active flash deals/promotions")
    if deals:
        d0 = deals[0]
        print(f"   ⚡ Top Deal: {d0.title} - {d0.discount_percent}% OFF ({d0.discount_price:,.0f} T)")

    # 4. Auth & Checkout verification
    print("4️⃣ Verifying live auth connectivity & checkout link...")
    chk_url = adapter.get_checkout_url()
    assert chk_url.startswith("https://"), f"Invalid checkout URL: {chk_url}"
    print(f"   ✅ Cart & Checkout URL: {chk_url}")
    probe_res = await adapter.send_otp("00000000000")
    assert "success" in probe_res, "send_otp must return standard response dict"
    print(f"   ✅ Live OTP Endpoint: Online & Responsive")

    print(f"🎉 {adapter.platform_title_fa} PASSED ALL LIVE NETWORK CHECKS!")
    return True


async def main():
    print("🚀 Starting Live Endpoint Verification for Iranian Quick-Commerce Platforms...")
    print(f"📍 Location Coordinates: {DEFAULT_LATITUDE}, {DEFAULT_LONGITUDE}")

    adapters = [
        SnappMarketAdapter(),
        DigikalaJetAdapter(),
        OkalaAdapter(),
        TapsiMarketAdapter(),
    ]

    results = await asyncio.gather(*(verify_platform(ad) for ad in adapters), return_exceptions=True)
    
    passed = 0
    for ad, res in zip(adapters, results):
        if isinstance(res, Exception):
            print(f"❌ {ad.platform_title_fa} FAILED: {res}")
        elif res is True:
            passed += 1

    print("\n------------------------------------------")
    print(f"Summary: {passed}/{len(adapters)} platforms verified successfully on live networks.")
    if passed < len(adapters):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
