"""
Interactive Live Cart Dispatch Test.
Allows real-world Add-to-Cart mutation against user's authenticated account on:
- SnappMarket
- Digikala Jet
- Okala

Usage:
    python tests/test_live_cart_dispatch.py --platform [snapp_market|digikala_jet|okala]
"""

import asyncio
import sys
import argparse
from sabad.adapters.snapp_market import SnappMarketAdapter
from sabad.adapters.digikala_jet import DigikalaJetAdapter
from sabad.adapters.okala import OkalaAdapter
from sabad.adapters.session_manager import SessionManager
from sabad.models.dispatch import CartItemMutation
from sabad.config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE


async def run_live_dispatch(platform: str, query: str = "شیر"):
    adapters = {
        "snapp_market": SnappMarketAdapter(),
        "digikala_jet": DigikalaJetAdapter(),
        "okala": OkalaAdapter(),
    }

    adapter = adapters.get(platform)
    if not adapter:
        print(f"❌ Unknown platform: {platform}. Choose from {list(adapters.keys())}")
        return

    print(f"\n=======================================================")
    print(f"🛒 LIVE CART DISPATCH TEST: {adapter.platform_title_fa} ({platform})")
    print(f"=======================================================")

    # Step 1: Check Authentication
    if not adapter.is_authenticated():
        print(f"\n⚠️ پلتفرم {adapter.platform_title_fa} در حال حاضر نشست فعال ندارد.")
        phone = input("📱 لطفاً شماره موبایل خود را وارد کنید (مثال: 09123456789): ").strip()
        if not phone:
            print("❌ شماره موبایل وارد نشد.")
            return

        print(f"📩 در حال ارسال کد پیامکی (OTP) به {phone}...")
        send_res = await adapter.send_otp(phone)
        if not send_res.get("success"):
            print(f"❌ خطا در ارسال کد: {send_res.get('message')}")
            return

        challenge_token = send_res.get("challenge_token")
        print(f"✅ {send_res.get('message', 'کد پیامک شد.')}")
        
        otp_code = input("🔑 کد پیامک‌شده را وارد کنید: ").strip()
        if not otp_code:
            print("❌ کد وارد نشد.")
            return

        print("🔍 در حال بررسی کد و صدور توکن نشست...")
        verify_res = await adapter.verify_otp(phone, otp_code, challenge_token)
        if not verify_res.get("success"):
            print(f"❌ احراز هویت ناموفق بود: {verify_res.get('message')}")
            return
        print(f"🎉 {verify_res.get('message', 'ورود موفقیت‌آمیز بود!')}")
    else:
        saved_phone = SessionManager.get_phone(platform) or "شناخته‌شده"
        print(f"✅ نشست فعال یافت شد (شماره: {saved_phone})")

    # Step 2: Resolve Store & Find a Live Product
    print(f"\n📍 استعلام نزدیک‌ترین شعبه و جستجوی کالای '{query}'...")
    store_info = await adapter.get_store_info(DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
    products = await adapter.search(query, DEFAULT_LATITUDE, DEFAULT_LONGITUDE)

    if not products:
        print(f"❌ هیچ کالایی برای '{query}' یافت نشد.")
        return

    target_product = products[0]
    print(f"📦 کالای انتخابی جهت تست:")
    print(f"   • عنوان: {target_product.title}")
    print(f"   • کد محصول (ID): {target_product.product_id}")
    print(f"   • شعبه (Store ID): {target_product.store_id or store_info.store_id}")
    print(f"   • قیمت: {target_product.discount_price:,.0f} تومان")

    # Step 3: Execute Add-To-Cart Mutation
    confirm = input(f"\n❓ آیا می‌خواهید این کالا به سبد حساب کاربری شما اضافه شود؟ (y/n): ").strip().lower()
    if confirm not in ['y', 'yes', 'بله']:
        print("عملیات لغو شد.")
        return

    print("🚀 در حال ارسال درخواست افزودن به سبد خرید (Add to Cart)...")
    mutation = CartItemMutation(
        store_id=target_product.store_id or store_info.store_id,
        product_id=target_product.product_id,
        quantity=1
    )
    result = await adapter.add_to_cart([mutation])

    print("\n-------------------------------------------------------")
    if result.success:
        print(f"🎉 با موفقیت به سبد خرید اضافه شد!")
        print(f"   ✅ تعداد اقلام اضافه شده: {result.items_added}")
        checkout_url = adapter.get_checkout_url()
        print(f"   🔗 لینک مشاهده سبد و پرداخت در {adapter.platform_title_fa}:")
        print(f"      {checkout_url}")
    else:
        print(f"❌ افزودن به سبد با خطا مواجه شد:")
        print(f"   پیام خطا: {result.error_message}")
    print("-------------------------------------------------------\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Cart Dispatch Tester")
    parser.add_argument(
        "--platform",
        choices=["snapp_market", "digikala_jet", "okala"],
        default="digikala_jet",
        help="Platform to test"
    )
    parser.add_argument("--query", default="شیر", help="Product query to search and add")
    args = parser.parse_args()

    asyncio.run(run_live_dispatch(args.platform, args.query))
