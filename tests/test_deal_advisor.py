"""
Unit & Integration Tests for Flash Deal Opportunity Advisor (FlashDealAdvisor).
Verifies:
1. Same-Store Addon Opportunities (40%-70% discounts, no extra shipping, free delivery tier trigger).
2. Store Switch + Super Deal Opportunities (70% deal where switching makes total basket far more profitable).
3. Edge cases: items already in cart, out-of-stock deals, low discounts, missing items in competitor stores.
4. End-to-end integration with MILPBasketOptimizer.
"""

import pytest
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier
from sabad.models.optimization import StoreOrder, BasketItemAssignment, FlashDealOpportunity
from sabad.optimizer.deal_advisor import FlashDealAdvisor
from sabad.optimizer.milp_solver import MILPBasketOptimizer


@pytest.fixture
def sample_stores():
    return {
        "snapp_market": StoreInfo(
            platform="snapp_market",
            store_id="s1",
            title="اسنپ‌مارکت",
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=300000, fee=25000),
                DeliveryTier(min_subtotal=300000, max_subtotal=None, fee=0),
            ],
        ),
        "digikala_jet": StoreInfo(
            platform="digikala_jet",
            store_id="j1",
            title="دیجی‌کالا جت",
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=None, fee=30000),
            ],
        ),
        "okala": StoreInfo(
            platform="okala",
            store_id="o1",
            title="افق کوروش / اکالا",
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=None, fee=20000),
            ],
        ),
    }


def test_same_store_addon_opportunity(sample_stores):
    """
    Scenario: User's optimal basket is at Digikala Jet.
    Digikala Jet has an in-stock 60% flash deal item (Tuna: 95,000 -> 38,000 T).
    Advisor must recommend adding it at low price without extra delivery fee.
    """
    milk = StoreItem(platform="digikala_jet", store_id="j1", product_id="m1", title="شیر کاله ۱ لیتری", base_price=45000, discount_price=40000, is_in_stock=True)
    cheese = StoreItem(platform="digikala_jet", store_id="j1", product_id="c1", title="پنیر ویلی ۳۵۰ گرمی", base_price=60000, discount_price=55000, is_in_stock=True)

    order_jet = StoreOrder(
        platform="digikala_jet",
        store_id="j1",
        items=[
            BasketItemAssignment(item=milk, quantity=1, line_total=40000, nominal_saving=5000),
            BasketItemAssignment(item=cheese, quantity=1, line_total=55000, nominal_saving=5000),
        ],
        items_subtotal=95000,
        delivery_fee=30000,
        total_cost=125000,
        total_savings=10000,
    )

    tuna_deal = StoreItem(
        platform="digikala_jet",
        store_id="j1",
        product_id="jet_deal_tuna",
        title="کنسرو تن ماهی در روغن شیلتون ۱۸۰ گرمی",
        brand="شیلتون",
        base_price=95000,
        discount_price=38000,
        discount_percent=60.0,
        is_flash_deal=True,
        is_in_stock=True,
    )

    flash_deals = {"digikala_jet": [tuna_deal]}

    opps = FlashDealAdvisor.find_opportunities(
        basket_items=[ParsedGroceryItem(raw_text="شیر", name="شیر", quantity=1), ParsedGroceryItem(raw_text="پنیر", name="پنیر", quantity=1)],
        catalog_matches={},
        store_infos=sample_stores,
        single_store_orders={"digikala_jet": order_jet},
        optimal_orders=[order_jet],
        flash_deals_by_store=flash_deals,
    )

    same_store = [o for o in opps if o.opportunity_type == "same_store_addon"]
    assert len(same_store) >= 1
    tuna_opps = [o for o in same_store if o.deal_item.product_id == "jet_deal_tuna"]
    assert len(tuna_opps) == 1
    best_deal = tuna_opps[0]
    assert best_deal.deal_item.product_id == "jet_deal_tuna"
    assert best_deal.deal_discount_percent == 60.0
    assert best_deal.deal_nominal_saving == 57000
    assert best_deal.projected_basket_cost == 125000 + 38000
    assert best_deal.projected_basket_savings == 10000 + 57000
    assert "دیجی‌کالا جت" in best_deal.message_fa
    assert "38,000" in best_deal.action_label_fa or "۳۸,۰۰۰" in best_deal.action_label_fa or "38000" in best_deal.action_label_fa


def test_same_store_addon_unlocks_free_shipping(sample_stores):
    """
    Scenario: Order at SnappMarket has subtotal 280,000 T (delivery fee = 25,000 T).
    Adding a 50% deal item worth 30,000 T brings subtotal to 310,000 T,
    unlocking the 0 T free shipping tier!
    The delivery fee drop offsets the product price.
    """
    item1 = StoreItem(platform="snapp_market", store_id="s1", product_id="x1", title="روغن", base_price=300000, discount_price=280000, is_in_stock=True)
    order_snapp = StoreOrder(
        platform="snapp_market",
        store_id="s1",
        items=[BasketItemAssignment(item=item1, quantity=1, line_total=280000, nominal_saving=20000)],
        items_subtotal=280000,
        delivery_fee=25000,
        total_cost=305000,
        total_savings=20000,
    )

    butter_deal = StoreItem(
        platform="snapp_market",
        store_id="s1",
        product_id="deal_butter",
        title="کره پاستوریزه ۱۰۰ گرمی",
        base_price=60000,
        discount_price=30000,
        discount_percent=50.0,
        is_flash_deal=True,
        is_in_stock=True,
    )

    opps = FlashDealAdvisor.find_opportunities(
        basket_items=[ParsedGroceryItem(raw_text="روغن", name="روغن", quantity=1)],
        catalog_matches={},
        store_infos=sample_stores,
        single_store_orders={"snapp_market": order_snapp},
        optimal_orders=[order_snapp],
        flash_deals_by_store={"snapp_market": [butter_deal]},
    )

    same_store = [o for o in opps if o.opportunity_type == "same_store_addon" and o.deal_item.product_id == "deal_butter"]
    assert len(same_store) == 1
    deal_opp = same_store[0]
    # Old total: 280k + 25k = 305k
    # New subtotal: 310k -> tier fee = 0 -> new total = 310k!
    assert deal_opp.projected_basket_cost == 310000.0
    # Net profit increase includes nominal saving (30k) + shipping saved (25k) = 55k!
    assert deal_opp.net_profit_increase == 55000.0


def test_store_switch_deal_opportunity_cheaper_total(sample_stores):
    """
    Scenario: Current optimal store is SnappMarket (Total cost = 280,000 T, Savings = 15,000 T).
    Alternative store Okala can fulfill the same basket for 200,000 T + 20,000 T shipping = 220,000 T.
    Okala also offers a 70% flash deal on Espresso Coffee (200,000 T -> 60,000 T, saving 140,000 T).
    If user switches to Okala AND adds Coffee:
    Total payment = 200,000 + 60,000 + 20,000 = 280,000 T (equal or cheaper!).
    Total savings = 30,000 (basket) + 140,000 (coffee) = 170,000 T!
    Advisor must recommend the golden store switch.
    """
    order_snapp = StoreOrder(
        platform="snapp_market",
        store_id="s1",
        items=[],
        items_subtotal=255000,
        delivery_fee=25000,
        total_cost=280000,
        total_savings=15000,
    )

    order_okala = StoreOrder(
        platform="okala",
        store_id="o1",
        items=[],
        items_subtotal=200000,
        delivery_fee=20000,
        total_cost=220000,
        total_savings=30000,
        missing_items_count=0,
    )

    coffee_deal = StoreItem(
        platform="okala",
        store_id="o1",
        product_id="okala_deal_coffee",
        title="دانه قهوه اسپرسو ۱۰۰٪ عربیکا بن‌مانو ۲۵۰ گرمی",
        brand="بن مانو",
        base_price=200000,
        discount_price=60000,
        discount_percent=70.0,
        is_flash_deal=True,
        is_in_stock=True,
    )

    opps = FlashDealAdvisor.find_opportunities(
        basket_items=[ParsedGroceryItem(raw_text="شیر و پنیر", name="شیر", quantity=1)],
        catalog_matches={},
        store_infos=sample_stores,
        single_store_orders={"snapp_market": order_snapp, "okala": order_okala},
        optimal_orders=[order_snapp],
        flash_deals_by_store={"okala": [coffee_deal]},
    )

    switch_opps = [o for o in opps if o.opportunity_type == "store_switch_deal" and o.target_store == "okala"]
    assert len(switch_opps) >= 1
    best_switch = switch_opps[0]
    assert best_switch.deal_discount_percent == 70.0
    assert best_switch.is_cheaper_total is True
    assert best_switch.projected_basket_savings > best_switch.current_basket_savings
    assert "افق کوروش / اکالا" in best_switch.message_fa
    assert "۷۰" in best_switch.message_fa or "70" in best_switch.message_fa


def test_deal_already_in_basket_is_not_suggested(sample_stores):
    """
    If the user has already put Tuna in their cart, the advisor must not suggest Tuna again as an add-on.
    """
    tuna_item = StoreItem(
        platform="digikala_jet",
        store_id="j1",
        product_id="jet_deal_tuna",
        title="کنسرو تن ماهی در روغن شیلتون ۱۸۰ گرمی",
        base_price=95000,
        discount_price=38000,
        discount_percent=60.0,
        is_flash_deal=True,
    )

    order_jet = StoreOrder(
        platform="digikala_jet",
        store_id="j1",
        items=[BasketItemAssignment(item=tuna_item, quantity=1, line_total=38000, nominal_saving=57000)],
        items_subtotal=38000,
        delivery_fee=30000,
        total_cost=68000,
        total_savings=57000,
    )

    opps = FlashDealAdvisor.find_opportunities(
        basket_items=[ParsedGroceryItem(raw_text="کنسرو تن ماهی شیلتون", name="تن ماهی", quantity=1)],
        catalog_matches={},
        store_infos=sample_stores,
        single_store_orders={"digikala_jet": order_jet},
        optimal_orders=[order_jet],
        flash_deals_by_store={"digikala_jet": [tuna_item]},
    )

    # Must NOT suggest Tuna as an add-on because it is already in the order
    same_store_tuna = [
        o for o in opps
        if o.opportunity_type == "same_store_addon" and o.deal_item.product_id == "jet_deal_tuna"
    ]
    assert len(same_store_tuna) == 0


def test_milp_solver_integrates_deal_opportunities(sample_stores):
    """
    Verifies that MILPBasketOptimizer.optimize automatically runs FlashDealAdvisor
    and attaches deal_opportunities to OptimizationResult.
    """
    milk = StoreItem(platform="digikala_jet", store_id="j1", product_id="m1", title="شیر کاله ۱ لیتری", base_price=45000, discount_price=45000, is_in_stock=True)

    catalog_matches = {
        "شیر": {
            "digikala_jet": milk,
            "snapp_market": None,
            "okala": None,
        }
    }

    optimizer = MILPBasketOptimizer()
    result = optimizer.optimize(
        basket_items=[ParsedGroceryItem(raw_text="شیر", name="شیر", quantity=1)],
        catalog_matches=catalog_matches,
        store_infos=sample_stores,
        allow_multi_store=False,
    )

    assert hasattr(result, "deal_opportunities")
    assert isinstance(result.deal_opportunities, list)
    assert len(result.deal_opportunities) > 0
    # Check that at least one high-discount deal (40% - 70%) is recommended
    assert any(o.deal_discount_percent >= 40.0 for o in result.deal_opportunities)


def test_ui_renders_flash_deal_opportunities(sample_stores):
    """
    Headless Streamlit UI test verifying:
    1. Render of same-store addon opportunity and store-switch opportunity.
    2. Interactive button click adds the discounted item to user_basket_text.
    """
    from streamlit.testing.v1 import AppTest
    from sabad.config import BASE_DIR
    from sabad.models.optimization import FlashDealOpportunity, OptimizationResult, TrapAuditReport

    b_item = ParsedGroceryItem(raw_text="شیر کاله ۱ لیتری", name="شیر", quantity=1)
    sp_milk = StoreItem(platform="digikala_jet", store_id="j1", product_id="m1", title="شیر کاله ۱ لیتری", base_price=45000, discount_price=40000, is_in_stock=True)

    order_jet = StoreOrder(
        platform="digikala_jet",
        store_id="j1",
        items=[BasketItemAssignment(item=sp_milk, quantity=1, line_total=40000)],
        items_subtotal=40000,
        delivery_fee=30000,
        total_cost=70000,
        total_savings=5000,
    )

    tuna_deal = StoreItem(
        platform="digikala_jet",
        store_id="j1",
        product_id="jet_deal_tuna",
        title="کنسرو تن ماهی در روغن شیلتون ۱۸۰ گرمی",
        brand="شیلتون",
        base_price=95000,
        discount_price=38000,
        discount_percent=60.0,
        is_flash_deal=True,
        is_in_stock=True,
    )

    coffee_deal = StoreItem(
        platform="okala",
        store_id="o1",
        product_id="okala_deal_coffee",
        title="دانه قهوه اسپرسو ۱۰۰٪ عربیکا بن‌مانو ۲۵۰ گرمی",
        brand="بن مانو",
        base_price=200000,
        discount_price=60000,
        discount_percent=70.0,
        is_flash_deal=True,
        is_in_stock=True,
    )

    same_opp = FlashDealOpportunity(
        opportunity_type="same_store_addon",
        deal_item=tuna_deal,
        target_store="digikala_jet",
        target_store_title="دیجی‌کالا جت",
        current_store="digikala_jet",
        current_store_title="دیجی‌کالا جت",
        deal_discount_percent=60.0,
        deal_base_price=95000,
        deal_discount_price=38000,
        deal_nominal_saving=57000,
        current_basket_cost=70000,
        projected_basket_cost=108000,
        current_basket_savings=5000,
        projected_basket_savings=62000,
        net_profit_increase=57000,
        title_fa="پیشنهاد شگفت‌انگیز از همین فروشگاه",
        message_fa="کنسرو تن ماهی با ۶۰٪ تخفیف بدون هزینه ارسال مازاد",
        badge_fa="%60 تخفیف از همین فروشگاه",
        action_label_fa="➕ افزودن به سبد خرید",
    )

    switch_opp = FlashDealOpportunity(
        opportunity_type="store_switch_deal",
        deal_item=coffee_deal,
        target_store="okala",
        target_store_title="افق کوروش / اکالا",
        current_store="digikala_jet",
        current_store_title="دیجی‌کالا جت",
        deal_discount_percent=70.0,
        deal_base_price=200000,
        deal_discount_price=60000,
        deal_nominal_saving=140000,
        current_basket_cost=70000,
        projected_basket_cost=120000,
        current_basket_savings=5000,
        projected_basket_savings=145000,
        net_profit_increase=95000,
        is_cheaper_total=False,
        title_fa="فرصت طلایی تغییر فروشگاه",
        message_fa="تغییر به اکالا به همراه قهوه با ۷۰٪ تخفیف",
        badge_fa="🔥 تغییر به اکالا با %70 تخفیف",
        action_label_fa="🔄 تغییر به اکالا و افزودن کالا",
    )

    opt_result = OptimizationResult(
        single_store_orders={"digikala_jet": order_jet, "okala": None, "snapp_market": None},
        optimal_orders=[order_jet],
        is_multi_store=False,
        total_items_cost=40000,
        total_delivery_fees=30000,
        grand_total_cost=70000,
        total_discounts_saved=5000,
        trap_audit=TrapAuditReport(),
        deal_opportunities=[same_opp, switch_opp],
    )

    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = {b_item.raw_text: {"digikala_jet": sp_milk}}
    at.session_state["store_infos"] = sample_stores
    at.session_state["basket_items"] = [b_item]
    at.session_state["opt_result"] = opt_result
    at.session_state["user_basket_text"] = "یک شیر کاله ۱ لیتری"

    at.run(timeout=30)
    assert len(at.exception) == 0

    markdown_all = " ".join(m.value for m in at.markdown)
    assert "کنسرو تن ماهی" in markdown_all
    assert "بن‌مانو" in markdown_all

    # Find the add-on opportunity button
    btn_addon = None
    for b in at.button:
        b_key = getattr(b, "key", None) or ""
        b_label = getattr(b, "label", None) or ""
        if "btn_addon_opp" in b_key or "افزودن به سبد خرید" in b_label:
            btn_addon = b
            break
    assert btn_addon is not None

    # Click the add-on button and run
    btn_addon.click().run(timeout=30)
    assert len(at.exception) == 0
    # User basket text should now contain the new item
    assert "کنسرو تن ماهی" in at.session_state["user_basket_text"]
    # Verify opt_result and optimal orders were directly updated!
    updated_opt = at.session_state["opt_result"]
    assert len(updated_opt.optimal_orders[0].items) == 2
    assert any(i.item.product_id == "jet_deal_tuna" for i in updated_opt.optimal_orders[0].items)
    assert updated_opt.grand_total_cost == 108000.0


def test_ui_switch_button_updates_store_and_order(sample_stores):
    """
    Headless Streamlit UI test verifying that clicking the store switch opportunity
    directly transfers the active order to the competitor store and adds the deal item.
    """
    from streamlit.testing.v1 import AppTest
    from sabad.config import BASE_DIR
    from sabad.models.optimization import FlashDealOpportunity, OptimizationResult, TrapAuditReport

    b_item = ParsedGroceryItem(raw_text="شیر کاله ۱ لیتری", name="شیر", quantity=1)
    sp_milk_jet = StoreItem(platform="digikala_jet", store_id="j1", product_id="m1", title="شیر کاله ۱ لیتری", base_price=45000, discount_price=40000, is_in_stock=True)
    sp_milk_okala = StoreItem(platform="okala", store_id="o1", product_id="m2", title="شیر کاله ۱ لیتری", base_price=45000, discount_price=35000, is_in_stock=True)

    order_jet = StoreOrder(
        platform="digikala_jet", store_id="j1",
        items=[BasketItemAssignment(item=sp_milk_jet, quantity=1, line_total=40000)],
        items_subtotal=40000, delivery_fee=30000, total_cost=70000, total_savings=5000,
    )
    order_okala = StoreOrder(
        platform="okala", store_id="o1",
        items=[BasketItemAssignment(item=sp_milk_okala, quantity=1, line_total=35000)],
        items_subtotal=35000, delivery_fee=20000, total_cost=55000, total_savings=10000, missing_items_count=0,
    )

    coffee_deal = StoreItem(
        platform="okala", store_id="o1", product_id="okala_deal_coffee", title="قهوه بن‌مانو",
        brand="بن مانو", base_price=200000, discount_price=60000, discount_percent=70.0, is_flash_deal=True, is_in_stock=True,
    )

    switch_opp = FlashDealOpportunity(
        opportunity_type="store_switch_deal", deal_item=coffee_deal, target_store="okala",
        target_store_title="افق کوروش / اکالا", current_store="digikala_jet", current_store_title="دیجی‌کالا جت",
        deal_discount_percent=70.0, deal_base_price=200000, deal_discount_price=60000, deal_nominal_saving=140000,
        current_basket_cost=70000, projected_basket_cost=115000, current_basket_savings=5000,
        projected_basket_savings=150000, net_profit_increase=95000, title_fa="", message_fa="",
        badge_fa="", action_label_fa="🔄 تغییر به اکالا و افزودن کالا",
    )

    opt_result = OptimizationResult(
        single_store_orders={"digikala_jet": order_jet, "okala": order_okala},
        optimal_orders=[order_jet],
        is_multi_store=False,
        total_items_cost=40000,
        total_delivery_fees=30000,
        grand_total_cost=70000,
        total_discounts_saved=5000,
        trap_audit=TrapAuditReport(),
        deal_opportunities=[switch_opp],
    )

    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = {b_item.raw_text: {"digikala_jet": sp_milk_jet, "okala": sp_milk_okala}}
    at.session_state["store_infos"] = sample_stores
    at.session_state["basket_items"] = [b_item]
    at.session_state["opt_result"] = opt_result
    at.session_state["user_basket_text"] = "یک شیر کاله ۱ لیتری"
    at.run(timeout=30)

    btn_switch = [b for b in at.button if "btn_switch_opp" in (getattr(b, "key", "") or "")][0]
    btn_switch.click().run(timeout=30)
    assert len(at.exception) == 0

    updated_opt = at.session_state["opt_result"]
    assert updated_opt.optimal_orders[0].platform == "okala"
    assert any(i.item.product_id == "okala_deal_coffee" for i in updated_opt.optimal_orders[0].items)
    assert "قهوه" in at.session_state["user_basket_text"]


def test_out_of_stock_deal_is_excluded(sample_stores):
    """Deals that are out of stock (is_in_stock=False) must never be recommended."""
    out_of_stock_deal = StoreItem(
        platform="digikala_jet",
        store_id="j1",
        product_id="oos_deal",
        title="روغن آفتابگردان",
        base_price=100000,
        discount_price=30000,
        discount_percent=70.0,
        is_flash_deal=True,
        is_in_stock=False,
    )
    order_jet = StoreOrder(
        platform="digikala_jet", store_id="j1", items=[],
        items_subtotal=50000, delivery_fee=30000, total_cost=80000, total_savings=5000,
    )

    opps = FlashDealAdvisor.find_opportunities(
        basket_items=[ParsedGroceryItem(raw_text="پنیر", name="پنیر", quantity=1)],
        catalog_matches={},
        store_infos=sample_stores,
        single_store_orders={"digikala_jet": order_jet},
        optimal_orders=[order_jet],
        flash_deals_by_store={"digikala_jet": [out_of_stock_deal]},
    )
    assert not any(o.deal_item.product_id == "oos_deal" for o in opps)


def test_low_discount_deal_is_excluded(sample_stores):
    """Deals with low discounts (< 40%) must not be treated as flash deal opportunities."""
    low_disc_deal = StoreItem(
        platform="digikala_jet",
        store_id="j1",
        product_id="low_disc",
        title="شیر معمولی",
        base_price=50000,
        discount_price=45000,
        discount_percent=10.0,
        is_flash_deal=True,
        is_in_stock=True,
    )
    order_jet = StoreOrder(
        platform="digikala_jet", store_id="j1", items=[],
        items_subtotal=50000, delivery_fee=30000, total_cost=80000, total_savings=5000,
    )

    opps = FlashDealAdvisor.find_opportunities(
        basket_items=[ParsedGroceryItem(raw_text="پنیر", name="پنیر", quantity=1)],
        catalog_matches={},
        store_infos=sample_stores,
        single_store_orders={"digikala_jet": order_jet},
        optimal_orders=[order_jet],
        flash_deals_by_store={"digikala_jet": [low_disc_deal]},
        min_discount_percent=40.0,
    )
    assert not any(o.deal_item.product_id == "low_disc" for o in opps)


def test_low_discount_in_catalog_matches_excluded(sample_stores):
    """Items in catalog_matches marked is_flash_deal=True but with low discount must be excluded."""
    sp_milk_fake_deal = StoreItem(
        platform="digikala_jet", store_id="j1", product_id="fake_deal_milk",
        title="شیر پرچرب کاله", base_price=50000, discount_price=46000,
        discount_percent=8.0, is_flash_deal=True, is_in_stock=True,
    )
    order_jet = StoreOrder(
        platform="digikala_jet", store_id="j1", items=[],
        items_subtotal=50000, delivery_fee=30000, total_cost=80000, total_savings=5000,
    )

    opps = FlashDealAdvisor.find_opportunities(
        basket_items=[ParsedGroceryItem(raw_text="ماست", name="ماست", quantity=1)],
        catalog_matches={"شیر": {"digikala_jet": sp_milk_fake_deal}},
        store_infos=sample_stores,
        single_store_orders={"digikala_jet": order_jet},
        optimal_orders=[order_jet],
        min_discount_percent=40.0,
    )
    assert not any(o.deal_item.product_id == "fake_deal_milk" for o in opps)


def test_competitor_store_missing_items_excluded_from_switch(sample_stores):
    """If competitor store cannot fulfill the user's basket items, do not recommend store switch."""
    order_snapp = StoreOrder(
        platform="snapp_market", store_id="s1", items=[],
        items_subtotal=200000, delivery_fee=25000, total_cost=225000, total_savings=10000,
    )
    order_okala = StoreOrder(
        platform="okala", store_id="o1", items=[],
        items_subtotal=150000, delivery_fee=20000, total_cost=170000, total_savings=30000,
        missing_items_count=2,  # Missing items!
    )
    deal_okala = StoreItem(
        platform="okala", store_id="o1", product_id="deal_ok",
        title="قهوه ویژه", base_price=100000, discount_price=30000, discount_percent=70.0, is_in_stock=True,
    )

    opps = FlashDealAdvisor.find_opportunities(
        basket_items=[ParsedGroceryItem(raw_text="شیر و پنیر", name="شیر", quantity=1)],
        catalog_matches={},
        store_infos=sample_stores,
        single_store_orders={"snapp_market": order_snapp, "okala": order_okala},
        optimal_orders=[order_snapp],
        flash_deals_by_store={"okala": [deal_okala]},
    )
    switch_opps = [o for o in opps if o.opportunity_type == "store_switch_deal" and o.target_store == "okala"]
    assert len(switch_opps) == 0


def test_token_boundary_no_false_positive_exclusion(sample_stores):
    """
    Substrings like 'نان' in 'کمپوت آناناس' or 'شیر' in 'شیره انگور' must NOT falsely
    cause the deal to be considered already in the basket.
    """
    bread_basket = [ParsedGroceryItem(raw_text="نان بربری", name="نان", quantity=1)]
    ananas_deal = StoreItem(
        platform="digikala_jet", store_id="j1", product_id="ananas_60",
        title="کمپوت آناناس حلقه ای گلدن ویو ۵۶۵ گرمی", base_price=120000,
        discount_price=48000, discount_percent=60.0, is_flash_deal=True, is_in_stock=True,
    )
    order_jet = StoreOrder(
        platform="digikala_jet", store_id="j1", items=[],
        items_subtotal=50000, delivery_fee=30000, total_cost=80000, total_savings=5000,
    )

    opps = FlashDealAdvisor.find_opportunities(
        basket_items=bread_basket,
        catalog_matches={},
        store_infos=sample_stores,
        single_store_orders={"digikala_jet": order_jet},
        optimal_orders=[order_jet],
        flash_deals_by_store={"digikala_jet": [ananas_deal]},
    )
    assert any(o.deal_item.product_id == "ananas_60" for o in opps)


def test_store_switch_marketing_trap_rejected(sample_stores):
    """
    If competitor's baseline basket is significantly more expensive (+40,000 T),
    even if competitor claims high nominal sticker savings, advisor must NOT recommend switching.
    """
    order_snapp = StoreOrder(
        platform="snapp_market", store_id="s1", items=[],
        items_subtotal=100000, delivery_fee=25000, total_cost=125000, total_savings=5000,
    )
    # Okala baseline is 45,000 T more expensive for the same items!
    order_okala = StoreOrder(
        platform="okala", store_id="o1", items=[],
        items_subtotal=150000, delivery_fee=20000, total_cost=170000, total_savings=60000,
        missing_items_count=0,
    )
    deal_okala = StoreItem(
        platform="okala", store_id="o1", product_id="deal_trap",
        title="قهوه ویژه", base_price=50000, discount_price=15000, discount_percent=70.0, is_in_stock=True,
    )

    opps = FlashDealAdvisor.find_opportunities(
        basket_items=[ParsedGroceryItem(raw_text="پنیر", name="پنیر", quantity=1)],
        catalog_matches={},
        store_infos=sample_stores,
        single_store_orders={"snapp_market": order_snapp, "okala": order_okala},
        optimal_orders=[order_snapp],
        flash_deals_by_store={"okala": [deal_okala]},
    )
    switch_opps = [o for o in opps if o.opportunity_type == "store_switch_deal" and o.target_store == "okala"]
    assert len(switch_opps) == 0


def test_apply_opportunity_same_store_addon(sample_stores):
    """Tests FlashDealAdvisor.apply_opportunity for same-store add-on."""
    sp_milk = StoreItem(platform="digikala_jet", store_id="j1", product_id="m1", title="شیر", base_price=45000, discount_price=40000, is_in_stock=True)
    order_jet = StoreOrder(
        platform="digikala_jet", store_id="j1",
        items=[BasketItemAssignment(item=sp_milk, quantity=1, line_total=40000, nominal_saving=5000)],
        items_subtotal=40000, delivery_fee=30000, total_cost=70000, total_savings=5000,
    )
    tuna_deal = StoreItem(
        platform="digikala_jet", store_id="j1", product_id="jet_tuna", title="کنسرو تن ماهی",
        base_price=100000, discount_price=40000, discount_percent=60.0, is_flash_deal=True, is_in_stock=True,
    )
    opportunity = FlashDealOpportunity(
        opportunity_type="same_store_addon", deal_item=tuna_deal, target_store="digikala_jet",
        target_store_title="دیجی‌کالا جت", current_store="digikala_jet", current_store_title="دیجی‌کالا جت",
        deal_discount_percent=60.0, deal_base_price=100000, deal_discount_price=40000, deal_nominal_saving=60000,
        current_basket_cost=70000, projected_basket_cost=110000, current_basket_savings=5000,
        projected_basket_savings=65000, net_profit_increase=60000, title_fa="", message_fa="", badge_fa="", action_label_fa="",
    )
    from sabad.models.optimization import OptimizationResult, TrapAuditReport
    opt_result = OptimizationResult(
        single_store_orders={"digikala_jet": order_jet},
        optimal_orders=[order_jet],
        is_multi_store=False,
        total_items_cost=40000,
        total_delivery_fees=30000,
        grand_total_cost=70000,
        total_discounts_saved=5000,
        trap_audit=TrapAuditReport(),
        deal_opportunities=[opportunity],
    )
    b_items = [ParsedGroceryItem(raw_text="شیر", name="شیر", quantity=1)]
    cat_matches = {"شیر": {"digikala_jet": sp_milk}}

    upd_opt, upd_b_items, upd_cat = FlashDealAdvisor.apply_opportunity(
        opt_result=opt_result,
        opportunity=opportunity,
        store_infos=sample_stores,
        basket_items=b_items,
        catalog_matches=cat_matches,
    )

    assert len(upd_opt.optimal_orders[0].items) == 2
    assert upd_opt.total_items_cost == 80000.0
    assert upd_opt.grand_total_cost == 110000.0
    assert upd_opt.total_discounts_saved == 65000.0
    assert len(upd_b_items) == 2
    assert len(upd_opt.deal_opportunities) == 0


def test_empty_inputs_deal_advisor():
    """Empty inputs must return empty list without exceptions."""
    opps = FlashDealAdvisor.find_opportunities(
        basket_items=[],
        catalog_matches={},
        store_infos={},
        single_store_orders={},
        optimal_orders=[],
    )
    assert opps == []




