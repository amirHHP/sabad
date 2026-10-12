"""
Automated tests for Streamlit UI and Cloud Deployment Preparation (M4).
Verifies headless app booting, alias entrypoint, multi-tenant session isolation,
and unified secrets/configuration resolution.
"""

import os
import tomllib
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from streamlit.testing.v1 import AppTest

from sabad.config import (
    BASE_DIR,
    SESSIONS_DIR,
    get_config,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DEFAULT_SPLIT_PENALTY_TOMANS,
)
from sabad.adapters.session_manager import SessionManager
from sabad.models.grocery import ParsedGroceryItem
from sabad.models.catalog import StoreItem, StoreInfo, DeliveryTier
from sabad.optimizer.milp_solver import MILPBasketOptimizer
from sabad.harvester import CatalogHarvester


def test_app_boots_headlessly():
    """Verify app.py boots headlessly without unhandled exceptions or crashes."""
    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.run(timeout=30)
    assert len(at.exception) == 0, f"app.py crashed with exceptions: {at.exception}"
    
    # Assert primary UI elements rendered
    assert len(at.text_area) >= 1, "Persian grocery text area must be present"
    assert len(at.button) >= 1, "Action buttons must be present"
    assert len(at.selectbox) >= 1, "Location selector in sidebar must be present"


def test_streamlit_app_alias_boots_headlessly():
    """Verify streamlit_app.py alias entry point runs and imports app cleanly."""
    at = AppTest.from_file(str(BASE_DIR / "streamlit_app.py"))
    at.run(timeout=30)
    assert len(at.exception) == 0, f"streamlit_app.py crashed with exceptions: {at.exception}"
    assert len(at.text_area) >= 1, "App elements should be loaded via alias entrypoint"


def test_streamlit_config_toml():
    """Verify .streamlit/config.toml is configured with correct server and theme settings."""
    config_path = BASE_DIR / ".streamlit" / "config.toml"
    assert config_path.exists(), ".streamlit/config.toml must exist"

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    # Server settings
    assert data["server"]["headless"] is True
    assert data["server"]["enableCORS"] is False
    assert data["server"]["enableXsrfProtection"] is True

    # Browser settings
    assert data["browser"]["gatherUsageStats"] is False

    # Theme settings
    assert data["theme"]["primaryColor"] == "#10b981"
    assert data["theme"]["backgroundColor"] == "#ffffff"
    assert data["theme"]["secondaryBackgroundColor"] == "#f8fafc"
    assert data["theme"]["textColor"] == "#0f172a"
    assert data["theme"]["font"] == "sans serif"


def test_unified_get_config():
    """Verify get_config resolves environment variables and defaults."""
    test_key = "SABAD_TEST_ENV_KEY_123"
    assert get_config(test_key, "default_val") == "default_val"

    os.environ[test_key] = "custom_env_val"
    try:
        assert get_config(test_key, "default_val") == "custom_env_val"
    finally:
        del os.environ[test_key]


def test_unified_get_config_secrets_precedence():
    """Verify get_config prioritizes st.secrets over os.environ when present."""
    mock_secrets = {"GEMINI_API_KEY": "secret_gemini_key_abc"}
    mock_st = MagicMock()
    mock_st.secrets = mock_secrets

    with patch.dict(os.environ, {"GEMINI_API_KEY": "env_gemini_key_xyz"}):
        with patch.dict("sys.modules", {"streamlit": mock_st}):
            resolved = get_config("GEMINI_API_KEY", "")
            assert resolved == "secret_gemini_key_abc"


def test_session_manager_multi_tenant_isolation_in_streamlit():
    """Verify SessionManager isolates sessions in st.session_state when running inside Streamlit."""
    platform = "test_st_tenant"
    token_value = "isolated_token_secret_12345"
    phone_value = "09129998877"

    # Ensure disk file does not exist before test
    disk_file = SESSIONS_DIR / f"{platform}.json"
    if disk_file.exists():
        disk_file.unlink()

    script = f"""
import streamlit as st
from sabad.adapters.session_manager import SessionManager

# Save token in Streamlit session
SessionManager.save_tokens('{platform}', '{token_value}', phone='{phone_value}')

# Retrieve values
st.session_state['out_token'] = SessionManager.get_token('{platform}')
st.session_state['out_phone'] = SessionManager.get_phone('{platform}')
st.session_state['out_auth'] = SessionManager.is_authenticated('{platform}')
st.session_state['has_isolated_key'] = '_session_{platform}' in st.session_state

# Clear session
SessionManager.clear_session('{platform}')
st.session_state['is_cleared'] = '_session_{platform}' not in st.session_state
"""
    at = AppTest.from_string(script).run()
    assert len(at.exception) == 0, f"AppTest script failed: {at.exception}"

    # Verify state inside the Streamlit instance
    assert at.session_state["out_token"] == token_value
    assert at.session_state["out_phone"] == phone_value
    assert at.session_state["out_auth"] is True
    assert at.session_state["has_isolated_key"] is True
    assert at.session_state["is_cleared"] is True

    # Crucial assertion: disk file was NEVER created (multi-tenant isolation)
    assert not disk_file.exists(), "Streamlit session credentials must not be written to shared disk"


def test_session_manager_cli_fallback():
    """Verify SessionManager falls back to .sessions/ disk files when running outside Streamlit."""
    platform = "test_cli_fallback_tenant"
    token_value = "cli_token_persistent_54321"
    phone_value = "09351234567"

    disk_file = SESSIONS_DIR / f"{platform}.json"
    if disk_file.exists():
        disk_file.unlink()

    try:
        # Running directly in pytest without ScriptRunContext
        assert SessionManager._get_streamlit_session_state() is None

        SessionManager.save_tokens(platform, token_value, phone=phone_value)
        assert disk_file.exists(), "CLI session credentials must be persisted to disk"

        assert SessionManager.get_token(platform) == token_value
        assert SessionManager.get_phone(platform) == phone_value
        assert SessionManager.is_authenticated(platform) is True

        SessionManager.clear_session(platform)
        assert not disk_file.exists(), "clear_session must delete disk file in CLI mode"
        assert SessionManager.get_token(platform) is None
    finally:
        if disk_file.exists():
            disk_file.unlink()


@pytest.fixture
def mock_calculation_data():
    """Generates realistic calculation dataset for testing the audit breakdown UI."""
    basket_items = [
        ParsedGroceryItem(
            raw_text="دو تا شیر پرچرب کاله یک لیتری",
            name="شیر",
            brand="کاله",
            quantity=2,
            volume_weight=1.0,
            unit="لیتر",
            fat_percentage=3.0,
        ),
        ParsedGroceryItem(
            raw_text="یه مایع ظرفشویی پریل ۴ لیتری",
            name="مایع ظرفشویی",
            brand="پریل",
            quantity=1,
            volume_weight=4.0,
            unit="لیتر",
        ),
    ]

    store_infos = {
        "snapp_market": StoreInfo(
            platform="snapp_market",
            store_id="snapp_branch_1",
            title="هایپراستار ارم (اسنپ‌مارکت)",
            is_open=True,
            minimum_order_value=150000.0,
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=450000, fee=29400.0),
                DeliveryTier(min_subtotal=450000, max_subtotal=None, fee=0.0),
            ],
        ),
        "digikala_jet": StoreInfo(
            platform="digikala_jet",
            store_id="jet_branch_1",
            title="جت مارت یوسف‌آباد (دیجی‌کالا جت)",
            is_open=True,
            minimum_order_value=100000.0,
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=None, fee=35000.0),
            ],
        ),
        "okala": StoreInfo(
            platform="okala",
            store_id="okala_branch_1",
            title="افق کوروش شعبه میدان فاطمی",
            is_open=True,
            minimum_order_value=200000.0,
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=300000, fee=25000.0),
                DeliveryTier(min_subtotal=300000, max_subtotal=None, fee=0.0),
            ],
        ),
        "tapsi_market": StoreInfo(
            platform="tapsi_market",
            store_id="tapsi_branch_1",
            title="هایپر میوه آندیا مارکت (تپسی مارکت)",
            is_open=True,
            minimum_order_value=100000.0,
            delivery_tiers=[
                DeliveryTier(min_subtotal=0, max_subtotal=None, fee=30000.0),
            ],
        ),
    }

    item1_snapp = StoreItem(
        platform="snapp_market",
        store_id="snapp_branch_1",
        product_id="sp_milk",
        title="شیر پرچرب کاله ۱ لیتری",
        base_price=42000.0,
        discount_price=37800.0,
        discount_percent=10.0,
        is_in_stock=True,
    )
    item2_snapp = StoreItem(
        platform="snapp_market",
        store_id="snapp_branch_1",
        product_id="sp_pril",
        title="مایع ظرفشویی پریل ۴ لیتری",
        base_price=180000.0,
        discount_price=162000.0,
        discount_percent=10.0,
        is_in_stock=True,
    )

    item1_jet = StoreItem(
        platform="digikala_jet",
        store_id="jet_branch_1",
        product_id="jet_milk",
        title="شیر پرچرب کاله ۱ لیتری",
        base_price=42000.0,
        discount_price=39000.0,
        discount_percent=7.0,
        is_in_stock=True,
    )
    # Jet has no dishwashing liquid (unmatched / missing item)
    item2_jet = None

    item1_okala = StoreItem(
        platform="okala",
        store_id="okala_branch_1",
        product_id="okala_milk",
        title="شیر پرچرب کاله ۱ لیتری",
        base_price=42000.0,
        discount_price=35000.0,
        discount_percent=16.0,
        is_in_stock=True,
    )
    item2_okala = StoreItem(
        platform="okala",
        store_id="okala_branch_1",
        product_id="okala_pril",
        title="مایع ظرفشویی پریل ۴ لیتری",
        base_price=180000.0,
        discount_price=150000.0,
        discount_percent=16.0,
        is_in_stock=True,
    )

    item1_tapsi = StoreItem(
        platform="tapsi_market",
        store_id="tapsi_branch_1",
        product_id="tapsi_milk",
        title="شیر پرچرب کاله ۱ لیتری",
        base_price=42000.0,
        discount_price=36000.0,
        discount_percent=14.0,
        is_in_stock=True,
    )
    item2_tapsi = None

    catalog_matches = {
        basket_items[0].raw_text: {
            "snapp_market": item1_snapp,
            "digikala_jet": item1_jet,
            "okala": item1_okala,
            "tapsi_market": item1_tapsi,
        },
        basket_items[1].raw_text: {
            "snapp_market": item2_snapp,
            "digikala_jet": item2_jet,
            "okala": item2_okala,
            "tapsi_market": item2_tapsi,
        },
    }

    opt_result = MILPBasketOptimizer().optimize(
        basket_items=basket_items,
        catalog_matches=catalog_matches,
        store_infos=store_infos,
        allow_multi_store=True,
    )

    return {
        "basket_items": basket_items,
        "store_infos": store_infos,
        "catalog_matches": catalog_matches,
        "opt_result": opt_result,
        "adapters": CatalogHarvester().adapters,
    }


def test_calculation_breakdown_rendering_with_mock_session_state(mock_calculation_data):
    """Verify interactive calculation breakdown renders all 4 tabs, itemized tables, missing items, and delivery tiers."""
    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = mock_calculation_data["catalog_matches"]
    at.session_state["store_infos"] = mock_calculation_data["store_infos"]
    at.session_state["basket_items"] = mock_calculation_data["basket_items"]
    at.session_state["opt_result"] = mock_calculation_data["opt_result"]
    at.session_state["adapters"] = mock_calculation_data["adapters"]

    at.run(timeout=30)
    assert len(at.exception) == 0, f"app.py crashed: {at.exception}"

    # Verify Section 4 subheader
    subheaders = [s.value for s in at.subheader]
    assert any("روند محاسبات و جزئیات اقلام" in s for s in subheaders), (
        f"Itemized calculation breakdown subheader missing from: {subheaders}"
    )

    # Verify 4 tabs are present with exact expected labels
    tab_labels = [tab.label for tab in at.tabs]
    assert "🏆 سبد بهینه نهایی (تخصیص هوشمند)" in tab_labels
    assert "🟡 اسنپ‌مارکت (SnappMarket)" in tab_labels
    assert "🔴 دیجی‌کالا جت (Digikala Jet)" in tab_labels
    assert "🟢 افق کوروش / اکالا (Okala)" in tab_labels

    # Verify itemized audit tables columns across rendered dataframes
    expected_itemized_cols = {
        "قلم درخواستی",
        "کالای متناظر در فروشگاه",
        "حجم/مشخصات انطباق‌یافته",
        "قیمت پایه واحد (تومان)",
        "قیمت فروش واحد (تومان)",
        "تعداد",
        "مجموع ردیف (تومان)",
        "سود تخفیف (تومان)",
        "وضعیت",
    }
    found_itemized_table = False
    for df in at.dataframe:
        cols = set(df.value.columns)
        if expected_itemized_cols.issubset(cols):
            found_itemized_table = True
            break
    assert found_itemized_table, "Itemized audit table with exact required columns must be rendered"

    # Verify delivery tier expanders and tables
    expander_labels = [exp.label for exp in at.expander]
    assert any("روند محاسبه هزینه ارسال و حداقل سفارش" in label for label in expander_labels), (
        f"Delivery tiers expander missing from: {expander_labels}"
    )

    expected_tier_cols = {"محدوده مبلغ سبد (تومان)", "هزینه ارسال", "وضعیت اعمال"}
    found_tier_table = False
    for df in at.dataframe:
        cols = set(df.value.columns)
        if expected_tier_cols.issubset(cols):
            found_tier_table = True
            break
    assert found_tier_table, "Delivery tier breakdown table must be rendered"

    # Verify missing items diagnostic container is rendered for Digikala Jet (which has 1 missing item)
    markdown_texts = [m.value for m in at.markdown]
    assert any("اقلام کسری و موارد عدم انطباق" in t for t in markdown_texts), (
        "Missing items container heading must be rendered"
    )
    assert any("عدم موجودی یا عدم یافتن کالا در شعبه فعال این فروشگاه" in t for t in markdown_texts), (
        "Diagnostic reason 1 must be rendered in missing items container"
    )
    assert any("رد شدن به دلیل عدم انطباق با حجم درخواستی" in t for t in markdown_texts), (
        "Diagnostic reason 2 must be rendered in missing items container"
    )


def test_calculation_breakdown_optimal_final_basket_tab(mock_calculation_data):
    """Verify optimal final basket tab displays mathematical formula, winning SKUs table, and store split cards."""
    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = mock_calculation_data["catalog_matches"]
    at.session_state["store_infos"] = mock_calculation_data["store_infos"]
    at.session_state["basket_items"] = mock_calculation_data["basket_items"]
    at.session_state["opt_result"] = mock_calculation_data["opt_result"]
    at.session_state["adapters"] = mock_calculation_data["adapters"]

    at.run(timeout=30)
    assert len(at.exception) == 0

    # Verify mathematical formula (LaTeX is rendered)
    assert len(at.latex) >= 1, "Mathematical breakdown formula in LaTeX must be rendered"

    # Verify winning SKU table columns
    expected_optimal_cols = {
        "قلم درخواستی",
        "فروشگاه برنده",
        "کالای برگزیده (SKU)",
        "قیمت واحد (تومان)",
        "تعداد",
        "مجموع ردیف (تومان)",
        "سود تخفیف (تومان)",
    }
    found_optimal_table = False
    for df in at.dataframe:
        cols = set(df.value.columns)
        if expected_optimal_cols.issubset(cols):
            found_optimal_table = True
            break
    assert found_optimal_table, "Optimal basket SKU assignment table must be rendered"

    # Verify store split cards
    markdown_texts = [m.value for m in at.markdown]
    assert any("کارت‌های تفکیک سفارش" in t for t in markdown_texts), (
        "Store split cards section must be rendered"
    )


def test_calculation_breakdown_empty_basket_resilience():
    """Verify breakdown UI handles empty basket or unfulfillable store orders without crashing."""
    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = {}
    at.session_state["store_infos"] = {}
    at.session_state["basket_items"] = []
    at.session_state["opt_result"] = MILPBasketOptimizer().optimize([], {}, {})
    at.session_state["adapters"] = CatalogHarvester().adapters

    at.run(timeout=30)
    assert len(at.exception) == 0, f"app.py crashed on empty basket: {at.exception}"

    # Verify tabs still render safely
    tab_labels = [tab.label for tab in at.tabs]
    assert "🏆 سبد بهینه نهایی (تخصیص هوشمند)" in tab_labels


def test_calculation_breakdown_session_state_persistence_across_reruns(mock_calculation_data):
    """Verify calculation breakdown and opt_result persist across user interactions / reruns."""
    at = AppTest.from_file(str(BASE_DIR / "app.py"))
    at.session_state["catalog_matches"] = mock_calculation_data["catalog_matches"]
    at.session_state["store_infos"] = mock_calculation_data["store_infos"]
    at.session_state["basket_items"] = mock_calculation_data["basket_items"]
    at.session_state["opt_result"] = mock_calculation_data["opt_result"]
    at.session_state["adapters"] = mock_calculation_data["adapters"]

    at.run(timeout=30)
    assert len(at.exception) == 0
    assert len(at.tabs) == 5

    # Trigger a rerun via widget interaction
    if at.checkbox:
        at.checkbox[0].uncheck().run(timeout=30)
        assert len(at.exception) == 0
        assert len(at.tabs) == 5, "Breakdown tabs must remain present across widget reruns"

