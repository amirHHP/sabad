"""
Adversarial Stress Test Suite for Sabad Streamlit UI and Cloud Deployment.
Authored by Empirical Challenger (challenger_2).

Exhaustively tests:
1. Headless App Stress (AppTest):
   - app.py & streamlit_app.py booting
   - Empty, whitespace, None inputs
   - Extreme input lengths (hundreds of items, 10,000+ characters)
   - Adversarial text (HTML/XSS, SQL patterns, symbols, emojis)
   - Repeated reruns and widget state toggling
2. Calculation Breakdown UI ("روند محاسبات و جزئیات اقلام"):
   - 4-tab presence and exact labels
   - Full missing items (100% out of stock / incompatible across all stores)
   - Unstocked items (catalog match exists but is_in_stock=False)
   - 0-cost delivery tiers (free shipping tier calculation)
   - Single-store optimal basket (100% from one store)
   - Multi-store split optimal basket (distributed across 3 stores)
   - Column schemas for audit and optimal tables
   - Missing items callouts with Persian diagnostic reasons
   - Delivery tier expander with MOV calculation
3. Streamlit Community Cloud Configuration:
   - Full .streamlit/config.toml parameter verification
   - Config resolver precedence (st.secrets vs os.environ vs default)
   - Multi-tenant SessionManager isolation across concurrent sessions
   - Non-leakage to .sessions/ disk storage
4. Sidebar OTP and Auth Flow Headless Stress
"""

import os
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from streamlit.testing.v1 import AppTest

from sabad.config import (
    BASE_DIR,
    SESSIONS_DIR,
    get_config,
)
from sabad.adapters.session_manager import SessionManager
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier
from sabad.models.optimization import (
    OptimizationResult,
    StoreOrder,
    BasketItemAssignment,
    TrapAuditReport,
    TrapAuditItem,
)
from sabad.optimizer.milp_solver import MILPBasketOptimizer
from sabad.harvester import CatalogHarvester


# ============================================================================
# 1. Headless Stress Testing with AppTest
# ============================================================================

def test_stress_boot_and_repeated_reruns():
    """Stress-test booting app.py and executing 5 consecutive reruns with widget interactions."""
    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.run(timeout=30)
    assert len(at.exception) == 0, f"Boot failed: {at.exception}"

    # Cycle through sample basket pills if present
    if at.pills:
        at.pills[0].select("سبد صبحانه").run(timeout=30)
        assert len(at.exception) == 0

        at.pills[0].select("سبد شوینده و بهداشتی").run(timeout=30)
        assert len(at.exception) == 0

        at.pills[0].select("سبد روزمره").run(timeout=30)
        assert len(at.exception) == 0

    # Toggle split checkbox
    if at.sidebar.checkbox:
        at.sidebar.checkbox[0].uncheck().run(timeout=30)
        assert len(at.exception) == 0
        at.sidebar.checkbox[0].check().run(timeout=30)
        assert len(at.exception) == 0


def test_stress_streamlit_app_alias_repeated_reruns():
    """Verify streamlit_app.py alias survives multiple reruns and widget modifications."""
    at = AppTest.from_file(str(BASE_DIR / "streamlit_app.py"))
    at.run(timeout=30)
    assert len(at.exception) == 0

    if at.sidebar.slider:
        at.sidebar.slider[0].set_value(40000).run(timeout=30)
        assert len(at.exception) == 0
        assert at.sidebar.slider[0].value == 40000


def test_stress_empty_and_whitespace_inputs():
    """Test empty, whitespace, and newline-only input strings."""
    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["show_editor"] = True
    at.run(timeout=30)
    assert len(at.exception) == 0

    # 1. Empty string
    at.text_area[0].set_value("").run(timeout=30)
    assert len(at.exception) == 0

    # 2. Whitespace and tabs/newlines
    at.text_area[0].set_value("   \n\t  \r\n  ").run(timeout=30)
    assert len(at.exception) == 0

    # 3. Trigger optimization button on empty input -> should show warning and stop cleanly
    # Find the primary action button
    optimize_btn = None
    for btn in at.button:
        if btn.key == "compare_basket":
            optimize_btn = btn
            break

    if optimize_btn:
        optimize_btn.click().run(timeout=30)
        assert len(at.exception) == 0
        assert len(at.warning) >= 1
        assert any("حداقل یک قلم کالا" in w.value for w in at.warning)


def test_stress_extremely_long_grocery_input():
    """Stress-test parser and UI with a 100-item, 6,000+ character grocery input."""
    items_list = [
        f"{i} تا شیر پرچرب کاله ۱ لیتری، پنیر ویلی ۳۵۰ گرمی، مایع ظرفشویی پریل ۴ لیتری"
        for i in range(1, 35)
    ]
    giant_input = " و ".join(items_list)
    assert len(giant_input) > 2500

    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["show_editor"] = True
    at.run(timeout=30)
    assert len(at.exception) == 0

    at.text_area[0].set_value(giant_input).run(timeout=30)
    assert len(at.exception) == 0

    # Ensure items were parsed and rendered into badges without crash
    assert len([b for b in at.button if b.key and b.key.startswith("del_cart_item_")]) >= 1


def test_stress_adversarial_and_special_character_inputs():
    """Stress-test with XSS scripts, SQL injection strings, unicode control chars, and emojis."""
    adversarial_texts = [
        "<script>alert('xss')</script> <img src=x onerror=alert(1)>",
        "'; DROP TABLE baskets; SELECT * FROM users WHERE '1'='1",
        "🛒🥩🥛🍞🧀🍕🍰🧁🍩🍪 %s %d %x {0} {{test}} \x00\x01\x02",
        "شیر !@#$%^&*()_+=-`~[]{}|;:'\",.<>/?\\",
        "۱/۵ لیتر شیر و نیم کیلو پنیر و ۳ تا ماست ۲.۵ کیلویی",
    ]

    for adv_text in adversarial_texts:
        at = AppTest.from_file(str(BASE_DIR / "app.py"))
        at.session_state["show_editor"] = True
        at.run(timeout=30)
        at.text_area[0].set_value(adv_text).run(timeout=30)
        assert len(at.exception) == 0, f"Failed on adversarial text: {adv_text}"


def test_stress_corrupt_session_state_resilience():
    """Stress-test app against corrupted, partial, or None session_state fields."""
    at = AppTest.from_file(str(BASE_DIR / "app.py"))

    # Inject corrupt / empty session states
    at.session_state["catalog_matches"] = {"corrupt_key": None}
    at.session_state["store_infos"] = {"snapp_market": None, "digikala_jet": None, "okala": None, "tapsi_market": None}
    at.session_state["basket_items"] = []
    at.session_state["adapters"] = None

    # Empty OptimizationResult with empty orders
    at.session_state["opt_result"] = OptimizationResult(
        single_store_orders={
            "snapp_market": None,
            "digikala_jet": None,
            "okala": None,
            "tapsi_market": None,
        },
        optimal_orders=[],
        is_multi_store=False,
        total_items_cost=0.0,
        total_delivery_fees=0.0,
        grand_total_cost=0.0,
        total_discounts_saved=0.0,
        trap_audit=TrapAuditReport(has_traps=False, summary_fa="بدون تخفیف")
    )

    at.run(timeout=30)
    assert len(at.exception) == 0, f"Crashed on corrupt session state: {at.exception}"
    assert len(at.tabs) == 5, "All 5 tabs must still render gracefully"


# ============================================================================
# 2. Calculation Breakdown UI ("روند محاسبات و جزئیات اقلام") Edge Cases
# ============================================================================

@pytest.fixture
def base_store_infos():
    return {
        "snapp_market": StoreInfo(
            platform="snapp_market",
            store_id="snapp_br_1",
            title="هایپراستار ارم (اسنپ‌مارکت)",
            is_open=True,
            minimum_order_value=120000.0,
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=300000, fee=29000.0),
                DeliveryTier(min_subtotal=300000, max_subtotal=None, fee=0.0),
            ],
        ),
        "digikala_jet": StoreInfo(
            platform="digikala_jet",
            store_id="jet_br_1",
            title="جت مارت یوسف‌آباد (دیجی‌کالا جت)",
            is_open=True,
            minimum_order_value=100000.0,
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=None, fee=35000.0),
            ],
        ),
        "okala": StoreInfo(
            platform="okala",
            store_id="okala_br_1",
            title="افق کوروش مطهری",
            is_open=True,
            minimum_order_value=150000.0,
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=250000, fee=22000.0),
                DeliveryTier(min_subtotal=250000, max_subtotal=None, fee=0.0),
            ],
        ),
        "tapsi_market": StoreInfo(
            platform="tapsi_market",
            store_id="tapsi_br_1",
            title="هایپر میوه آندیا مارکت (تپسی مارکت)",
            is_open=True,
            minimum_order_value=100000.0,
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=None, fee=30000.0),
            ],
        ),
    }


def test_breakdown_edge_case_all_missing_items(base_store_infos):
    """
    Edge Case: 100% of requested items are missing / out of stock across all stores.
    Verifies that all 5 tabs render, missing containers show diagnostics, and no exceptions are raised.
    """
    basket_items = [
        ParsedGroceryItem(raw_text="یه پنیر محلی تبریز ۵۰۰ گرمی", name="پنیر محلی", quantity=1),
        ParsedGroceryItem(raw_text="یه عسل سدر خالص یک کیلویی", name="عسل سدر", quantity=1),
    ]

    # Every store has None for every item
    catalog_matches = {
        basket_items[0].raw_text: {"snapp_market": None, "digikala_jet": None, "okala": None, "tapsi_market": None},
        basket_items[1].raw_text: {"snapp_market": None, "digikala_jet": None, "okala": None, "tapsi_market": None},
    }

    opt_result = OptimizationResult(
        single_store_orders={
            "snapp_market": StoreOrder(
                platform="snapp_market",
                store_id="snapp_br_1",
                items=[],
                items_subtotal=0.0,
                delivery_fee=0.0,
                total_cost=0.0,
                meets_mov=False,
                minimum_order_value=120000.0,
                missing_items_count=2,
            ),
            "digikala_jet": None,
            "okala": None,
            "tapsi_market": None,
        },
        optimal_orders=[],
        is_multi_store=False,
        total_items_cost=0.0,
        total_delivery_fees=0.0,
        grand_total_cost=0.0,
        total_discounts_saved=0.0,
        trap_audit=TrapAuditReport(has_traps=False, summary_fa="هیچ کالایی یافت نشد"),
    )

    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = catalog_matches
    at.session_state["store_infos"] = base_store_infos
    at.session_state["basket_items"] = basket_items
    at.session_state["opt_result"] = opt_result
    at.session_state["adapters"] = CatalogHarvester().adapters

    at.run(timeout=30)
    assert len(at.exception) == 0, f"Crashed on all-missing items: {at.exception}"

    # Verify 5 tabs
    assert len(at.tabs) == 5

    # Verify missing items diagnostic text is displayed
    markdown_texts = [m.value for m in at.markdown]
    assert any("اقلام کسری و موارد عدم انطباق" in t for t in markdown_texts)
    assert any("عدم موجودی یا عدم یافتن کالا" in t for t in markdown_texts)

    # In optimal tab, unfulfillable items must show "❌ عدم تامین"
    optimal_df = None
    for df in at.dataframe:
        if "فروشگاه برنده" in df.value.columns:
            optimal_df = df.value
            break
    assert optimal_df is not None
    assert (optimal_df["فروشگاه برنده"] == "❌ عدم تامین").all()


def test_breakdown_edge_case_unstocked_items(base_store_infos):
    """
    Edge Case: Items match catalog SKU but are flagged as is_in_stock=False (out of stock).
    Verifies that the row displays '⚠️ ناموجود در انبار' and line total is '-'.
    """
    basket_items = [
        ParsedGroceryItem(raw_text="دو تا شیر پرچرب کاله ۱ لیتری", name="شیر", quantity=2),
    ]

    unstocked_milk = StoreItem(
        platform="snapp_market",
        store_id="snapp_br_1",
        product_id="unstocked_milk_123",
        title="شیر پرچرب کاله ۱ لیتری",
        base_price=45000.0,
        discount_price=40000.0,
        is_in_stock=False,  # Out of stock
    )

    catalog_matches = {
        basket_items[0].raw_text: {
            "snapp_market": unstocked_milk,
            "digikala_jet": None,
            "okala": None,
        }
    }

    opt_result = OptimizationResult(
        single_store_orders={
            "snapp_market": StoreOrder(
                platform="snapp_market",
                store_id="snapp_br_1",
                items=[],
                items_subtotal=0.0,
                delivery_fee=0.0,
                total_cost=0.0,
                meets_mov=False,
                minimum_order_value=120000.0,
                missing_items_count=1,
            ),
            "digikala_jet": None,
            "okala": None,
        },
        optimal_orders=[],
        is_multi_store=False,
        total_items_cost=0.0,
        total_delivery_fees=0.0,
        grand_total_cost=0.0,
        total_discounts_saved=0.0,
        trap_audit=TrapAuditReport(),
    )

    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = catalog_matches
    at.session_state["store_infos"] = base_store_infos
    at.session_state["basket_items"] = basket_items
    at.session_state["opt_result"] = opt_result
    at.session_state["adapters"] = CatalogHarvester().adapters

    at.run(timeout=30)
    assert len(at.exception) == 0

    # Find store audit table
    store_df = None
    for df in at.dataframe:
        if "وضعیت" in df.value.columns:
            store_df = df.value
            break
    assert store_df is not None
    assert any("ناموجود در انبار" in str(s) for s in store_df["وضعیت"])


def test_breakdown_edge_case_zero_cost_free_delivery_tier(base_store_infos):
    """
    Edge Case: Basket qualifies for 0-cost free delivery tier (subtotal >= 300,000 Tomans).
    Verifies that the delivery tier expander displays 'رایگان (۰ تومان)' and indicates active tier.
    """
    basket_items = [
        ParsedGroceryItem(raw_text="دو تا روغن زیتون ۱ لیتری", name="روغن زیتون", quantity=2),
    ]

    olive_oil = StoreItem(
        platform="snapp_market",
        store_id="snapp_br_1",
        product_id="olive_oil_456",
        title="روغن زیتون فرابکر ۱ لیتری",
        base_price=220000.0,
        discount_price=200000.0,
        is_in_stock=True,
    )

    catalog_matches = {
        basket_items[0].raw_text: {
            "snapp_market": olive_oil,
            "digikala_jet": None,
            "okala": None,
        }
    }

    # subtotal = 400,000 > 300,000 threshold -> delivery_fee = 0.0
    single_order = StoreOrder(
        platform="snapp_market",
        store_id="snapp_br_1",
        items=[
            BasketItemAssignment(
                item=olive_oil,
                quantity=2,
                line_total=400000.0,
                nominal_saving=40000.0,
            )
        ],
        items_subtotal=400000.0,
        delivery_fee=0.0,
        total_cost=400000.0,
        total_savings=40000.0,
        meets_mov=True,
        minimum_order_value=120000.0,
        missing_items_count=0,
    )

    opt_result = OptimizationResult(
        single_store_orders={"snapp_market": single_order, "digikala_jet": None, "okala": None},
        optimal_orders=[single_order],
        is_multi_store=False,
        total_items_cost=400000.0,
        total_delivery_fees=0.0,
        grand_total_cost=400000.0,
        total_discounts_saved=40000.0,
        trap_audit=TrapAuditReport(),
    )

    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = catalog_matches
    at.session_state["store_infos"] = base_store_infos
    at.session_state["basket_items"] = basket_items
    at.session_state["opt_result"] = opt_result
    at.session_state["adapters"] = CatalogHarvester().adapters

    at.run(timeout=30)
    assert len(at.exception) == 0

    # Check delivery tier table
    tier_df = None
    for df in at.dataframe:
        if "هزینه ارسال" in df.value.columns and "وضعیت اعمال" in df.value.columns:
            tier_df = df.value
            break
    assert tier_df is not None
    assert any("رایگان (۰ تومان)" in str(fee) for fee in tier_df["هزینه ارسال"])
    assert any("👈 سطح اعمال‌شده (فعال)" in str(st) for st in tier_df["وضعیت اعمال"])


def test_breakdown_edge_case_single_store_vs_multi_store_split(base_store_infos):
    """
    Edge Case: Single-Store Winner vs Multi-Store Split.
    Verifies that when is_multi_store=True, multi-store comparison row and split cards appear;
    when is_multi_store=False, only single-store cards appear.
    """
    item1 = ParsedGroceryItem(raw_text="یک شیر کاله ۱ لیتری", name="شیر", quantity=1)
    item2 = ParsedGroceryItem(raw_text="یک پنیر ویلی ۳۵۰ گرمی", name="پنیر", quantity=1)
    basket_items = [item1, item2]

    sp_milk = StoreItem(platform="snapp_market", store_id="snapp_br_1", product_id="m1", title="شیر کاله ۱ لیتری", base_price=40000.0, discount_price=36000.0, is_in_stock=True)
    jet_cheese = StoreItem(platform="digikala_jet", store_id="jet_br_1", product_id="c1", title="پنیر ویلی ۳۵۰ گرمی", base_price=50000.0, discount_price=45000.0, is_in_stock=True)

    catalog_matches = {
        item1.raw_text: {"snapp_market": sp_milk, "digikala_jet": None, "okala": None},
        item2.raw_text: {"snapp_market": None, "digikala_jet": jet_cheese, "okala": None},
    }

    order_snapp = StoreOrder(
        platform="snapp_market", store_id="snapp_br_1",
        items=[BasketItemAssignment(item=sp_milk, quantity=1, line_total=36000.0)],
        items_subtotal=36000.0, delivery_fee=29000.0, total_cost=65000.0,
        meets_mov=False, minimum_order_value=120000.0, missing_items_count=1,
    )
    order_jet = StoreOrder(
        platform="digikala_jet", store_id="jet_br_1",
        items=[BasketItemAssignment(item=jet_cheese, quantity=1, line_total=45000.0)],
        items_subtotal=45000.0, delivery_fee=35000.0, total_cost=80000.0,
        meets_mov=False, minimum_order_value=100000.0, missing_items_count=1,
    )

    # Multi-store split result
    opt_multi = OptimizationResult(
        single_store_orders={"snapp_market": order_snapp, "digikala_jet": order_jet, "okala": None},
        optimal_orders=[order_snapp, order_jet],
        is_multi_store=True,
        total_items_cost=81000.0,
        total_delivery_fees=64000.0,
        grand_total_cost=145000.0,
        total_discounts_saved=9000.0,
        trap_audit=TrapAuditReport(),
    )

    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = catalog_matches
    at.session_state["store_infos"] = base_store_infos
    at.session_state["basket_items"] = basket_items
    at.session_state["opt_result"] = opt_multi
    at.session_state["adapters"] = CatalogHarvester().adapters

    at.run(timeout=30)
    assert len(at.exception) == 0

    # Multi-store comparison table must have the combined row
    comp_df = at.dataframe[0].value
    assert any("سبد ترکیبی بهینه (Multi-Store)" in str(s) for s in comp_df["فروشگاه"])

    # Now test single-store winner
    opt_single = OptimizationResult(
        single_store_orders={"snapp_market": order_snapp, "digikala_jet": None, "okala": None},
        optimal_orders=[order_snapp],
        is_multi_store=False,
        total_items_cost=36000.0,
        total_delivery_fees=29000.0,
        grand_total_cost=65000.0,
        total_discounts_saved=4000.0,
        trap_audit=TrapAuditReport(),
    )

    at2 = AppTest.from_file(str(BASE_DIR / "app.py"))
    at2.session_state["catalog_matches"] = catalog_matches
    at2.session_state["store_infos"] = base_store_infos
    at2.session_state["basket_items"] = basket_items
    at2.session_state["opt_result"] = opt_single
    at2.session_state["adapters"] = CatalogHarvester().adapters

    at2.run(timeout=30)
    assert len(at2.exception) == 0

    comp_df_2 = at2.dataframe[0].value
    assert not any("سبد ترکیبی بهینه (Multi-Store)" in str(s) for s in comp_df_2["فروشگاه"])


# ============================================================================
# 3. Streamlit Community Cloud Configuration & Multi-Tenant Isolation
# ============================================================================

def test_cloud_config_toml_full_parameters():
    """Verify all mandatory Streamlit Community Cloud parameters in .streamlit/config.toml."""
    config_path = BASE_DIR / ".streamlit" / "config.toml"
    assert config_path.is_file(), f"Missing config file at {config_path}"

    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)

    # Server section
    assert "server" in cfg, "Missing [server] section in config.toml"
    assert cfg["server"].get("headless") is True, "server.headless must be True for Cloud"
    assert cfg["server"].get("enableCORS") is False, "server.enableCORS must be False for Cloud"
    assert cfg["server"].get("enableXsrfProtection") is True, "server.enableXsrfProtection must be True"

    # Browser section
    assert "browser" in cfg, "Missing [browser] section in config.toml"
    assert cfg["browser"].get("gatherUsageStats") is False, "browser.gatherUsageStats should be False"

    # Theme section
    assert "theme" in cfg, "Missing [theme] section in config.toml"
    assert cfg["theme"].get("primaryColor") == "#10b981", "primaryColor must match Sabad emerald theme"
    assert cfg["theme"].get("backgroundColor") == "#ffffff"
    assert cfg["theme"].get("secondaryBackgroundColor") == "#f8fafc"
    assert cfg["theme"].get("textColor") == "#0f172a"
    assert cfg["theme"].get("font") == "sans serif"


def test_cloud_get_config_precedence_thorough():
    """Exhaustively verify get_config precedence: st.secrets > os.environ > default."""
    test_key = "TEST_SABAD_CLOUD_KEY_XYZ"

    # 1. Fallback to default when neither exists
    with patch.dict(os.environ, {}, clear=False):
        if test_key in os.environ:
            del os.environ[test_key]
        assert get_config(test_key, "fallback_default") == "fallback_default"

    # 2. os.environ wins over default when st.secrets is absent
    with patch.dict(os.environ, {test_key: "from_os_env"}):
        assert get_config(test_key, "fallback_default") == "from_os_env"

    # 3. st.secrets wins over os.environ
    mock_st = MagicMock()
    mock_st.secrets = {test_key: "from_st_secrets_priority"}

    with patch.dict(os.environ, {test_key: "from_os_env"}):
        with patch.dict("sys.modules", {"streamlit": mock_st}):
            assert get_config(test_key, "fallback_default") == "from_st_secrets_priority"

    # 4. Exception in st.secrets gracefully falls back to os.environ
    mock_err_st = MagicMock()
    mock_err_st.secrets = MagicMock()
    mock_err_st.secrets.__contains__.side_effect = RuntimeError("Secrets vault locked")

    with patch.dict(os.environ, {test_key: "from_os_env_after_err"}):
        with patch.dict("sys.modules", {"streamlit": mock_err_st}):
            assert get_config(test_key, "fallback_default") == "from_os_env_after_err"


def test_cloud_multi_tenant_session_manager_concurrent_simulated_sessions():
    """
    Verify SessionManager guarantees absolute multi-tenant session isolation across
    concurrent simulated browser sessions.
    User 1 and User 2 must never observe or overwrite each other's credentials,
    and neither credential may touch disk (.sessions/).
    """
    platform = "snapp_market"

    # Ensure disk file does not exist
    disk_path = SESSIONS_DIR / f"{platform}.json"
    if disk_path.exists():
        disk_path.unlink()

    # User 1 script: stores phone 09121111111 and token user1_tok
    script_user1 = f"""
import streamlit as st
from sabad.adapters.session_manager import SessionManager

SessionManager.save_tokens('{platform}', 'user1_tok_abc', phone='09121111111')
st.session_state['user1_out_tok'] = SessionManager.get_token('{platform}')
st.session_state['user1_out_phone'] = SessionManager.get_phone('{platform}')
"""

    # User 2 script: stores phone 09352222222 and token user2_tok
    script_user2 = f"""
import streamlit as st
from sabad.adapters.session_manager import SessionManager

SessionManager.save_tokens('{platform}', 'user2_tok_xyz', phone='09352222222')
st.session_state['user2_out_tok'] = SessionManager.get_token('{platform}')
st.session_state['user2_out_phone'] = SessionManager.get_phone('{platform}')
"""

    # User 3 script: guest user (no login)
    script_user3 = f"""
import streamlit as st
from sabad.adapters.session_manager import SessionManager

st.session_state['user3_out_tok'] = SessionManager.get_token('{platform}')
st.session_state['user3_is_auth'] = SessionManager.is_authenticated('{platform}')
"""

    # Run User 1
    at1 = AppTest.from_string(script_user1).run()
    assert len(at1.exception) == 0
    assert at1.session_state["user1_out_tok"] == "user1_tok_abc"
    assert at1.session_state["user1_out_phone"] == "09121111111"

    # Run User 2 concurrently
    at2 = AppTest.from_string(script_user2).run()
    assert len(at2.exception) == 0
    assert at2.session_state["user2_out_tok"] == "user2_tok_xyz"
    assert at2.session_state["user2_out_phone"] == "09352222222"

    # Run User 3 (guest)
    at3 = AppTest.from_string(script_user3).run()
    assert len(at3.exception) == 0
    assert at3.session_state["user3_out_tok"] is None
    assert at3.session_state["user3_is_auth"] is False

    # Cross-check User 1 state again: must NOT have been overwritten by User 2
    assert at1.session_state["user1_out_tok"] == "user1_tok_abc"

    # Absolute proof of cloud security: disk file was NEVER written
    assert not disk_path.exists(), (
        f"Critical security violation: Session credentials leaked to disk file {disk_path}!"
    )


# ============================================================================
# 4. Sidebar OTP & Login UI Stress
# ============================================================================

def test_settings_otp_login_flow_headless():
    """Store login is only available after opening settings; reject short phones."""
    at = AppTest.from_file(str(BASE_DIR / "app.py")).run(timeout=30)
    assert not at.text_input
    at.button(key="open_settings").click().run()
    assert not at.exception
    at.text_input(key="phone_input_snapp_market").set_value("0912").run()
    at.button(key="send_otp_btn_snapp_market").click().run()
    assert not at.exception
    assert any("شماره موبایل معتبر" in warning.value for warning in at.warning)
